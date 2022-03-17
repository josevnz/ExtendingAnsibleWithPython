# Ansible Inventory plugins

On the previous article, you saw how to get a dynamic inventory by writing a very flexible script in Python that uses Nmap results underneath.

But why this may not be desirable? Well, there are a couple of reasons:

1. You want to standardize the language used to write provisioning tools. It is great if your team knows how to write Perl, Ruby, Python, Go, Rust but can you assure than ALL your members are proficient on all of these? it pays off to stick to a few tools and master them!
2. [DRY](https://en.wikipedia.org/wiki/Don%27t_repeat_yourself): You may have to reinvent the wheel. Ansible plugins give you many things for free like services like caching and encryption, configuration management.
3. An Ansible inventory plugin is expected to live in certain specific locations. This makes it predictable and easier to distribute to other servers or to share with other teams (following conventions)

It is time now to cover a third approach to tackle the original issue of dynamic inventories, focusing on Nmap as the discovery tool.

## What are you going to learn on this article?

There are many ways to manage your inventories in Ansible, will cover one last alternative here:

* Writing an Ansible inventory plugin

All this while following good practices of packaging our tools, using virtual environments and unit testing our code.

## Writing an Ansible module

The idea is to take advantage of Ansible ecosystem for common tasks like execution and caching, as [explained in the documentation](https://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html#developing-an-inventory-plugin).

I will take advantage of the parser and Nmap wrapper I wrote earlier, so the module file will have those classes embedded as well.

We will add 'Ansible' as a dependency to make our development easier, for things like auto-completion (```requirements.txt```):

```text
setuptools>=60.5.0
build>=0.7.0
packaging==21.3
wheel==0.37.1
pip-audit==2.0.0
ansible==5.4.0
```

Then we install our dependencies (Ansible it is a HEAVY package, so you should go a grab a coffee):
```shell
# Also you can:
# pip install ansible==5.4.0
pip install -r requirements.txt
```

### How the module looks like?

To keep the dependencies simple for this tutorial, I included the 'OutputParser' and 'NmapRunner' together the module 'nmap_plugin' where the new
plugin class 'NmapInventoryModule' will be:

```python
"""
A simple inventory plugin that uses Nmap to get the list of hosts
Jose Vicente Nunez (kodegeek.com@protonmail.com)
"""

import os.path
from subprocess import CalledProcessError
import os
import shlex
import shutil
import subprocess
from typing import List, Dict, Any
from xml.etree import ElementTree
# The imports below are the ones required for an Ansible plugin
from ansible.errors import AnsibleParserError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

DOCUMENTATION = r'''
    name: nmap_plugin
    plugin_type: inventory
    short_description: Returns a dynamic host inventory from Nmap scan
    description: Returns a dynamic host inventory from Nmap scan, filter machines that can be accessed with SSH
    options:
      plugin:
          description: Name of the plugin
          required: true
          choices: ['nmap_plugin']
      address:
        description: Address to scan, in Nmap supported format
        required: true
'''


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):

    NAME = 'nmap_plugin'

    def __init__(self):
        super(InventoryModule, self).__init__()
        self.address = None
        self.plugin = None

    def verify_file(self, path: str):
        if super(InventoryModule, self).verify_file(path):
            return path.endswith('yaml') or path.endswith('yml')
        return False

    def parse(self, inventory: Any, loader: Any, path: Any, cache: bool = True) -> Any:
        super(InventoryModule, self).parse(inventory, loader, path, cache)
        self._read_config_data(path)  # This also loads the cache
        try:
            self.plugin = self.get_option('plugin')
            self.address = self.get_option('address')
            hosts_data = list(NmapRunner(self.address))
            if not hosts_data:
                raise AnsibleParserError("Unable to get data for Nmap scan!")
            for host_data in hosts_data:
                for name, address in host_data.items():
                    self.inventory.add_host(name)
                    self.inventory.set_variable(name, 'ip', address)
        except KeyError as kerr:
            raise AnsibleParserError(f'Missing required option on the configuration file: {path}', kerr)
        except CalledProcessError as cpe:
            raise AnsibleParserError("There was an error while calling Nmap", cpe)


class OutputParser:
    def __init__(self, xml: str):
        self.xml = xml

    def get_addresses(self) -> List[Dict[str, str]]:
        """
        Several things need to happen for an address to be included:
        1. Host is up
        2. Port is TCP 22
        3. Port status is open
        4. Uses IPv4
        """
        addresses = []
        root = ElementTree.fromstring(self.xml)
        for host in root.findall('host'):
            name = None
            for hostnames in host.findall('hostnames'):
                for hostname in hostnames:
                    name = hostname.attrib['name']
                    break
            if not name:
                continue
            is_up = True
            for status in host.findall('status'):
                if status.attrib['state'] == 'down':
                    is_up = False
                    break
            if not is_up:
                continue
            port_22_open = False
            for ports in host.findall('ports'):
                for port in ports.findall('port'):
                    if port.attrib['portid'] == '22':
                        for state in port.findall('state'):
                            if state.attrib['state'] == "open":  # Up not the same as open, we want SSH access!
                                port_22_open = True
                                break
            if not port_22_open:
                continue
            address = None
            for address_data in host.findall('address'):
                address = address_data.attrib['addr']
                break
            addresses.append({name: address})
        return addresses


class NmapRunner:

    def __init__(self, hosts: str):
        self.nmap_report_file = None
        found_nmap = shutil.which('nmap', mode=os.F_OK | os.X_OK)
        if not found_nmap:
            raise ValueError("Nmap binary is missing!")
        self.nmap = found_nmap
        self.hosts = hosts

    def __iter__(self):
        command = [self.nmap]
        command.extend(__NMAP__FLAGS__)
        command.append(self.hosts)
        completed = subprocess.run(
            command,
            capture_output=True,
            shell=False,
            check=True
        )
        completed.check_returncode()
        out_par = OutputParser(completed.stdout.decode('utf-8'))
        self.addresses = out_par.get_addresses()
        return self

    def __next__(self):
        try:
            return self.addresses.pop()
        except IndexError:
            raise StopIteration


"""
Convert the args for proper usage on the Nmap CLI
Also, do not use the -n flag. We need to resolve IP addresses to hostname, even if we sacrifice a little bit of speed
"""
NMAP_DEFAULT_FLAGS = {
    '-p22': 'Port 22 scanning',
    '-T4': 'Aggressive timing template',
    '-PE': 'Enable this echo request behavior. Good for internal networks',
    '--disable-arp-ping': 'No ARP or ND Ping',
    '--max-hostgroup 50': 'Hostgroup (batch of hosts scanned concurrently) size',
    '--min-parallelism 50': 'Number of probes that may be outstanding for a host group',
    '--osscan-limit': 'Limit OS detection to promising targets',
    '--max-os-tries 1': 'Maximum number of OS detection tries against a target',
    '-oX -': 'Send XML output to STDOUT, avoid creating a temp file'
}
__NMAP__FLAGS__ = shlex.split(" ".join(NMAP_DEFAULT_FLAGS.keys()))
```

Things to notice on the InventoryModule:

* If some of these classes look familiar is because we reused the Nmap wrapper and XML parsing we wrote for the dynamic inventory script.
* The method __verify_file__ doesn't need be implemented, but __it is a good idea__. It decides if a configuration file is good enough to be used
* The plugin class requires the parse method to be implemented. This is where Nmap is called, XML output is parsed and inventory is populated
* It uses multiple inheritance and because of that we get a few things for free, like configuration parsing, caching.
* All the exceptions coming from this module must be wrapped around an AnsibleParserError

Our configuration file is in place from the previous exercise, let's now deploy the module where ansible can find it:

```shell
[josevnz@dmaf5 ExtendingAnsibleWithPython]$ ansible-config dump|grep DEFAULT_INVENTORY_PLUGIN_PATH
DEFAULT_INVENTORY_PLUGIN_PATH(default) = ['/home/josevnz/.ansible/plugins/inventory', '/usr/share/ansible/plugins/inventory']
/bin/mkdir --parents --verbose /home/josevnz/.ansible/plugins/inventory/
/bin/cp -p -v Inventories/inventories/nmap_plugin.py /home/josevnz/.ansible/plugins/inventory/
```

And define an inventory file that uses the new plugin ([nmap_plugin_inventory.yaml](test/nmap_plugin_inventory.yaml)):
```yaml
# Sample configuration file for custom nmap_plugin. Yes, it is the same file we used for tye dynamic inventory script
---
plugin: nmap_plugin
address: 192.168.1.0/24
```

Let's test the new module:

```shell
# Does Ansible recognize it?
[josevnz@dmaf5 ExtendingAnsibleWithPython]$ ansible-doc -t inventory -l|grep nmap_plugin
nmap_plugin         Returns a dynamic host inventory from Nmap scan
```

```shell
# Smoke test, check if we get any host listed
(ExtendingAnsibleWithPythonInventory) [josevnz@dmaf5 Inventories]$ ansible-inventory --inventory $PWD/test/nmap_plugin_inventory.yaml  --list -v -v -v
[josevnz@dmaf5 ExtendingAnsibleWithPython]$ ansible-inventory --inventory Inventories/test/nmap_plugin_inventory.yaml --list
{
    "_meta": {
        "hostvars": {
            "dmaf5.home": {
                "ip": "192.168.1.25"
            },
            "macmini2": {
                "ip": "192.168.1.16"
            },
            "raspberrypi": {
                "ip": "192.168.1.11"
            }
        }
    },
    "all": {
        "children": [
            "ungrouped"
        ]
    },
    "ungrouped": {
        "hosts": [
            "dmaf5.home",
            "macmini2",
            "raspberrypi"
        ]
    }
}
```

Results are the same as the dynamic inventory plugin. But if you enable other functionality, like caching results (not covered here) you will see some benefits, like a speed-up on the inventory generation (things like this are huge if you number of hosts is big)

## What is next?

You created an inventory plugin, taking advantage of the Ansible environment to build our network scanner without too much boilerplate code. It is also a more rigid compared with the dynamic inventory script, but you get several services for free like caching and configuration file parsing.

But there is more to learn!; now that you know at least 3 ways to handle dynamic inventories I recommend you to also check the following content:

* [Official documentation](https://docs.ansible.com/ansible/latest/user_guide/intro_inventory.html)
* [Managing Meaningful inventories - Ansible fest 2019](https://www.ansible.com/managing-meaningful-inventories)
* [Ansible Inventory for Fun And Profit](https://www.ansible.com/ansible-inventory-for-fun-and-profit)
* [Ansible Custom Inventory Plugin - a hands-on, quick start guide](https://termlen0.github.io/2019/11/16/observations/): This is another very well done tutorial on how to write inventory plugins, but also how to troubleshoot them.
* Ansible's collections through [Ansible Galaxy](https://docs.ansible.com/ansible/latest/user_guide/collections_using.html): There is a more robust way to package and share your Ansible modules, just like using [pip](https://pypi.org/project/pip/) to install Python modules.

Remember, you [can download the code](https://github.com/josevnz/ExtendingAnsibleWithPython) and experiment!. The best way to learn is by doing and making mistakes.



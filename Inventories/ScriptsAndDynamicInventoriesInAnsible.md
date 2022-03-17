# Scripts and dynamic inventories with Ansible

On the [previous article](BeyondStaticInventoriesInAnsible.md) of this series, you saw why it is not very convenient to use a static inventory to handle your Ansible playbooks:

* The inventory can be quite large
* Or the servers on the inventory that require automation can change constantly (for example, a pool of Linux laptops that use DHCP)

To cover that gap, used the host list and the Nmap plugins to generate a dynamic inventory.

## What are you going to learn on this article?

In this article we will write our own dynamic inventory script using the Python language, all this while following good practices of packaging our tools, using virtual environments and unit testing our code.

## Enter the world of dynamic inventory

Ansible documentation explains [several ways to generate dynamic inventories](https://docs.ansible.com/ansible/latest/user_guide/intro_dynamic_inventory.html); I decided to try writing a simple Python script that is a front-end to the Nmap command.

Why you should write your own dynamic script?
* You have legacy code written in other language than Python and you want to re-use that logic to generate that host list (Java, Perl, Bash, Ruby, Go. Sky is the limit)
* You or your team are proficient on a specific language (say Bash, Ruby) and the Ansible dynamic script is flexible enough that you can write your plugin in the language of your choice.

To illustrate this, we will write a script that fetches hosts using Nmap.

## Code foundation, running Nmap command line interface and parsing the results in XML format

The foundation is a wrapper around the Nmap command goes like this:

1. NmapRunner executes the Nmap with the desired flags and captures the XML output
2. OutputParser parses the XML returns just the ip addresses we need
3. NMapRunner implements an [iterator](https://wiki.python.org/moin/Iterator), so we can go and process each address any way we see it fit.

Here is the code:

```python
import os
import shlex
import shutil
import subprocess
from typing import List, Dict
from xml.etree import ElementTree


class OutputParser:
    def __init__(self, xml: str):
        self.xml = xml

    def get_addresses(self) -> List[Dict[str, str]]:
        """
        Several things need to happen for an address to be included:
        1. Host is up
        2. Port is TCP 22
        3. Port status is open
        Otherwise the iterator will not be filled
        :return:
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
            raise ValueError(f"Nmap is missing!")
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

For example, you could use the NmapRunner like this:

```python
import pprint
def test_iter():
    for hosts_data in NmapRunner("192.168.1.0/24"):
        pprint.print(hosts_data)
```

Believe it or not, this was the hardest part of writing the inventory script. Next part will require writing a script that follows Ansible contracts for dynamic inventory scripts.

## Writing an inventory script

Ansible documentation [is very clear](https://docs.ansible.com/ansible/latest/dev_guide/developing_inventory.html#inventory-script-conventions) about the only 2 requirements we need for our script.
1. Must support --list and --host <hostname> excluding flag
2. Must return [JSON](https://www.json.org/json-en.html) in a format that Ansible can understand
3. Other flags can be added but will not be used by Ansible

But wait a second. There is nothing in there that says than Ansible will provide the network to scan for hosts, so __how do we inject that?__

Simple!, our script will be able to read a [YAML](https://yaml.org/) configuration file from a predefined location, like "/home/josevnz/.ansible/plugins/cliconf/nmap_plugin.yaml" with the following:

```yaml
# Sample configuration file. Suspiciously similar to the official Nmap plugin configuration file
---
plugin: nmap_plugin
address: 192.168.1.0/24
```

The class that reads the configuration YAML file is quite simple:
```python
"""
Using a configuration file in YAML format, so it can be reused by the plugin.
Init file with ConfigParser is more convenient, trying to keep Ansible happy :wink:
"""
import os
from yaml import safe_load

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

def load_config(config_file: str = os.path.expanduser("~/.ansible/plugins/cliconf/nmap_inventory.cfg")):
    """
    Where to copy the configuration file:
    ```shell
    [josevnz@dmaf5 EnableSysadmin]$ ansible-config dump |grep DEFAULT_CLICONF_PLUGIN_PATH
    DEFAULT_CLICONF_PLUGIN_PATH(default) = ['/home/josevnz/.ansible/plugins/cliconf', '/usr/share/ansible/plugins/cliconf']
    ```
    :param config_file:
    :return:
    """
    with open(config_file, 'r') as stream:
        data = safe_load(stream)
        return data
```

Very good, let's see dynamic inventory script code now:

```python
#!/usr/bin/env python
"""
# nmap_inventory.py - Generates an Ansible dynamic inventory using NMAP
# Author
Jose Vicente Nunez Zuleta (kodegeek.com@protonmail.com)
"""
import json
import os.path
import argparse
from configparser import ConfigParser, MissingSectionHeaderError

from inventories.nmap import NmapRunner

def load_config() -> ConfigParser:
    cp = ConfigParser()
    try:
        config_file = os.path.expanduser("~/.config/nmap_inventory.cfg")
        cp.read(config_file)
        if not cp.has_option('DEFAULT', 'Addresses'):
            raise ValueError("Missing configuration option: DEFAULT -> Addresses")
    except MissingSectionHeaderError as mhe:
        raise ValueError("Invalid or missing configuration file:", mhe)
    return cp


def get_empty_vars():
    return json.dumps({})


def get_list(search_address: str, pretty=False) -> str:
    """
    All group is always returned
    Ungrouped at least contains all the names found
    IP addresses are added as vars in the __meta tag, for efficiency as mentioned in the Ansible documentation.
    Note than we can add logic here to put machines in custom groups, will keep it simple for now.
    :param search_address: Results of the scan with NMap
    :param pretty: Indentation
    :return: JSON string
    """
    found_data = list(NmapRunner(search_address))
    hostvars = {}
    ungrouped = []
    for host_data in found_data:
        for name, address in host_data.items():
            if name not in ungrouped:
                ungrouped.append(name)
            if name not in hostvars:
                hostvars[name] = {'ip': []}
            hostvars[name]['ip'].append(address)
    data = {
        '_meta': {
          'hostvars': hostvars
        },
        'all': {
            'children': [
                'ungrouped'
            ]
        },
        'ungrouped': {
            'hosts': ungrouped
        }
    }
    return json.dumps(data, indent=pretty)

if __name__ == '__main__':

    arg_parser = argparse.ArgumentParser(
        description=__doc__,
        prog=__file__
    )
    arg_parser.add_argument(
        '--pretty',
        action='store_true',
        default=False,
        help="Pretty print JSON"
    )
    mandatory_options = arg_parser.add_mutually_exclusive_group()
    mandatory_options.add_argument(
        '--list',
        action='store',
        nargs="*",
        default="dummy",
        help="Show JSON of all managed hosts"
    )
    mandatory_options.add_argument(
        '--host',
        action='store',
        help="Display vars related to the host"
    )

    try:
        config = load_config()
        addresses = config.get('DEFAULT', 'Addresses')

        args = arg_parser.parse_args()
        if args.host:
            print(get_empty_vars())
        elif len(args.list) >= 0:
            print(get_list(addresses, args.pretty))
        else:
            raise ValueError("Expecting either --host $HOSTNAME or --list")

    except ValueError:
        raise
```

You probably noticed a few things:
1. Most of the code on this script is dedicated to handling arguments and loading configuration, besides presenting the JSON
2. You could add grouping logic into get_list. For now, I'm populating the 2 required default groups.

It is time to kick the tires. Install the code first:

```shell
git clone git@github.com:josevnz/ExtendingAnsibleWithPython.git
cd ExtendingAnsibleWithPython/Inventory
python3 -m venv ~/virtualenv/ExtendingAnsibleWithPythonInventory
. ~/virtualenv/ExtendingAnsibleWithPythonInventory/bin/activate
pip install wheel
pip install --upgrade pip
pip install build
python setup.py bdist_wheel
pip install dist/*
```

The virtual environment should be active now, let's see if we get an empty host information (put the name of a machine in your network):

```shell
(ExtendingAnsibleWithPythonInventory) [josevnz@dmaf5 Inventories]$ ansible-inventory --inventory scripts/nmap_inventory.py --host raspberrypi
{}
```

Good, empty JSON expected as we did not implement the ```--host $HOSTNAME method```. What about ```--list```?:

```shell
(ExtendingAnsibleWithPythonInventory) [josevnz@dmaf5 Inventories]$ ansible-inventory --inventory scripts/nmap_inventory.py --list
{
    "_meta": {
        "hostvars": {
            "dmaf5.home": {
                "ip": [
                    "192.168.1.26",
                    "192.168.1.25"
                ]
            },
            "macmini2": {
                "ip": [
                    "192.168.1.16"
                ]
            },
            "raspberrypi": {
                "ip": [
                    "192.168.1.11"
                ]
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

Finally, let's try our new inventory with the ping module:

```shell
(ExtendingAnsibleWithPythonInventory) [josevnz@dmaf5 Inventories]$ ansible --inventory scripts/nmap_inventory.py --user josevnz -m ping all
dmaf5.home | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
raspberrypi | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
macmini2 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

## What is next?

_We cover a lot of material_, here is a quick summary of what we learned:

* Wrote utility classes to call Nmap and parse the scan resulls
* Reused those classes inside a script complies with the Ansible inventory contract, so it can be used to get create a dynamic inventory. 
 
This is probably the most flexible in terms of coding as the requirements are pretty loose, and can be done any language.

But is it the right way? On the last part of this article I'll show you why it could be better to write an Ansible plugin as opposed to use an inventory script.

Remember, you [can download the code](https://github.com/josevnz/ExtendingAnsibleWithPython) and experiment!. The best way to learn is by doing and making mistakes.



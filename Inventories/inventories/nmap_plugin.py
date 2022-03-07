"""
Module around the NmapWorker class.
No need to use 'from ansible.module_utils.common.text.converters import to_text' as this plugin doesn't
support Jinja2 expressions.

Where you can install this module?

```shell
[josevnz@dmaf5 ExtendingAnsibleWithPython]$ ansible-config dump|grep DEFAULT_INVENTORY_PLUGIN_PATH
DEFAULT_INVENTORY_PLUGIN_PATH(default) = ['/home/josevnz/.ansible/plugins/inventory', '/usr/share/ansible/plugins/inventory']
```

"""
import os.path
from subprocess import CalledProcessError
import os
import shlex
import shutil
import subprocess
from typing import List, Dict
from xml.etree import ElementTree
from ansible.errors import AnsibleParserError
from ansible.plugins.inventory import BaseInventoryPlugin, Cacheable, Constructable

DOCUMENTATION = r'''
    name: nmap_plugin
    plugin_type: inventory
    short_description: Returns Ansible inventory from Nmap scan
    description: Returns Ansible inventory from Nmap scan
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

    def verify_file(self, path: str):
        if super(InventoryModule, self).verify_file(path):
            return path.endswith('nmap_plugin_inventory.yaml') or path.endswith('nmap_plugin.yaml')
        return False

    def parse(self, inventory, loader, path: str, cache: bool=True):

        super(InventoryModule, self).parse(inventory, loader, path, cache=cache)
        self._read_config_data(path)  # This also loads the cache
        # root_group_name = self.inventory.add_group('root-group')

        if not self.has_option('address'):
            raise AnsibleParserError(f'Option "address" is required on the configuration file: {path}')
        try:
            hosts_data = list(NmapRunner(self.get_option('address')))
            if not hosts_data:
                raise AnsibleParserError(f"Unable to get data for Nmap scan!")
            for host_data in hosts_data:
                for name, address in host_data.items():
                    self.inventory.add_host(name)
                    self.inventory.set_variable(name, 'ip', address)
        except CalledProcessError as cpe:
            raise AnsibleParserError(f"There was an error while calling Nmap", cpe)


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
        :return: List of dictionaries
        It is possible to have multiple PTR records assigned to different IP addresses
        [josevnz@dmaf5 EnableSysadmin]$ nslookup dmaf5.home
        Server:		127.0.0.53
        Address:	127.0.0.53#53
        Non-authoritative answer:
        Name:	dmaf5.home
        Address: 192.168.1.26
        Name:	dmaf5.home
        Address: 192.168.1.25
        Name:	dmaf5.home
        Address: fd22:4e39:e630:1:1937:89d4:5cbc:7a8d
        Name:	dmaf5.home
        Address: fd22:4e39:e630:1:e711:3539:b731:10dd
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

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

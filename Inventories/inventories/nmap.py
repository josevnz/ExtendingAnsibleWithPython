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

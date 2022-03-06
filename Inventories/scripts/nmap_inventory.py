#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
# nmap_inventory.py - Generates an Ansible dynamic inventory using NMAP
# Author
Jose Vicente Nunez Zuleta (kodegeek.com@protonmail.com)
"""
import json
import argparse

from inventories.nmap import NmapRunner
from inventories.config import load_config


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
        addresses = config['address']

        args = arg_parser.parse_args()
        if args.host:
            print(get_empty_vars())
        elif len(args.list) >= 0:
            print(get_list(addresses, args.pretty))
        else:
            raise ValueError("Expecting either --host $HOSTNAME or --list")

    except ValueError:
        raise

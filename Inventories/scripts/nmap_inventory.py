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

from Inventories.inventories.nmap import NmapRunner


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


def get_list(addresses: str):
    nr = NmapRunner(addresses)


if __name__ == '__main__':

    arg_parser = argparse.ArgumentParser(
        description=__doc__,
        prog=__file__
    )
    arg_parser.add_argument(
        '--debug',
        action='store_true',
        default=False,
        help="Enable debug mode"
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
            print(get_list(addresses))
        else:
            raise ValueError("Expecting either --host $HOSTNAME or --list")

    except ValueError:
        raise

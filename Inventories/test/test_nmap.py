"""
Unit tests for Nmap host capture
"""
from pathlib import Path
from unittest import TestCase

from inventories.config import load_config
from inventories.nmap import OutputParser, NmapRunner

BASEDIR = Path(__file__).parent


class TestOutputParser(TestCase):

    def test_get_addresses(self):
        with open(BASEDIR.joinpath("home_scan.xml"), 'rt') as home_scan_file:
            out_p = OutputParser(home_scan_file.read())
            self.assertIsNotNone(out_p)
            hosts_data = out_p.get_addresses()
            self.assertIsNotNone(hosts_data)
            for host_data in hosts_data:
                for name, address in host_data.items():
                    self.assertIsNotNone(name)
                    self.assertIn(address, ['192.168.1.11', '192.168.1.16', '192.168.1.25', '192.168.1.26'])
                    print(address)


class TestNmapRunner(TestCase):
    """
    This test will fail if you are not running SSH at localhost.
    """

    def test_iter(self):
        addresses = list(NmapRunner("127.0.01/32"))
        self.assertIsNotNone(addresses)
        self.assertTrue(len(addresses) > 0)
        for address in addresses:
            print(address)


class TestConfig(TestCase):

    def test_load_config(self):
        config = load_config(str(BASEDIR.joinpath('nmap_plugin_inventory.yaml')))
        self.assertIsNotNone(config)
        self.assertIn('plugin', config)
        self.assertIsNotNone(config['plugin'])
        self.assertIn('address', config)
        self.assertIsNotNone(config['address'])

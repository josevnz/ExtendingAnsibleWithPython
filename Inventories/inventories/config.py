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

import os.path

from ansible.plugins.inventory import BaseInventoryPlugin
from ansible.plugins.inventory.auto import InventoryModule
from ansible.module_utils.common.text.converters import to_text


class NmapInventoryModule(BaseInventoryPlugin, InventoryModule):
    NAME = 'nmap'

    def __init__(self):
        super(InventoryModule, self).__init__()

    def verify_file(self, path: str):
        if super(InventoryModule, self).verify_file(path):
            file_name, extension = os.path.splitext(path)
            if extension and extension in ['init', 'config', 'cfg']:
                return True
            elif extension and extension in ['yml', 'yaml']:
                return True
        return False

    def parse(self, inventory, loader, path, cache=True):
       pass
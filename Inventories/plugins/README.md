# Ansible nmap_plugin

This plugin has the same functionality as the nmap_inventory.py script from this repository, but it uses the [inventory plugin](https://docs.ansible.com/ansible/latest/plugins/inventory.html)
to get advantage of extra services like caching.

## Installing the plugin

You can copy the plugin or make a symbolic link

```shell
/bin/mkdir --verbose --parents $HOME/.ansible/plugins/inventory/
# /bin/ln --symbolic --verbose --force $HOME/EnableSysadmin/ExtendingAnsibleWithPython/Inventories/plugins/inventory/nmap_plugin.py $HOME/.ansible/plugins/inventory/nmap_plugin.py
/bin/cp --verbose $HOME/EnableSysadmin/ExtendingAnsibleWithPython/Inventories/plugins/inventory/nmap_plugin.py $HOME/.ansible/plugins/inventory/nmap_plugin.py
```

Confirm than Ansible can locate the nmap_plugin plugin and parse the description

```shell
[josevnz@dmaf5 ExtendingAnsibleWithPython]$ ansible-doc -t inventory -l|grep nmap
nmap                Uses nmap to find hosts to target                                                                                                                                                  
nmap_plugin         Returns a dynamic host inventory from Nmap scan                
```

The plugin is used on an inventory ([nmap_plugin_inventory.yaml](../test/nmap_plugin_inventory.yaml)) file like this one:

```shell
# This is the configuration file for my version of the Nmap plugin, nmap_plugin
# Showing required parameters below
---
plugin: nmap_plugin
address: 192.168.1.0/24
```

## Testing it

```shell
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

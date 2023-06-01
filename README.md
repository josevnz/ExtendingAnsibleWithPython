# ExtendingAnsibleWithPython

![](mazinger-z.png)

Tutorial how to extend Ansible with Python

This repository is composed of several modules. They are small enough right now, so I plan to keep this in a single place 
instead of splitting in submodules.

# Topics
## [Inventories](Inventories/README.md)

How to manage dynamic inventories in Ansible

### Installation

```shell
git clone git@github.com:josevnz/ExtendingAnsibleWithPython.git
cd ExtendingAnsibleWithPython.git/Inventory
python3 -m venv ~/virtualenv/ExtendingAnsibleWithPythonInventory
. ~/virtualenv/ExtendingAnsibleWithPythonInventory/bin/activate
```

#### Developer installation
```shell
. ~/virtualenv/ExtendingAnsibleWithPythonInventory/bin/activate
pip install wheel
pip install --upgrade pip
pip install build
python setup.py develop
```

Running unit tests
```shell
(ExtendingAnsibleWithPythonInventory) [josevnz@dmaf5 Inventories]$ python -m unittest test/test_nmap.py 
.{'127.0.01': '127.0.0.1'}
.192.168.1.11
192.168.1.16
192.168.1.25
192.168.1.26
.
----------------------------------------------------------------------
Ran 3 tests in 0.070s

OK
```

#### User installation
```shell
. ~/virtualenv/ExtendingAnsibleWithPythonInventory/bin/activate
python setup.py bdist_wheel
pip install dist/ansible_nmap_inventories-0.0.1-py3-none-any.whl
```

Then please read the [Inventories tutorial](Inventories/README.md) to see what is available.


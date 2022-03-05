# Extending Ansible Inventories With Python

If you ever used Ansible, you know than one of its fundamental pieces is the [inventory](https://docs.ansible.com/ansible/latest/user_guide/intro_inventory.html); the inventory is nothing more than a list of machines and possibly variables where you can run your ansible playbooks.

An inventory file can be written in YAML, JSON or Windows INI format and can describe groups of machines as follows:

```yaml
---
all:
  children:
    servers:
      hosts:
        macmini2:
        raspberrypi:
      vars:
        description: Linux servers for the Nunez family
    desktops:
      hosts:
        dmaf5:
        mac-pro-1-1:
      vars:
        description: Desktops for the Nunez family
```

And you can confirm than it has the right structure too; for example filter only the machines that belong to the 'desktops' pattern:

```shell
[josevnz@dmaf5 ExtendingAnsibleWithPython]$ ansible-inventory --yaml --inventory /home/josevnz/EnableSysadmin/BashHere/hosts.yaml --graph desktops
@desktops:
  |--dmaf5
  |--mac-pro-1-1
```

Having a static YAML inventory may not be entirely practical for the following reasons:

1. You host inventory is really large. Admit it, you have better things to do than to edit YAML files, right?
2. Your inventory is on a format that is not compatible with Ansible YAML; It may be on a database, a plain text file
3. The servers that are part of your inventory is, well really dynamic; You create machines on your private cloud as you need them and their IP address change all the time, or you have a home network with lots of roaming devices (tables, phones). You want o maintain that by hand?

## What are you going to learn on this article

There are many ways to manage your inventories in Ansible, will cover a few alternatives here:

* Converting inventories from legacy formats into Ansible
* Dynamic inventories with plugins, specifically NMAP
* Writing our own inventory script to generate inventories dynamically
* Writing an Ansible plugin

All this while following good practices of packaging our tools, using virtual environments and unit testing our code.

## Don't repeat yourself: Check first if someone wrote it for you!

And chances are they did. You can quickly see if someone wrote a plugin that can handle inventory from a different source like this:

```shell
ansible-doc -t inventory -l
```

For example:

```shell
[josevnz@dmaf5 ExtendingAnsibleWithPython]$ ansible-doc -t inventory -l
advanced_host_list  Parses a 'host list' with ranges                                                                                                                                                                     
auto                Loads and executes an inventory plugin specified in a YAML config                                                                                                                                    
aws_ec2             EC2 inventory source                                                                                                                                                                                 
aws_rds             rds instance source                                                                                                                                                                                  
azure_rm            Azure Resource Manager inventory plugin                                                                                                                                                              
cloudscale          cloudscale.ch inventory source                                                                                                                                                                       
constructed         Uses Jinja2 to construct vars and groups based on existing inventory                                                                                                                                 
docker_machine      Docker Machine inventory source                                                                                                                                                                      
docker_swarm        Ansible dynamic inventory plugin for Docker swarm nodes                                                                                                                                              
foreman             foreman inventory source                                                                                                                                                                             
gcp_compute         Google Cloud Compute Engine inventory source                                                                                                                                                         
generator           Uses Jinja2 to construct hosts and groups from patterns                                                                                                                                              
gitlab_runners      Ansible dynamic inventory plugin for GitLab runners                                                                                                                                                  
hcloud              Ansible dynamic inventory plugin for the Hetzner Cloud                                                                                                                                               
host_list           Parses a 'host list' string                                                                                                                                                                          
ini                 Uses an Ansible INI file as inventory source                                                                                                                                                         
k8s                 Kubernetes (K8s) inventory source                                                                                                                                                                    
kubevirt            KubeVirt inventory source                                                                                                                                                                            
linode              Ansible dynamic inventory plugin for Linode                                                                                                                                                          
netbox              NetBox inventory source                                                                                                                                                                              
nmap                Uses nmap to find hosts to target                                                                                                                                                                    
online              Online inventory source                                                                                                                                                                              
openshift           OpenShift inventory source                                                                                                                                                                           
openstack           OpenStack inventory source                                                                                                                                                                           
scaleway            Scaleway inventory source                                                                                                                                                                            
script              Executes an inventory script that returns JSON                                                                                                                                                       
toml                Uses a specific TOML file as an inventory source                                                                                                                                                     
tower               Ansible dynamic inventory plugin for Ansible Tower                                                                                                                                                   
virtualbox          virtualbox inventory source                                                                                                                                                                          
vmware_vm_inventory VMware Guest inventory source                                                                                                                                                                        
vultr               Vultr inventory source                                                                                                                                                                               
yaml                Uses a specific YAML file as an inventory source                          
```

### Host_list plugin

It is the simples one. You pass a list of machines or IP addresses, and you're good to go.
Let's try it with the ping module, and the remote user 'josevnz':

```shell
[josevnz@dmaf5 ExtendingAnsibleWithPython]$ cat /etc/hosts
127.0.0.1   localhost localhost.localdomain localhost4 localhost4.localdomain4
::1         localhost localhost.localdomain localhost6 localhost6.localdomain6
192.168.1.17 mac-pro-1-1
192.168.1.16 macmini2
192.168.1.11 raspberrypi

[josevnz@dmaf5 ExtendingAnsibleWithPython]$ cat /etc/hosts| /bin/cut -f1 -d' '|/bin/grep -P '^[a-z1]'
127.0.0.1
192.168.1.17
192.168.1.16
192.168.1.11

[josevnz@dmaf5 ExtendingAnsibleWithPython]$ ansible -u josevnz -i $(/bin/cat /etc/hosts| /bin/cut -f1 -d' '|/bin/grep -P '^[a-z1]'|/bin/xargs|/bin/sed 's# #,#g') -m ping all
127.0.0.1 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
192.168.1.11 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
192.168.1.16 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
192.168.1.17 | SUCCESS => {
    "changed": false,
    "ping": "pong"
}
```

No surprises here. But as you can see, this is not very convenient as we had to do a little but of Bash scripting to generate the hostlist; also the inventory is hardcoded.

Let's move on to a more interesting plug-ing, using nmap

### nmap plugin

The [Nmap](https://docs.ansible.com/ansible/2.9/plugins/inventory/nmap.html) plugin allows you to use the well known network scanner to build your inventory list.

But first let's see how this works, by running nmap by hand

#### Crash course on Nmap
As a refresher, you can use [Nmap](https://nmap.org/) on the command line to get a very good idea of what machines and services are on your network:

```shell
[josevnz@dmaf5 ExtendingAnsibleWithPython]$ sudo nmap -v -n -p- -sT -sV -O --osscan-limit --max-os-tries 1 -oX $HOME/home_scan.xml 192.168.1.0/24
Starting Nmap 7.80 ( https://nmap.org ) at 2022-03-05 10:29 EST
NSE: Loaded 45 scripts for scanning.
Initiating ARP Ping Scan at 10:29
Scanning 254 hosts [1 port/host]
Completed ARP Ping Scan at 10:29, 5.10s elapsed (254 total hosts)
Nmap scan report for 192.168.1.0 [host down]
Nmap scan report for 192.168.1.2 [host down]
Initiating Connect Scan at 10:29
Scanning 4 hosts [65535 ports/host]
Discovered open port 443/tcp on 192.168.1.1
Discovered open port 8080/tcp on 192.168.1.1
Discovered open port 445/tcp on 192.168.1.1
Discovered open port 139/tcp on 192.168.1.1
Discovered open port 80/tcp on 192.168.1.1
Discovered open port 80/tcp on 192.168.1.4
Discovered open port 35387/tcp on 192.168.1.4
```

Keep in mind than the scan above is a time-consuming operation; You are checking every port and every possible host on your network, so this may take minutes _or even hours if you don't tune up your query_.

With that in mind, let's keep this useful links around:

* [NMAP Port Scanning Techniques](https://nmap.org/book/man-port-scanning-techniques.html)
* [NMAP Timing and Performance](https://nmap.org/book/man-performance.html).
* [NMAP Timing Templates (-T)](https://nmap.org/book/performance-timing-templates.html)

And for our inventory, we really care about machines where Ansible can SSH and perform operations. Limiting the port number to TCP 22 *will speed up considerable* our scanning:

```shell
# '-n': 'Never do DNS resolution',
# '-sS': 'TCP SYN scan, recommended',
# '-p-': 'All ports. Use -p22 to limit scan to port 22',
# '-sV': 'Probe open ports to determine service/version info',
# '-T4': 'Aggressive timing template',
# '-PE': 'Enable this echo request behavior. Good for internal networks',
# '--version-intensity 1': 'Set version scan intensity. Default is 7',
# '--disable-arp-ping': 'No ARP or ND Ping',
# '--max-hostgroup 100': 'Hostgroup (batch of hosts scanned concurrently) size',
# '--min-parallelism 20': 'Number of probes that may be outstanding for a host group',
# '--osscan-limit': 'Limit OS detection to promising targets',
# '--max-os-tries 1': 'Maximum number of OS detection tries against a target',
# '-oX -': 'Send XML output to STDOUT, avoid creating a temp file'
[josevnz@dmaf5 ExtendingAnsibleWithPython]$ nmap -v -n -p22 -sT -sV  --osscan-limit --max-os-tries 1 -oX $HOME/home_scan.xml 192.168.1.0/24
Starting Nmap 7.80 ( https://nmap.org ) at 2022-03-05 10:51 EST
NSE: Loaded 45 scripts for scanning.
Initiating Ping Scan at 10:51
Scanning 256 hosts [2 ports/host]
Completed Ping Scan at 10:51, 2.31s elapsed (256 total hosts)
Nmap scan report for 192.168.1.0 [host down]
Nmap scan report for 192.168.1.2 [host down]
Nmap scan report for 192.168.1.5 [host down]
Nmap scan report for 192.168.1.7 [host down]
...
Completed NSE at 10:51, 0.00s elapsed
Nmap scan report for 192.168.1.1
Host is up (0.0024s latency).

PORT   STATE  SERVICE VERSION
22/tcp closed ssh

Nmap scan report for 192.168.1.3
Host is up (0.070s latency).
...
Nmap scan report for 192.168.1.11
Host is up (0.00036s latency).
PORT   STATE SERVICE VERSION
22/tcp open  ssh     OpenSSH 8.2p1 Ubuntu 4ubuntu0.4 (Ubuntu Linux; protocol 2.0)
Service Info: OS: Linux; CPE: cpe:/o:linux:linux_kernel
...
Read data files from: /usr/bin/../share/nmap
Service detection performed. Please report any incorrect results at https://nmap.org/submit/ .
Nmap done: 256 IP addresses (10 hosts up) scanned in 2.73 seconds
```

There are [many ways to extend Nmap](https://github.com/josevnz/home_nmap/blob/main/tutorial/README.md) to give you the data that you want; We will use '[nmap_scan_rpt.py](https://github.com/josevnz/home_nmap/blob/main/scripts/nmap_scan_rpt.py)' to show the results of the scan in a nice table, with links to NIST advisories if versions of your services are vulnerable:

```shell
git clone git@github.com:josevnz/home_nmap.git $HOME/home_nmap.git
pushd home_nmap/
python3 -m venv $HOME/virtualenv/home_nmap/
. ~/virtualenv/home_nmap/bin/activate
nmap_scan_rpt.py $HOME/home_scan.xml
```

![](nmap_scan_rpt.py.png)

Feel free to play with the code, you can also run Nmap as a web service, but for now let's move into Ansible with Nmap

### The Ansible nmap plugin

Now we are ready to explore the [Ansible Nmap plugin](https://docs.ansible.com/ansible/latest/collections/community/general/nmap_inventory.html);

```yaml
# We do not want to do a port scan, only get the list of hosts dynamically
---
plugin: nmap
address: 192.168.1.0/24
strict: False
ipv4: yes
ports: no
```

```shell
[josevnz@dmaf5 EnableSysadmin]$ ansible-inventory -i ExtendingAnsibleWithPython/Inventories/home_nmap_inventory.yaml --lis
```

```json
{
    "_meta": {
        "hostvars": {

            "android-1c5660ab7065af69.home": {
                "ip": "192.168.1.4",
                "ports": []
            },
            "dmaf5.home": {
                "ip": "192.168.1.26",
                "ports": []
            },
    },
    "all": {
        "children": [
            "ungrouped"
        ]
    },
    "ungrouped": {
        "hosts": [
            "android-1c5660ab7065af69.home",
            "dmaf5.home",
            "macmini2",
            "new-host-2.home",
            "new-host-6.home",
            "raspberrypi",
        ]
    }
}
```
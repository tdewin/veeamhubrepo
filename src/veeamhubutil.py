#
# non dialog functions

import netifaces
import psutil
import pystemd
import subprocess
import re

# creates a list of all ipv4 address
def realnics():
    return [i for i in netifaces.interfaces() if not i == 'lo' ]

def myips():
    ipaddr = []
    for nif in realnics():
        ifaddr = netifaces.ifaddresses(nif)
        if netifaces.AF_INET in ifaddr:
            addrdetails = ifaddr[netifaces.AF_INET]
            for addr in addrdetails:
                ip = addr['addr']
                if ip != '127.0.0.1':
                    ipaddr.append(ip)
    return ipaddr


def firstipwithnet(networkinterface):
    ipwithnet = "169.254.128.128/24"

    if netifaces.AF_INET in netifaces.ifaddresses(networkinterface):
        addrs = netifaces.ifaddresses(networkinterface)[netifaces.AF_INET]
        if len(addrs) > 0:
            nm = ipaddress.IPv4Network("0.0.0.0/"+addrs[0]['netmask'])
            ipwithnet = addrs[0]['addr'] + "/" + str(nm.prefixlen)

    return ipwithnet

def firstgw(networkinterface):
    gw = "169.254.128.1"

    gws = netifaces.gateways()
    if netifaces.AF_INET in gws:
        fgw = [g for g in gws[netifaces.AF_INET] if g[1] == networkinterface ]
        if len(fgw) > 0:
            gw = fgw[0][0]
    
    return gw


def veeamrunning():
    procs = [p for p in psutil.process_iter(['pid', 'name', 'username']) if "veeamtransport" in p.name()]
    return len(procs) > 0

def veeamreposshcheck(username):
    procs = [p for p in psutil.process_iter(['pid', 'name', 'username']) if username in p.username() and "ssh" in p.name()]
    return len(procs) > 0

def getsshservice():
    ssh = pystemd.systemd1.Unit(b'ssh.service')
    ssh.load()
    return ssh

def is_ssh_on():
    s = getsshservice()
    return s.Unit.ActiveState == b'active'

def ufw_is_inactive():
	ufw = subprocess.run(["ufw", "status"], capture_output=True)
	if ufw.returncode == 0:
		return "inactive" in str(ufw.stdout,"utf-8")
	else:
		raise Exception("ufw feedback not as expected {}".format(ufw.stdout))

def ufw_activate():
	ufw = subprocess.run(["ufw","--force","enable"], capture_output=True)
	if ufw.returncode != 0:
		raise Exception("ufw feedback not as expected {}".format(ufw.stdout))
	else:
		return ufw.stdout

def ufw_ssh(setstatus="deny"):
	ufw = subprocess.run(["ufw",setstatus,"ssh"], capture_output=True)
	if ufw.returncode != 0:
		raise Exception("ufw feedback not as expected {}".format(ufw.stdout))
	else:
		return ufw.stdout


def gettimeinfo():
    timeinfo = ["Could not fetch timeinfo"]
    time = ""
    date = ""
    zone = ""
    ntpactive = False
    pout = subprocess.run(["timedatectl","status"], capture_output=True) 
    if pout.returncode == 0:
        timeinfo = []
        for line in str(pout.stdout,'utf-8').split("\n"):
            line = line.strip()
            if line != "":
                tim = re.match("Local time: [A-Za-z]+ ([0-9]{4}-[0-9]{2}-[0-9]{2}) ([0-9]{2}:[0-9]{2}:[0-9]{2})",line)
                if tim:
                    time = tim.group(2)
                    date = tim.group(1)
                else:
                    zm = re.match("Time zone: ([A-Za-z/]+)",line)
                    if zm:
                        zone = zm.group(1)
                    else:
                        ntpm = re.match("NTP service: ([A-Za-z/]+)",line)
                        if ntpm:
                            ntpactive = ntpm.group(1) == "active"
                            
                timeinfo.append(line)

    return timeinfo,time,date,zone,ntpactive

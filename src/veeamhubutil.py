#
# non dialog functions

import netifaces
import psutil
import pystemd
import subprocess
import re
import json
import humanize
import os
import time
import sshcmd

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

# Ubuntu 22.10+ (incl. 24.04) socket-activates SSH: the listening unit is
# ssh.socket, and ssh.service only runs while a connection is open. So we drive
# the socket (falling back to the service) and treat either being active as "on".
_SSH_UNITS = (b'ssh.socket', b'ssh.service')

def _ssh_unit(name):
    u = pystemd.systemd1.Unit(name)
    u.load()
    return u

def is_ssh_on():
    for name in _SSH_UNITS:
        try:
            if _ssh_unit(name).Unit.ActiveState == b'active':
                return True
        except Exception:
            pass
    return False

# hardening disables both units, so remember the configured mode beforehand
_SSH_MODE_FILE = "/var/lib/veeamhubrepo/sshunit"

# Ubuntu disables socket activation by masking this generator; it is the only
# trace of service mode when neither unit is enabled (e.g. started by hand)
_SSH_GENERATOR = "/etc/systemd/system-generators/sshd-socket-generator"

def _ssh_mode_inputs():
    # (socket state, service state, generator masked) for sshcmd.start_units
    states = []
    for name in _SSH_UNITS:
        try:
            states.append(_ssh_unit(name).Unit.UnitFileState)
        except Exception:
            states.append(b'')
    states.append(os.path.realpath(_SSH_GENERATOR) == "/dev/null")
    return states

def _ssh_recorded_unit():
    try:
        with open(_SSH_MODE_FILE, 'rb') as f:
            return f.read().strip()
    except OSError:
        return None

def ssh_start():
    # start the unit matching the configured mode (socket vs service), so an
    # explicit service setup (custom Port/ListenAddress) is not bypassed by the
    # default socket on :22. returns True only if a unit is actually running.
    for name in sshcmd.start_units(_ssh_recorded_unit(), *_ssh_mode_inputs()):
        try:
            u = _ssh_unit(name)
            u.Unit.Start(b'replace')
        except Exception:
            continue
        # Start only queues a job: a unit can be accepted and still fail
        # (e.g. bad sshd_config), so wait until it settles before reporting.
        # ponytail: fixed 5s poll; a socket is active instantly, sshd within ~1s
        for _ in range(20):
            state = u.Unit.ActiveState
            if state == b'active':
                return True
            if state == b'failed':
                break
            time.sleep(0.25)
    return False

def ssh_stop():
    for name in _SSH_UNITS:
        try:
            u = _ssh_unit(name)
            if u.Unit.ActiveState == b'active':
                u.Unit.Stop(b'replace')
        except Exception:
            pass

def ssh_stop_and_disable():
    # stop, then persistently disable every SSH unit file present so SSH does
    # not come back on reboot (ssh.socket + ssh.service + sshd.service alias)
    units = sshcmd.start_units(None, *_ssh_mode_inputs())
    if len(units) == 1:
        # ponytail: only record a known mode; a second harden run keeps the first record
        os.makedirs(os.path.dirname(_SSH_MODE_FILE), exist_ok=True)
        with open(_SSH_MODE_FILE, 'wb') as f:
            f.write(units[0])
    ssh_stop()
    mgr = pystemd.systemd1.Manager()
    mgr.load()
    wanted = ("ssh.socket", "ssh.service", "sshd.service")
    for serv in mgr.Manager.ListUnitFiles():
        base = serv[0].split(b'/')[-1]
        if any(w == str(base, 'utf-8') for w in wanted):
            try:
                mgr.Manager.DisableUnitFiles([base], False)
            except Exception:
                pass

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

def packagetest(dpkgtest):
	code = 0
	pout = subprocess.run(["dpkg","-s",dpkgtest], capture_output=True)
	if pout.returncode != 0:
		code = -1
	else:
		for ln in str(pout.stdout,"utf-8").split("\n"):
			if re.match("Status: install ok installed",ln):
				code = 1
	return code

def removepackage(packagename):
    pout = subprocess.run(["apt-get","remove",packagename,"-y"], capture_output=True) 
    if pout.returncode != 0:
        raise Exception("Error removing {0}".format(str(pout.stderr,'utf-8')))



def installpackage(d,packagename):
    pout = subprocess.run(["apt-get","update","-y"], capture_output=True) 
    if pout.returncode != 0:
        raise Exception("Error updating {0}".format(str(pout.stderr,'utf-8')))
   
    pout = subprocess.run(["apt-get","install",packagename,"-y"], capture_output=True) 
    if pout.returncode != 0:
        raise Exception("Error updating {0}".format(str(pout.stderr,'utf-8')))


def usersexists(user):
    found = False
    with open("/etc/passwd", 'r') as outfile:
        allu = outfile.readlines()
        for u in allu:
            us = u.split(":")
            if us[0] == user:
                found = True

    return found

# Makes a list of candidate drives from lsblk
# Uses recursion to dig deeper
# Drive is candidate if it does not have child partitions / is not mounter / is not a CD
# In case of children, do the recursion
# I is kept to keep the logical order
#recursive lsblk()
class BlkPathSize:
    Path = ""
    Size = 0

    def MenuEntry(self):
        return "{} {}".format(self.Path,humanize.filesize.naturalsize(self.Size))

    def __init__(self,jsonblock):
        self.Path = jsonblock["path"]
        self.Size = jsonblock["size"]

def rlsblk(blkdevices,blklist):
    for device in blkdevices:
        if not device["mountpoint"] and not "children" in device and not device["maj:min"].split(":")[0] == "11" :
            #11 -> /dev/sr[]
            blkdev = BlkPathSize(device)
            #if bigger then 1GB, cause everything smaller than 1GB really doesn't make sense
            if blkdev.Size > 1073741824:
                blklist.append(blkdev)

        elif "children" in device:
            rlsblk(device["children"],blklist)


def lsblk():
    lsout = subprocess.run(["lsblk", "--json","-b","-o","PATH,MAJ:MIN,NAME,MOUNTPOINT,SIZE"], capture_output=True)
    if lsout.returncode != 0:
        raise Exception("Unable to load partition schema"+lsout.stderr)

    jout = json.loads(lsout.stdout)
    blklist = []
    rlsblk(jout["blockdevices"],blklist)
    return blklist






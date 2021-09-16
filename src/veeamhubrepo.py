#! /usr/bin/env python3

# Veeamhub Repo
# VEEAMHUBREPOVERSION: 0.3.4

import locale
from pathlib import Path
import json
import re
import subprocess
import shutil
import netifaces
import pystemd
import psutil
import os
import glob
import sys
import time
import configparser
import datetime
import getpass
import yaml
import ipaddress

#local imports
#
import dialogwrappers
import veeamhubutil

# Start menu in home() function at the bottom

# Open a file for reading, by default trying to use config reader
# By default nano is set in the config file
# Nano is a bit nicer then the textbox functionality
def readfile(config,d,path):
    if "reader" in config and shutil.which(config["reader"][0]) is not None:
        procrun = config["reader"] + [path]
        subprocess.call(procrun)
    else:
        d.textbox(path,width=80,height=30)
# Open a file for wrting
def openfile(config,d,path):
    if "writer" in config and shutil.which(config["writer"][0]) is not None:
        procrun = config["writer"] + [path]
        subprocess.call(procrun)
    else:
        d.editbox(path,width=80,height=30)

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

def removepackage(d,packagename):
    pout = subprocess.run(["apt-get","remove",packagename,"-y"], capture_output=True) 
    if pout.returncode != 0:
        d.msgbox("Error removing {0}".format(str(pout.stderr,'utf-8')))
        error = True


def installpackage(d,packagename):
    error = False


    d.infobox("Checking repo's for definitions")
    pout = subprocess.run(["apt-get","update","-y"], capture_output=True) 
    if pout.returncode != 0:
        d.msgbox("Error updating {0}".format(str(pout.stderr,'utf-8')))
        error = True
   
    if not error:
        d.infobox("Installing {}".format(packagename))
        pout = subprocess.run(["apt-get","install",packagename,"-y"], capture_output=True) 
        if pout.returncode != 0:
            d.msgbox("Error updating {0}".format(str(pout.stderr,'utf-8')))
            error = True
    
    return error


# Menu 1 Create User
# Check if the user exists by parsing /etc/passwd
def usersexists(user):
    found = False
    with open("/etc/passwd", 'r') as outfile:
        allu = outfile.readlines()
        for u in allu:
            us = u.split(":")
            if us[0] == user:
                found = True

    return found

# the repouser function itself
def setrepouser(config,d):
    code,user = d.inputbox("Confirm your user",init=config["repouser"])
    if code == d.OK:
        if not usersexists(user):
            code = d.yesno("User {0} does not exists, do you want to create it?".format(user))
            if code == d.OK:
                pout = subprocess.run(["useradd","-m",user], capture_output=True) 
                if pout.returncode != 0:
                    d.msgbox("Error creating user {0}".format(str(pout.stderr,'utf-8')))
                    return
                else:
                    code,pwd = d.passwordbox("Enter password for user",insecure=True)
                    pout = subprocess.run(["chpasswd"],input="{}:{}".format(user,pwd).encode('utf-8'),capture_output=True)
                    if pout.returncode != 0:
                        d.msgbox("Error setting passwd {0}".format(str(pout.stderr,'utf-8')))
                        return
                    else:
                        d.msgbox("User created")
        config["repouser"] = user

# Menu 2 Format drive
# Makes a list of candidate drives from lsblk
# Uses recursion to dig deeper
# Drive is candidate if it does not have child partitions / is not mounter / is not a CD 
# In case of children, do the recursion
# I is kept to keep the logical order
def rlsblk(devices,choices,shadow,i):
    for device in devices:
        if not device["mountpoint"] and not "children" in device and not device["maj:min"].split(":")[0] == "11" :
            choices.append((str(i),"{} {}".format(device["path"],device["size"])))
            shadow[i] = device["path"]
            i=i+1
        elif "children" in device:
                i = rlsblk(device["children"],choices,shadow,i)
    return i

# the format function itself
def formatdrive(config,d):
    choices = [("1","Manually define disk")]
    shadow = {1:"/dev/"}
    i = 2

    repoadded = ""

    #lsblk --json -o PATH,MAJ:MIN,NAME,MOUNTPOINT,SIZE
    #output nice json we can parse and includes lvm volumes and disk size
    #proc part only contains phys devices

    trypart = True

    #if lsblk is available, use it, otherwise read /proc/partitions which has less info
    if shutil.which("lsblk") is not None:
        lsout = subprocess.run(["lsblk", "--json", "-o","PATH,MAJ:MIN,NAME,MOUNTPOINT,SIZE"], capture_output=True)
        if lsout.returncode == 0:
            jout = json.loads(lsout.stdout)
            i = rlsblk(jout["blockdevices"],choices,shadow,i)
            trypart = False

    if trypart:
        with open('/proc/partitions','r') as outfile:
            parts = outfile.readlines()
            for part in parts:
                partsplit = re.split("\s+",part.strip())
                if partsplit[0] == "8":
                    #8       16   52428800 sdb
                    choices.append((str(i),"/dev/{}".format(partsplit[3])))
                    shadow[i] = "/dev/{0}".format(partsplit[3])
                    i=i+1
     
    code, tag = d.menu("Select partition to format", choices=choices)
    if code == d.OK:
        code,part = d.inputbox("Confirm selected partition", init=shadow[int(tag)])
        if code == d.OK:
            code = d.yesno(f"Are you sure you want to format {part}?")
            if code == d.OK:
                #trying to suggest to make a primary partition on a complete disk
                if re.match("/dev/.d[a-z]{1,2}$", part):
                    code = d.yesno(f"{part} contains no partitions. Do you want to partition it?")
                    if code == d.OK:
                        if shutil.which("parted") is not None:
                            try:
                                pout = subprocess.run([
                                    "parted","-s",part,
                                    "mklabel","gpt",
                                    "mkpart", "primary", "0%", "100%"
                                    ], capture_output=True)
                                part = f"{part}1"
                            except subprocess.CalledProcessError as e:
                                d.msgbox(
                                    f"Error partitioning {part}, code {e.returncode}:"
                                    f"{e.stderr}".encode("utf-8")
                                )
                                return 1, repoadded
                        else:
                            d.msgbox("Parted not found, stopping")
                            return 1,repoadded

                d.msgbox(f"Now formating {part} with XFS")
 
                time.sleep(1)
                pout = subprocess.run(["mkfs.xfs","-b","size=4096","-m","reflink=1,crc=1",part], capture_output=True)
                if pout.returncode != 0:
                    force = d.yesno("mkfs.xfs failed, do you want me to try to force it?\n{0}".format(str(pout.stderr,'utf-8')),width=80)
                    if force == d.OK:
                        pout = subprocess.run(["mkfs.xfs","-f","-b","size=4096","-m","reflink=1,crc=1",part], capture_output=True)


                if pout.returncode != 0:
                   d.msgbox("Error formatting {0}".format(str(pout.stderr,'utf-8')))
                else:
                    choices = [
                                ("1", "One digit (repo1)"),
                                ("2", "Two digits (repo01)"),
                                ("3", "Three digits (repo001)"),
                              ]
                    code, tag = d.menu("Select leading zeros in disk name", choices=choices)
                    
                    mountpoint = ""
                    
                    found = False
                    i = 1
                    high = (10**int(tag))-1
                    zeros = len(str(high))

                    while not found and i < high:
                        test_path = Path("/backups/disk-{}".format(str(i).zfill(zeros)))
                        if test_path.exists():
                            i = i+1
                        else:
                            mountpoint = test_path
                            found = True
                    
                    code, mountpoint = d.inputbox("Where do you want to mount the disk?",init=str(mountpoint))
                    if code == d.OK:
                        p = Path(mountpoint)
                        if p.exists():
                            d.msgbox("Path exists, stopping")
                            return 1, repoadded
                        else:
                            p.mkdir(mode=0o770, parents=True, exist_ok=False)

                            uuid = ""
                            for dbid in Path("/dev/disk/by-uuid/").iterdir():
                                if str(dbid.resolve()) == part:
                                    uuid = dbid

                            if uuid == "":
                                d.msgbox("Can not resolve uuid")
                                return 1,repoadded
                            else:
                                mountline = "\n{} {} xfs defaults 0 0\n".format(str(uuid),mountpoint)
                                with open("/etc/fstab", "a") as fstab:
                                    fstab.write(mountline)

                                pout = subprocess.run(["mount",mountpoint], capture_output=True)
                                if pout.returncode != 0:
                                    d.msgbox("Error mounting {0}".format(str(pout.stderr,'utf-8')))
                                    return 1,repoadded
                                else:
                                    shutil.chown(str(p),config["repouser"],config["repouser"])
                                    d.msgbox("{} mounted and added!".format(mountpoint))
                                    repoadded = mountpoint
                                    return 0,repoadded

    return 0,repoadded


# Menu 3 register the server
def registerserver(config,d):
        forceregister = False
        if veeamhubutil.veeamrunning():
            c = d.yesno("Veeam Transport Service is already running, do you want to continue")
            if c != d.OK:
                return
            else:
                forceregister = True

        # uses dbus to talk to the service, should be more stable then parsing systemctl output
        # enable ssh when registration starts
        ssh = veeamhubutil.getsshservice()
        sshstarted = False 
        sshstop = False
        if ssh.Unit.ActiveState != b'active':
            code = d.yesno("SSH is not started, shall I temporarily start it?")
            if code == d.OK:
                ssh.Unit.Start(b'replace')
                sshstarted = True
                sshstop = True
        else:
            sshstarted = True

        # if ufw is on (firewall), enable ssh
        if not veeamhubutil.ufw_is_inactive():
            veeamhubutil.ufw_ssh(setstatus="allow")

        #if ssh started, then add a temp sudo file giving the repouser sudo rights
        if sshstarted:
            veeamrepouser = config["repouser"]
            sudofp = "/etc/sudoers.d/90-{}".format(veeamrepouser)
            if not Path(sudofp).exists():
                with open(sudofp, 'w') as outfile:
                    outfile.write("{}   ALL=(ALL:ALL) ALL".format(veeamrepouser))
                os.chmod(sudofp,0o440)        
                timeout = 500
                if 'registertimeout' in config:
                    timeout = config['registertimeout']
                sleeper = 5
                try :
                    while (not veeamhubutil.veeamrunning() or forceregister) and timeout > 0:
                        lines = ["Go to the backup server and connect with single use cred",
                                "User :",config["repouser"],""
                                "IPs :"]
                        lines = lines + veeamhubutil.myips() + ["","Repos:"]
                        for repo in config['repositories']:
                            lines.append(repo)
                        if forceregister:
                            lines = lines + ["","Running in forced mode"]
                        lines = lines + ["","CTRL+C to force exit","Auto locking in {} seconds".format(timeout)]
                        d.infobox("\n".join(lines),width=60,height=(len(lines)+10))
                        timeout = timeout-sleeper
                        time.sleep(sleeper)
                    if veeamhubutil.veeamrunning():
                        while veeamhubutil.veeamreposshcheck(config["repouser"]) and timeout > 0:
                            d.infobox("Veeam Process detected\nWaiting for SSH to stop or for timeout ({})".format(timeout))
                            timeout = timeout-sleeper
                            time.sleep(sleeper)
                except KeyboardInterrupt:
                    d.infobox("Cleaning up")
                
                #delete sudo file and close ssh after the user 
                Path(sudofp).unlink()
                if sshstop:
                    ssh.Unit.Stop(b'replace')
                
                if not veeamhubutil.ufw_is_inactive():
                    veeamhubutil.ufw_ssh(setstatus="deny")
            else:
                d.msgbox("Sudo file already exists, possible breach, please clean up by using sudo rm {0}".format(sudofp))
        else:
            d.msgbox("SSH not started, can not continue")
        

# Menu 4, monitor box
# 4.1
def checkspace(config,d):
    cont = d.OK
    while cont == d.OK:
        ln = ["Repositories:"]
        for repo in config['repositories']:
            stat = shutil.disk_usage(repo)
            #total=53658783744, used=407994368, free=53250789376
            ln.append("{:40} {}% {}GB".format(repo,int(stat.used*10000/stat.total)/100,int(stat.total/1024/1024/1024)))
         
        cont = d.yesno("\n".join(ln),width=60,height=len(ln)+4,yes_label="Refresh",no_label="Cancel")
        print(cont)
# 4.2
def checklogs(config,d):
    code = d.OK
    path = "/var/log/"

    if Path("/var/log/VeeamBackup/").is_dir():
        path = "/var/log/VeeamBackup/"

    while code == d.OK and not Path(path).is_file():
        code, path = d.fselect(path,width=80,height=30)

    if code == d.OK:
        readfile(config,d,path)

# 4.3
def checkproc(config,d):
    cont = d.OK

    procfilter = "veeam"
    while cont == d.OK:
        ln = []
        procs = [p for p in psutil.process_iter(['pid', 'name', 'username']) if procfilter in p.name()]
        if len(procs) > 0:
            for proc in procs:
                ln.append("{} {} {}".format(proc.pid,proc.username(),proc.name()))
        else:
            ln = ["No processes found matching 'veeam'","Did you add this repo?"]
        cont = d.yesno("\n".join(ln),width=60,height=len(ln)+4,yes_label="Refresh",no_label="Cancel")

# 4 main
def monitorrepos(config,d):
        code = d.OK
        while code == d.OK:
            code, tag = d.menu("What do you want to do:",
                       choices=[("1", "Check Disk Space"),
                                ("2", "Check Logs"),
                                ("3", "Show Veeam Processes"),
                                ])
            if code == d.OK:
                if tag == "1":
                    checkspace(config,d)
                elif tag == "2":
                    checklogs(config,d)
                elif tag == "3":
                    checkproc(config,d)
    
# Menu 5, add repo path
def managerepo(config,d):
    updated = False
    code = d.OK
    while code == d.OK:
        code, tag = d.menu("What do you want to do:",
                       choices=[("1", "Add A Repo"),
                                ("2", "Delete A repo"),
                                ])
        if code == d.OK:
            if tag == "1":
                acode,mountpoint = d.inputbox("Which path do you want to add?",init="/backups/repo")
                if acode == d.OK:
                    if not Path(mountpoint).is_dir():
                        d.msgbox("{} is not a path or dir".format(mountpoint))
                    else:
                        d.msgbox("{} added".format(mountpoint))
                        config['repositories'].append(mountpoint)
                        updated = True
            elif tag == "2":
                if len(config['repositories']) == 0:
                    d.msgbox("No repo's added yet")
                else:
                    listrepo = []
                    shadow = {}
                    i = 1
                    for repo in config['repositories']:
                        listrepo.append((str(i),repo))
                        shadow[str(i)] = repo
                        i = i+1
                    dcode, dtag  = d.menu("What repository do you want to remove from config:",choices=listrepo)
                    if dcode == d.OK:
                        config['repositories'].remove(shadow[dtag])
                        updated = True
                    
    return updated

# Menu 6 manage ubuntu
# 6.1 update 
def update(config,d):
    if shutil.which("apt-get") is not None:
        d.infobox("Checking updates...")
        pout = subprocess.run(["apt-get","update","-y"], capture_output=True) 
        if pout.returncode != 0:
            d.msgbox("Error updating {0}".format(str(pout.stderr,'utf-8')))
            return
        d.infobox("Running Update...")
        pout = subprocess.run(["apt-get","upgrade","-y"], capture_output=True) 
        if pout.returncode != 0:
            d.msgbox("Error updating {0}".format(str(pout.stderr,'utf-8')))
            return
        d.infobox("Update Completed")
        time.sleep(1)
    else:
        d.infobox("Apt-get not found, not executing update")
        time.sleep(5)

# 6.2 harden
def disablessh():
    ssh = veeamhubutil.getsshservice()
    if ssh.Unit.ActiveState == b'active':
        ssh.Unit.Stop(b'replace')
		
    mgr = pystemd.systemd1.Manager()
    mgr.load()
    if len([serv for serv in mgr.Manager.ListUnitFiles() if "sshd" in str(serv[0]) ]) > 0:
        mgr.Manager.DisableUnitFiles([b'sshd.service'],False)
    if not veeamhubutil.ufw_is_inactive():
        veeamhubutil.ufw_ssh(setstatus="deny")

def enablefw():
    if veeamhubutil.ufw_is_inactive():
         veeamhubutil.ufw_activate()

def harden(config,d):
    code, tag = d.menu("What do you want to do:",
        choices=[("1", "Enable UFW"),
                    ("2", "Stop and disable SSH"),
                    ("3", "Temporarly enable SSH")])
    if code == d.OK:
        if tag == "1":
            enablefw()			
        elif tag == "2":
            disablessh()
        elif tag == "3":
            ssh = veeamhubutil.getsshservice()
            if ssh.Unit.ActiveState != b'active':
                ssh.Unit.Start(b'replace')
            if not veeamhubutil.ufw_is_inactive():
                veeamhubutil.ufw_ssh(setstatus="allow")
            d.msgbox("SSH started but not on reboot\nDo not forget to Stop it again!!",width=60)

# 6.3 time
# 6.3.1 timezone

def configtimezone(config,d):
    code = d.OK
    path = "/usr/share/zoneinfo/"
    while code == d.OK and not Path(path).is_file():
        code, path = d.fselect(path,width=80,height=30)

    if code == d.OK:
        zi = re.match("^/usr/share/zoneinfo/(.*)",path)
        if zi:
            szi = zi.group(1)
            d.msgbox("Time zone set to {0}".format(szi))

            pout = subprocess.run(["timedatectl","set-timezone",szi], capture_output=True) 
            if pout.returncode != 0:
                d.msgbox("Error updating {0}".format(str(pout.stderr,'utf-8')))
            #symlink doesnt want existing
            #os.symlink(path,"/etc/localtime.new")
            #os.rename("/etc/localtime.new","/etc/localtime")
            #with open("/etc/timezone", 'w') as tz:
            #    tz.write(zi.group(1))

        else:
            d.msgbox("Not a time zone file ({0})".format(path))

# 6.3.2 time
def settime(config,d,time,date,zone,ntpactive):
    if ntpactive:
        y = d.yesno("NTP is already active\nShould I temporarily stop it?")
        if y != d.OK:
            return
        else:
            tsd = pystemd.systemd1.Unit(b'systemd-timesyncd.service')
            tsd.load()
            tsd.Unit.Stop(b'replace')
            
    y,nt = d.inputbox("Define time hh:mm:ss({0})".format(zone),init=time)
    if y == d.OK:
        if not re.match("[0-9]{2}:[0-9]{2}:[0-9]{2}",nt):
            d.msgbox("Error matching time, please make sure to use leading zeroes\nGiven : {0}".format(nt))
            return
        else:
            y,nd = d.inputbox("Define date yyyy-mm-dd",init=date)
            if y == d.OK:
                if not re.match("[0-9]{4}-[0-9]{2}-[0-9]{2}",nd):
                    d.msgbox("Error matching date, please make sure to use leading zeroes\nGiven : {0}".format(nd))
                    return
                else:
                    pout = subprocess.run(["timedatectl","set-time","{} {}".format(nd,nt)], capture_output=True) 
                    if pout.returncode != 0:
                        d.msgbox(str(pout.stderr,'utf-8'))

# 6.3.3 disable ntp
def disablentp(config,d):
    if packagetest("systemd-timesyncd") != 1:
        d.msgbox("NTP is not installed (timesyncd), doing nothing")
    else:
        tsd = pystemd.systemd1.Unit(b'systemd-timesyncd.service')
        tsd.load()
        if tsd.Unit.ActiveState == b'active':
            tsd.Unit.Stop(b'replace')

        mgr = pystemd.systemd1.Manager()
        mgr.load()
        if len([serv for serv in mgr.Manager.ListUnitFiles() if "timesyncd" in str(serv[0]) ]) > 0:
            mgr.Manager.DisableUnitFiles([b'systemd-timesyncd.service'],False)
            

        d.msgbox("Unloaded and disabled timesyncd")

# 6.3.4 ntp
def ntp(config,d):
        if packagetest("systemd-timesyncd") != 1:
            c = d.yesno("Systemd-timesyncd does not seem to be install it\nDo you want to install it?")
            if c != d.OK:
                return
            else:
                if installpackage(d,"systemd-timesyncd"):
                    return

        ntpset = ""
        failoverntp = "ntp.ubuntu.com"

        cfile = "/etc/systemd/timesyncd.conf"
        # timesyncd seems to be a kind of ini file which can be easily parsed. By default it is completely commented out with only the "Time" section
        config = configparser.ConfigParser()
        config.optionxform=str
        config.read(cfile)
        if 'Time' in config.sections():
                if "NTP" in config['Time']:
                    ntpset = config['Time']['NTP']
                if "FallbackNTP" in config['Time']:
                    failoverntp = config['Time']['FallbackNTP']
       
        y,newntpset = d.inputbox("NTP server\n(space separated)",init=ntpset)
        if y == d.OK:
            y,newfailover = d.inputbox("Failover NTP server\n(space separated)",init=failoverntp)
            if y == d.OK:
                if newntpset != ntpset or newfailover != failoverntp:
                    shutil.copyfile(cfile, "{}.{}.backup".format(cfile,datetime.datetime.now().strftime("%Y%m%d%H%M%S")))
                    config['Time']['NTP'] = newntpset
                    config['Time']['FallbackNTP'] = newfailover

                    d.infobox("Updating..")
                    with open(cfile, 'w') as configfile:
                           config.write(configfile)


                d.infobox("Reloading timesync service")
                tsd = pystemd.systemd1.Unit(b'systemd-timesyncd.service')
                tsd.load()
                tsd.Unit.Stop(b'replace')
                tsd.Unit.Start(b'replace')
                
                mgr = pystemd.systemd1.Manager()
                mgr.load()
                mgr.Manager.EnableUnitFiles([b'systemd-timesyncd.service'],False,True)
                    
# 6.3 main menu

def managetime(config,d):
        code = d.OK
        while code == d.OK:
            ln,time,date,zone,ntpactive = veeamhubutil.gettimeinfo()
            ln.append("") 
            ln.append("What do you want to do")
            code, tag = d.menu("\n".join(ln),
                       choices=[("1", "Configure Timezone"),
                                ("2", "Manually Set Time"),
                                ("3", "Disable NTP (timesyncd)"),
                                ("4", "Configure NTP (timesyncd)")
                                ],height=len(ln)+9)
            if code == d.OK:
                if tag == "1":
                    configtimezone(config,d)
                elif tag == "2":
                    settime(config,d,time,date,zone,ntpactive)
                elif tag == "3":
                    disablentp(config,d)
                elif tag == "4":
                    ntp(config,d)

def netfileselector(config,d):
    basedir = "/etc/netplan"
    files = glob.glob(basedir+"/*.yaml")
    lenf = len(files)
    if lenf == 0:
        d.msgbox("Error could not located yaml file")
        return ""
    elif lenf > 1:
        code = d.OK
        path = basedir
        while code == d.OK and not Path(path).is_file():
            code, path = d.fselect(path,width=80,height=30)
        if code != d.OK:
            return ""
        else:
            return path
    else:
        return files[0]


def applynetplanyaml(config,d,yfile,newyaml):
    if newyaml != "":
        os.rename(yfile,yfile+".backup")
        with open(yfile,'w') as yamlfile:
            yamlfile.write(newyaml)

        pout = subprocess.run(["netplan","apply"], capture_output=True) 
        if pout.returncode != 0:
            d.msgbox("Error  {0}".format(str(pout.stderr,'utf-8'))) 

# 6.4.1
def managestaticip(config,d):
    file = netfileselector(config,d)
    if file != "":
        newyaml = ""
        with open(file,'r') as yamlfile:
            loadedyaml = yaml.load(yamlfile,Loader=yaml.SafeLoader)
            choices = []
            ch = 1
            shadow = {}

            for net in veeamhubutil.realnics():
                choices.append((str(ch),net))
                shadow[str(ch)] = net
                ch = ch+1
            
            
            code, tag = d.menu("Which network card do you want to edit",choices=choices,height=len(choices)+11)
            if code == d.OK:
                netifsh = shadow[tag]

                
                section = "ethernets"
                if netifsh in loadedyaml.get("network").get("bonds"):
                    section = "bonds"

                if netifsh in loadedyaml.get("network").get("bridges"):
                    section = "bridges"

                netifyaml = loadedyaml.get("network").get(section).get(netifsh)


                addrs = veeamhubutil.firstipwithnet(netifsh)
                if netifyaml:
                    addrsg = netifyaml.get('addresses')
                    if addrsg:
                        addrs = ",".join(addrsg)
                
                code,addrs = d.inputbox("IPv4/subnet",addrs)
                if code != d.OK:
                    return

                gw = veeamhubutil.firstgw(netifsh)
                if netifyaml:
                    gwg = netifyaml.get('gateway4')
                    if gwg:
                        gw = gwg 
                
                code,gateway = d.inputbox("Gateway",init=gw)
                if code != d.OK:
                    return
                    
                dns = "8.8.8.8,8.8.4.4"
                search = ""

                if netifyaml:
                    ns = netifyaml.get('nameservers')
                    if ns:
                        dnsg = ns.get('addresses')
                        if dnsg:
                            dns = ",".join(dnsg)

                        searchg = ns.get('search')
                        if searchg:
                            search = ",".join(searchg)

                code,dns = d.inputbox("DNS servers seperated with ,",init=dns)
                if code != d.OK:
                    return

                code,dnssearch = d.inputbox("DNS search seperated with ,",init=search)
                if code != d.OK:
                    return

                code = d.yesno("\n".join(["Confirm settings","","IPv4: "+addrs,"Gateway: "+gateway,"DNS: "+dns,"DNSSearch: "+dnssearch]))
                if code == d.OK:
                    ifconf = {'addresses': addrs.split(","), 'gateway4': gateway, 'nameservers': {'addresses': dns.split(","), 'search': dnssearch.split(",")}}
                    if section == "bonds" or section == "bridges":
                        oldconfig = loadedyaml.get('network').get(section)[netifsh]
                        if oldconfig:
                            if oldconfig.get('parameters'):
                                ifconf['parameters'] = oldconfig.get('parameters')
                            if oldconfig.get('interfaces'):
                                ifconf['interfaces'] = oldconfig.get('interfaces')

                    loadedyaml.get('network').get(section)[netifsh] = ifconf

                    newyaml = yaml.dump(loadedyaml)

        if newyaml != "":
            os.rename(file,file+".backup")
            with open(file,'w') as yamlfile:
                yamlfile.write(newyaml)

            pout = subprocess.run(["netplan","apply"], capture_output=True) 
            if pout.returncode != 0:
                d.msgbox("Error  {0}".format(str(pout.stderr,'utf-8')))

#6.4.2
def managedhcp(config,d):
    file = netfileselector(config,d)
    if file != "":
        newyaml = ""
        with open(file,'r') as yamlfile:
            loadedyaml = yaml.load(yamlfile,Loader=yaml.SafeLoader)
            choices = []
            ch = 1
            shadow = {}


            for net in veeamhubutil.realnics():
                choices.append((str(ch),net))
                shadow[str(ch)] = net
                ch = ch+1
            
            
            code, tag = d.menu("Which network card do you want to edit",choices=choices,height=len(choices)+11)
            if code == d.OK:
                netifsh = shadow[tag]

                section = "ethernets"
                if netifsh in loadedyaml.get("network").get("bonds"):
                    section = "bonds"

                if netifsh in loadedyaml.get("network").get("bridges"):
                    section = "bridges"


                code = d.yesno("\n".join(["Confirm DHCP for",netifsh]))
                if code == d.OK:
                    ifconf = {'dhcp4': True}

                    if section == "bonds" or section == "bridges":
                        oldconfig = loadedyaml.get('network').get(section)[netifsh]
                        if oldconfig:
                            if oldconfig.get('parameters'):
                                ifconf['parameters'] = oldconfig.get('parameters')
                            if oldconfig.get('interfaces'):
                                ifconf['interfaces'] = oldconfig.get('interfaces')


                    loadedyaml.get('network').get(section)[netifsh] = ifconf
                    newyaml = yaml.dump(loadedyaml)

        if newyaml != "":
            os.rename(file,file+".backup")
            with open(file,'w') as yamlfile:
                yamlfile.write(newyaml)

            pout = subprocess.run(["netplan","apply"], capture_output=True) 
            if pout.returncode != 0:
                d.msgbox("Error  {0}".format(str(pout.stderr,'utf-8'))) 

def managebond(config,d):
    yfile = netfileselector(config,d)
    if yfile != "":
        newyaml = ""
        with open(yfile,'r') as yamlfile:
            loadedyaml = yaml.load(yamlfile,Loader=yaml.SafeLoader)
            choices = []
            shadow = {}
            ch = 1

            for net in veeamhubutil.realnics():
                choices.append((str(ch),net,0))
                shadow[str(ch)] = net
                ch = ch+1

            code,choices = d.checklist("Select interfaces for your bound.\nThe first bond will be your primary!!!",choices=choices,height=len(choices)+11)
            if code == d.OK and len(choices) > 0:
                nifs = []
                
                for c in choices:
                    nifs.append(shadow[c])
                
                code = d.yesno("Are you sure you want to add the following interfaces:\n"+"\n".join(nifs)+"\nPrimary: "+nifs[0])
                if code == d.OK:
                    code, bondname = d.inputbox("Give your bond a name in the form bond<num> e.g bond0",init="bond0")
                    if code == d.OK:

                        

                        choices = [("1","active-backup"),("2","lacp")]

                        code, modus = d.menu("Which modus do you want?",choices=choices,height=len(choices)+11)
                        if code == d.OK:
                            parameters = {"mode":"active-backup","primary":nifs[0],"mii-monitor-interval": 100} 
                            if modus == "2":
                                parameters = {"mode":"802.3ad","lacp-rate":"fast","mii-monitor-interval":100} 

                            bonds = loadedyaml.get('network').get("bonds")
                            if not bonds:
                                bonds = {}
                            
                            pdef = loadedyaml.get('network').get("ethernets")[nifs[0]]
                            bondconfig = {"dhcp4": True}

                            if pdef:
                                code = d.yesno("Do you want me to migrate the network from "+nifs[0])
                                if code == d.OK:
                                    bondconfig = pdef
                           
                            bondconfig["interfaces"] = nifs
                            bondconfig["parameters"] = parameters
                            bonds[bondname] = bondconfig
                            for nif in nifs:
                                loadedyaml.get('network').get('ethernets')[nif] = {'dhcp4': False}

                            loadedyaml.get('network')["bonds"] = bonds
                            newyaml = yaml.dump(loadedyaml)

        if newyaml != "":
            applynetplanyaml(config,d,yfile,newyaml)
        

#6.4.4
def managenetman(config,d):
    file = netfileselector(config,d)
    if file != "":
        openfile(config,d,file) 

        code = d.yesno("\n".join(["Apply changes?"]))
        if code == d.OK:
            pout = subprocess.run(["netplan","apply"], capture_output=True) 
            if pout.returncode != 0:
                d.msgbox("Error  {0}".format(str(pout.stderr,'utf-8'))) 
#6.4.6
def managebridge(config,d):
    yfile = netfileselector(config,d)
    if yfile != "":
        newyaml = ""
        with open(yfile,'r') as yamlfile:
            loadedyaml = yaml.load(yamlfile,Loader=yaml.SafeLoader)
            choices = []
            shadow = {}
            ch = 1

            for net in veeamhubutil.realnics():
                choices.append((str(ch),net,0))
                shadow[str(ch)] = net
                ch = ch+1
            
            code,tag = d.menu("Select interfaces for your bridge",choices=choices,height=len(choices)+11)
            if code == d.OK:
                netif = shadow[tag]
                if d.yesno("Are you sure you want to create a bridge on "+netif) == d.OK:
                    section = "ethernets"
                    if netif in loadedyaml.get("network").get("bonds"):
                        section = "bonds"
                

                    brconfig = {"dhcp4": True}
                    copysection = loadedyaml.get("network").get(section)[netif]

                    updatetoorig = {"dhcp4": False}
                    if copysection["interfaces"]:
                        updatetoorig["interfaces"] = copysection["interfaces"]
                    if copysection["parameters"]:
                        updatetoorig["parameters"] = copysection["parameters"]
                    loadedyaml.get("network").get(section)[netif] = updatetoorig

                    if copysection:
                        brconfig = copysection
                        if brconfig["parameters"]:
                            del brconfig["parameters"]
                    brconfig["interfaces"] = [netif]
                    
                    brs = loadedyaml.get('network').get("bridges")
                    if not brs:
                        brs = {}

                    brs["br0"] = brconfig

                    loadedyaml.get('network')["bridges"] = brs
                    newyaml = yaml.dump(loadedyaml)

        if newyaml != "":
            applynetplanyaml(config,d,yfile,newyaml)


# 6.4 manage network
def managenetwork(config,d):
    code = d.OK
    while code == d.OK:
        ln = []
        ln.append("What do you want to do")
        code, tag = d.menu("\n".join(ln),
                       choices=[("1", "Setup STATIC IP"),
                                ("2", "Setup DHCP"),
                                ("3", "Create a Bond"),
                                ("4", "Manually change netplan"),
                                ("5", "Create a bridge for LXD"),
                                ],height=len(ln)+11)
        if code == d.OK:
            if tag == "1":
                managestaticip(config,d)
            elif tag == "2":
                managedhcp(config,d)
            elif tag == "3":
                managebond(config,d)
            elif tag == "4":
                managenetman(config,d)
            elif tag == "5":
                managebridge(config,d)
                
# 6.5.1 lxdproxy
def lxdsetup(config,d):
        code = d.yesno("\n".join(["Are you sure you want to set this up? This is highly experimental"]))
        if code == d.OK:
            pout = subprocess.run(["sudo","snap","install","lxd"], capture_output=True) 
            if pout.returncode != 0:
                d.msgbox("Error  {0}".format(str(pout.stderr,'utf-8')))
                return
            else:
                if not "br0" in veeamhubutil.realnics():
                    d.msgbox("Please setup bridge networking first")
                else:
                    d.infobox("Doing lxd initial setup, this can take a while")
                    pout = subprocess.run(["lxd","init","--auto"], capture_output=True) 
                    if pout.returncode != 0:
                        d.msgbox("Error  {0}".format(str(pout.stderr,'utf-8')))
                        return
                    pout = subprocess.run(["lxd","waitready"], capture_output=True) 
                    if pout.returncode != 0:
                        d.msgbox("Error  {0}".format(str(pout.stderr,'utf-8')))
                        return
                    pout = subprocess.run("lxc profile copy default veeamproxy".split(), capture_output=True) 
                    if pout.returncode != 0:
                        d.msgbox("Error  {0}".format(str(pout.stderr,'utf-8')))
                        return
                    pout = subprocess.run("lxc profile device remove veeamproxy eth0".split(), capture_output=True) 
                    if pout.returncode != 0:
                        d.msgbox("Error  {0}".format(str(pout.stderr,'utf-8')))
                        return
                                        

def lxcproxyinfo(d,tolerateerror=False):
        s = subprocess.run(["lxc","list","lxdproxy","--format","yaml"], capture_output=True)
        lxpyaml = {"status":{"status_code":1}}

        if s.returncode == 0:
            lxpyaml = yaml.load(s.stdout,Loader=yaml.SafeLoader)[0]
        else:
            if not tolerateerror:
                d.msgbox("Unexpected error "+str(s.stderr))
        return s.returncode,lxpyaml

def lxdexec(d,step,instructarr):
    d.infobox("LXC exec : "+step)
    pout = subprocess.run(instructarr, capture_output=True)
    if pout.returncode != 0:
        d.msgbox("Error  {0}".format(str(pout.stderr,'utf-8')))
        return False
    else:
        return True

def lxctryexec(d):
    trycmd = ["lxc","exec","lxdproxy","--","/bin/bash","-c","echo ''"] 
    tryouts = 12

    pout = subprocess.run(trycmd, capture_output=True)
    while pout.returncode != 0 and tryouts > 0:
        pout = subprocess.run(trycmd, capture_output=True)
        tryouts = tryouts - 1
        d.infobox("Waiting for image to stabilize\n"+str(tryouts)+"\n"+str(pout.stderr))
        time.sleep(5)
    
    if pout.returncode != 0:
        d.msgbox("Tried to stabilize image but didn't work "+str(pout.stderr))
    return pout.returncode

def lxdsetupproxy(config,d):
    steps = [
            { "step":"lxd waitready", "instruct":["lxd","waitready"]},
            { "step":"lxc proxy (download 3GB, get a coffee)", "instruct":["lxc","launch","ubuntu:20.04","lxdproxy","--vm","--network","br0","--profile","veeamproxy"] }
        ]
    for s in steps:
        success = lxdexec(d,s["step"],s["instruct"])
        if not success:
            return

    #code 103 means the vm is running
    scode = 0
    while scode != 103 and scode != -1:
        err,lxcinfo = lxcproxyinfo(d,True)
        if err != 0:
            scode = -1
        scode = lxcinfo.get("state").get("status_code")
        d.infobox("Waiting for VM to get ready")
        time.sleep(1)

    if scode == 103:
        d.infobox("LXC proxy running")
        lxctryexec(d)

        code,ipaddr = d.inputbox("IP for proxy","0.0.0.0/24")
        code,gateway = d.inputbox("Gateway for proxy","0.0.0.0")
        code,dns = d.inputbox("DNS server for proxy","8.8.8.8")

        #this really needs some cleaner way
        modnet = 'NETPLAN=$(find /etc/netplan/*.yaml) && sed -i \'s/\\([ ]*\\)dhcp4: true/\\1addresses: ['+ipaddr.replace("/",'\\/')+']\\n\\1gateway4: '+gateway+'\\n\\1nameservers: { addresses: ['+dns+']}/\' $NETPLAN'

        steps = [ 
            { "step":"modifying NET", "instruct":["lxc","exec","lxdproxy","--","/bin/bash","-c",modnet]}, 
            { "step":"applying NET", "instruct":["lxc","exec","lxdproxy","--","/bin/bash","-c","netplan apply"]}, 
            { "step":"setup SSH", "instruct":["lxc","exec","lxdproxy","--","/bin/bash","-c","ssh-keygen -A && systemctl start ssh && systemctl enable ssh"]}, 
            { "step":"setup USER", "instruct":["lxc","exec","lxdproxy","--","/bin/bash","-c","useradd -m veeamproxy && echo 'veeamproxy:$6$moMETbaDQEN2m8pt$UTL5FzNLsIb1PbFGXSyr/AJiMjLJcYbcjxWyNEo7rTR5B04CCFxGatNArKOZvnL/UtnkhKLXJQH68y.O5a8sb.' | chpasswd -e"]},
            { "step":"allow PW Login", "instruct":["lxc","exec","lxdproxy","--","/bin/bash","-c","sed -i 's/PasswordAuthentication no/PasswordAuthentication yes/g' /etc/ssh/sshd_config && systemctl restart sshd"]},
            { "step":"adding SUDO", "instruct":["lxc","exec","lxdproxy","--","/bin/bash","-c","echo 'veeamproxy    ALL=(ALL:ALL) ALL' >> /etc/sudoers"]},
        ]
            #{ "step":"", "instruct":["lxc","exec","lxdproxy","--","/bin/bash","-c","''"]},
        for s in steps:
            success = lxdexec(d,s["step"],s["instruct"])
            if not success:
                return

        d.msgbox("Proxy should be reachable on "+ipaddr+" with veeamproxy:changeme\nMake sure to change the password by logging in via ssh/putty and using the passwd command")




def managelxd(config,d):
    code,agree = d.inputbox("This potentially creates another security vector\nPlease type 'iunderstand' to continue")
    if code == d.OK and agree == 'iunderstand':
        while code == d.OK:
            code, tag = d.menu("What do you want to do:",
                       choices=[("1", "Initial setup"),
                                ("2", "Create Proxy")
                                ])
            if code == d.OK:
                if tag == "1":
                    lxdsetup(config,d)
                elif tag == "2":
                    lxdsetupproxy(config,d)

# 6
def manageubuntu(config,d):
        code = d.OK
        while code == d.OK:
            code, tag = d.menu("What do you want to do:",
                       choices=[("1", "Update"),
                                ("2", "Harden"),
                                ("3", "Manage Time"),
                                ("4", "Manage Network"),
                                ("5", "Add Experimental LXD Proxy"),
                                ])
            if code == d.OK:
                if tag == "1":
                    update(config,d)
                elif tag == "2":
                    harden(config,d)
                elif tag == "3":
                    managetime(config,d)
                elif tag == "4":
                    managenetwork(config,d)
                elif tag == "5":
                    managelxd(config,d)

 
# main loop
def saveconfig(cfile,config):
    with open(cfile, 'w') as outfile:
        json.dump(config, outfile)


def home(style="default"):
    # http://pythondialog.sourceforge.net/ following this
    # This is almost always a good thing to do at the beginning of your programs.
    locale.setlocale(locale.LC_ALL, '')

    # config file is made under /etc/veeamhubtinyrepoman
    # mainly keeps the repositories data and the repouser
    cfile = Path('/etc') / "veeamhubtinyrepoman"
    
    #d =  Dialog(dialog="dialog")
    #d.set_background_title("VeeamHub Tiny Repo Manager")

    rows,columns = dialogwrappers.screensize()

    if (rows < 40 or columns < 90) and style == "default":
        print("Switching to alternate dialog style because small terminal (r{},c{}), need at least 40 rows and 90 columns".format(rows,columns))
        print("To avoid this message, resize the terminal or run with -alt flag")
        print("In VMware the console screen might be to small, you can adapt it with vga=791 in grub")
        print("https://askubuntu.com/questions/86561/how-can-i-increase-the-console-resolution-of-my-ubuntu-server")
    
        style="alternate"
        time.sleep(2)
    

    d = 0
    if style == "alternate":
        d = dialogwrappers.AlternateDialog("Alternate VeeamHub Tiny Repo Manager",rows,columns)
    else:
        d = dialogwrappers.DialogWrapper("VeeamHub Tiny Repo Manager")


    code = d.OK
    config = {"repouser":"veeamrepo","vbrserver":"","reader":["nano","-v"],"writer":["nano"],"registertimeout":500}

    firstrun = False

    # json file. If it does not exists, it's create with the default settings above
    # if exists, it is read
    if not cfile.is_file():
        d.infobox("Trying to create:\n{}".format(str(cfile)),width=80)
        time.sleep(2)
        firstrun = True
        config['repositories'] = []
        with open(cfile, 'w') as outfile:
                json.dump(config, outfile)
    else:
        with open(cfile, 'r') as outfile:
                config = json.load(outfile)
    

    if firstrun:
        c = d.yesno("This is the first time you started veeamhubrepo\n\nDo you want to run the wizard process?\n\nThis will execute certain actions automatically!",width=60,height=15)
        if c == d.OK:
            setrepouser(config,d)
            saveconfig(cfile,config)

            rcode,mp = formatdrive(config,d)
            if rcode == 0 and mp != "":
                config['repositories'].append(mp)
            saveconfig(cfile,config)

            c = d.yesno("Do you want to configure NTP and the timezone?")
            if c == d.OK:
                configtimezone(config,d)
                ntp(config,d)

            d.infobox("Disabling SSH at startup")
            time.sleep(1)
            disablessh()

            d.infobox("Enabling the firewall")
            time.sleep(1)
            enablefw()

            c = d.yesno("Do you want to try to update the server now?")
            if c == d.OK:
                update(config,d)

            registerserver(config,d)

            

    # while you keep getting ok, keep going
    while code == d.OK:
        updated = False
    
        ln = ["Current IPv4: {}".format(",".join(veeamhubutil.myips()))]
        if veeamhubutil.is_ssh_on():
            ln.append("! SSH is running !")

        ln.append("")
        ln.append("What do you want to do:")

        # keep structure as it, add new functionality under sub menu so that it doesn't get too big
        code, tag = d.menu("\n".join(ln),
                       choices=[("1", "Set/Create Unprivileged Repo User"),
                                ("2", "Format Drive XFS"),
                                ("3", "Register Hardened Repo"),
                                ("4", "Monitor Repositories"),
                                ("5", "Manages Repo Paths"),
                                ("6", "Manage Ubuntu"),
                                ],height=len(ln)+14,cancel="Exit")
        if code == d.OK:
            if tag == "1":
                setrepouser(config,d)
                updated = True
            elif tag == "2" or tag == "5":
                if usersexists(config["repouser"]):
                    if tag == "2":
                        rcode,mp = formatdrive(config,d)
                        if rcode == 0 and mp != "":
                            config['repositories'].append(mp)
                            updated = True
                    elif tag == "5":
                        updated = managerepo(config,d)
                else:
                    d.msgbox("Please create repo user first")
            elif tag == "3":
                registerserver(config,d)
            elif tag == "4":
                monitorrepos(config,d)
            elif tag == "6":
                manageubuntu(config,d)
            if updated:
                with open(cfile, 'w') as outfile:
                    json.dump(config, outfile)

# cleans output after being done
def main():
    args = sys.argv[0:]
    if "-alt" in args:
        home(style="alternate")
    else:
        home(style="default")

    subprocess.run(["clear"])

if __name__ == "__main__":
    if os.getuid() != 0:
        print("You are running this command as a regular user")
        print("Please use sudo e.g. sudo veeamhubrepo")
        exit(1)
    main()

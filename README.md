# VeeamHub Repo

Experimental Python script to quickly setup an immutable repository. Initially made to quickly setup demo labs but feedback is appreciated. Tested only on Ubuntu 20.04 LTS (and this is the only target for this project until the next LTS).

Check the release page to get debian package

Easy install by using wget to download the package and sudo apt-get install ./veeamhubrepo.deb to install it e.g
```
sudo wget -O ./veeamhubrepo.deb https://github.com/tdewin/veeamhubrepo/releases/download/v0.3.1/veeamhubrepo_noarch.deb
sudo apt-get install ./veeamhubrepo.deb
sudo veeamhubrepo
```

How it works:
- Deploy Ubuntu 20.04 LTS on disk 1 (16GB is more then enough, you only need the base install)
- Add a secondary repository disk/block device
- Deploy Veeamhub Repo
- Launch Veeamhub Repo
- A wizard will start that should detect the second disk/block device via lsblk and ask you to format it (experimental project be careful)
- Additionally it will create a new unpriveleged user, disable SSH, configure the firewall, ..
- Add the end of the wizard it will ask you to enable SSH. Before you start this process, make sure that you are ready to add the repository to a Veeam V11 installation
- Enable SSH, the wizard will show you the configured IP, user, etc. as a reminder. Go to V11 and register the repo with "Single use credentials" and "elevate automatically" checked
- Once you click through, the GUI should detect that the repository is added, auto close SSH and remove sudo power to the veeamrepo user. 

Next time you open the VeeamHub repo manager, it will allow you to modify settings, read logs or monitor space usage


If you did a clean install, you install the packages and it complains about depencies, please run an apt-get update
```
sudo apt-get update
```

Alternatively you can just download the python script but the advantage with the package is that it will put everything in the correct location and it will download all dependecies.


# FAQ

Q: Why is the initial release 0.3.1
A: This was an internal project so that other engineers quickly could get started with Linux immutable repositories


# Screenshot

![Main Menu](https://raw.githubusercontent.com/tdewin/veeamhubrepo/main/media/screenshot_main.png)

MIT License 
 

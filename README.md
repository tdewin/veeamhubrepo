# VeeamHub Repo

*Initial README, needs updating after everything is uploaded*

Experimental Python script to quickly setup an immutable repository. Initially made to quickly setup demo labs but feedback is appreciated. Tested only on Ubuntu 20.04 LTS (and this is the only target for this project until the next LTS).

Check the release page to get debian package

Easy install by using wget to download the package and sudo apt-get install ./veeamhubrepo.deb to install it e.g
```
sudo wget -O ./veeamhubrepo.deb https://github.com/tdewin/url/to/release/veeamhubrepo-0.3.1_noarch.deb
sudo apt-get install ./veeamhubrepo.deb
sudo veeamhubrepo
```

Alternatively you can just download the python script but the advantage with the package is that it will put everything in the correct location and it will download all dependecies.

# FAQ

Q: Why is the initial release 0.3.1
A: This was an internal project so that other engineers quickly could get started with Linux immutable repositories

MIT License 
 

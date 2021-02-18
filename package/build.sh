BUILDPATH=/home/veeamadmin/package
rm $BUILDPATH/../dist/veeamhubrep*.deb
cp $BUILDPATH/../src/veeamhubrepo $BUILDPATH/veeamhubrepo/usr/bin/
dpkg-deb --build $BUILDPATH/veeamhubrepo
mv $BUILDPATH/veeamhubrepo.deb $BUILDPATH/../dist/veeamhubrepo_noarch_latest.deb
cp $BUILDPATH/../dist/veeamhubrepo_noarch_latest.deb $BUILDPATH/../dist/veeamhubrepo_noarch_$(date +"Y_%m_%d").deb

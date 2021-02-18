BUILDPATH=$(pwd)
DIST=$BUILDPATH/../dist
SRC=$BUILDPATH/../src

mkdir $DIST -p

cp $SRC/veeamhubrepo $BUILDPATH/veeamhubrepo/usr/bin/
dpkg-deb --build $BUILDPATH/veeamhubrepo

mv $BUILDPATH/veeamhubrepo.deb $DIST/veeamhubrepo_noarch_latest.deb
cp $BUILDPATH/../dist/veeamhubrepo_noarch_latest.deb $BUILDPATH/../dist/veeamhubrepo_noarch_$(date +"Y_%m_%d").deb


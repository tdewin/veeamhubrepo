#! /usr/bin/env python3
# run: python3 src/test_package_ownership.py package/veeamhubrepo.deb
import io
import subprocess
import sys
import tarfile


def check_package_ownership(package):
    payload = subprocess.run(
        ["dpkg-deb", "--fsys-tarfile", package],
        check=True,
        stdout=subprocess.PIPE,
    ).stdout
    with tarfile.open(fileobj=io.BytesIO(payload)) as archive:
        incorrect = [
            f"{member.name}: {member.uid}:{member.gid}"
            for member in archive
            if member.uid != 0 or member.gid != 0
        ]
    if incorrect:
        raise SystemExit("Package entries must be owned by root:root:\n" + "\n".join(incorrect))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(f"Usage: {sys.argv[0]} PACKAGE.deb")
    check_package_ownership(sys.argv[1])
    print("ok  package entries are owned by root:root")

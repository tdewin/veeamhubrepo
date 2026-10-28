#! /usr/bin/env python3
# run: python3 test_mkfs_cmd.py
import diskcmd

def test_mkfs_skips_discard():
    # -K is the hang fix and must always be present
    cmd = diskcmd.mkfsxfs_cmd("/dev/sdb1")
    assert "-K" in cmd, "must skip discard (-K) or huge disks hang on TRIM"
    assert cmd[0] == "mkfs.xfs" and cmd[-1] == "/dev/sdb1"
    assert "-f" not in cmd
    # log size is left to mkfs.xfs auto-sizing (no -l)
    assert "-l" not in cmd

def test_mkfs_force():
    cmd = diskcmd.mkfsxfs_cmd("/dev/sdb1", force=True)
    assert "-f" in cmd and "-K" in cmd

def test_partition_node():
    assert diskcmd.partition_node("/dev/sdb") == "/dev/sdb1"
    assert diskcmd.partition_node("/dev/nvme0n1") == "/dev/nvme0n1p1"
    assert diskcmd.partition_node("/dev/mmcblk0") == "/dev/mmcblk0p1"

def test_is_whole_disk():
    assert diskcmd.is_whole_disk("/dev/sdb")
    assert diskcmd.is_whole_disk("/dev/nvme0n1")
    assert not diskcmd.is_whole_disk("/dev/sdb1")
    assert not diskcmd.is_whole_disk("/dev/nvme0n1p1")

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")

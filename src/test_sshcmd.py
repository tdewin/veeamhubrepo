#! /usr/bin/env python3
# run: python3 test_sshcmd.py
from sshcmd import start_units, SOCKET, SERVICE

def test_default_socket_activation():
    assert start_units(None, b'enabled', b'disabled') == [SOCKET]

def test_explicit_service_never_starts_socket():
    # P1: socket disabled but present, service configured -> don't open :22
    assert start_units(None, b'disabled', b'enabled') == [SERVICE]
    assert start_units(None, b'masked', b'disabled') == [SERVICE]
    # socket merely disabled, service not enabled, but generator masked
    assert start_units(None, b'disabled', b'disabled', True) == [SERVICE]

def test_recorded_mode_survives_hardening():
    # after hardening both are disabled; the recorded mode decides
    assert start_units(SERVICE, b'disabled', b'disabled') == [SERVICE]
    assert start_units(SOCKET, b'disabled', b'disabled') == [SOCKET]

def test_unknown_falls_back():
    assert start_units(None, b'disabled', b'disabled') == [SOCKET, SERVICE]
    assert start_units(None, b'', b'disabled') == [SOCKET, SERVICE]

if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all passed")

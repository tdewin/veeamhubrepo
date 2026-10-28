# pure SSH unit selection, no external deps so it can be self-checked
# (see test_sshcmd.py)

SOCKET, SERVICE = b'ssh.socket', b'ssh.service'

def start_units(recorded, socket_state, service_state, generator_masked=False):
    # which unit(s) to start, honouring the mode the admin configured.
    # recorded: unit saved before our hardening disabled both, else None.
    # *_state: systemd UnitFileState (b'enabled', b'disabled', b'masked', ...)
    # generator_masked: sshd-socket-generator masked, i.e. the admin opted out
    #   of socket activation even if neither unit is enabled right now
    # current explicit config wins: the admin may have switched mode after we
    # recorded it, and a stale socket record would reopen :22 on all interfaces
    if socket_state == b'enabled':
        return [SOCKET]
    if service_state == b'enabled' or socket_state == b'masked' or generator_masked:
        return [SERVICE]
    # nothing explicit left (our hardening disabled both): fall back to the record
    if recorded in (SOCKET, SERVICE):
        return [recorded]
    # mode unknown: Ubuntu 22.10+ default is the socket, older is the service
    return [SOCKET, SERVICE]

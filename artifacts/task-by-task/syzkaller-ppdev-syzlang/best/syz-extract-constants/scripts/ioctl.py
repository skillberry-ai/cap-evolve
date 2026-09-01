#!/usr/bin/env python3
"""Compute Linux ioctl request numbers as DECIMAL integers for syzkaller .const files.

Linux encodes an ioctl request as a 32-bit number:  dir(2) | size(14) | type(8) | nr(8)

    _IO(type, nr)         no data transfer        -> syzlang arg omitted entirely
    _IOR(type, nr, size)  kernel -> user  (read)  -> syzlang arg ptr[out, ...]
    _IOW(type, nr, size)  user  -> kernel (write) -> syzlang arg ptr[in,  ...]
    _IOWR(type, nr, size) both directions         -> syzlang arg ptr[inout, ...]

`type` is the "magic" character (e.g. 'p' for ppdev) or its numeric code.
`nr` is the command ordinal, `size` is sizeof(the data type) in bytes.

Usage (nr/size accept 0x hex or decimal, output is always DECIMAL):
    python3 ioctl.py IO   p 0x8b          # -> 28811
    python3 ioctl.py IOW  p 0x80 4        # -> 1074032768
    python3 ioctl.py IOR  p 0x98 4        # -> 2147774616
    python3 ioctl.py IOWR p 0x12 8

    # batch: read "NAME KIND type nr [size]" lines on stdin, emit "NAME = decimal"
    printf 'PPCLAIM IO p 0x8b\nPPSETMODE IOW p 0x80 4\n' | python3 ioctl.py --batch

IMPORTANT: write the values into the .const file as PLAIN BASE-10 DECIMAL
integers (e.g. `PPCLAIM = 28811`). Do NOT write hex (`0x708b`) — tooling that
parses the .const file expects decimal.
"""
import sys

_IOC_NRBITS = 8
_IOC_TYPEBITS = 8
_IOC_SIZEBITS = 14
_IOC_NRSHIFT = 0
_IOC_TYPESHIFT = _IOC_NRSHIFT + _IOC_NRBITS       # 8
_IOC_SIZESHIFT = _IOC_TYPESHIFT + _IOC_TYPEBITS   # 16
_IOC_DIRSHIFT = _IOC_SIZESHIFT + _IOC_SIZEBITS    # 30
_IOC_NONE, _IOC_WRITE, _IOC_READ = 0, 1, 2


def _type_code(t):
    """A single-character magic ('p') or a numeric literal ('0x70'/'112')."""
    t = str(t).strip()
    if len(t) == 1 and not t.isdigit():
        return ord(t)
    return int(t, 0)


def _ioc(direction, t, nr, size):
    return ((direction << _IOC_DIRSHIFT)
            | (_type_code(t) << _IOC_TYPESHIFT)
            | (int(str(nr), 0) << _IOC_NRSHIFT)
            | (int(str(size), 0) << _IOC_SIZESHIFT)) & 0xFFFFFFFF


def _IO(t, nr):          return _ioc(_IOC_NONE, t, nr, 0)
def _IOR(t, nr, size):   return _ioc(_IOC_READ, t, nr, size)
def _IOW(t, nr, size):   return _ioc(_IOC_WRITE, t, nr, size)
def _IOWR(t, nr, size):  return _ioc(_IOC_READ | _IOC_WRITE, t, nr, size)

_KINDS = {"IO": _IOC_NONE, "IOR": _IOC_READ, "IOW": _IOC_WRITE,
          "IOWR": _IOC_READ | _IOC_WRITE}


def compute(kind, t, nr, size=0):
    kind = kind.upper().lstrip("_")
    if kind not in _KINDS:
        raise ValueError(f"unknown ioctl kind {kind!r}; use IO/IOR/IOW/IOWR")
    return _ioc(_KINDS[kind], t, nr, size)


def main(argv):
    if argv and argv[0] == "--batch":
        for line in sys.stdin:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            name, kind, t, nr = parts[0], parts[1], parts[2], parts[3]
            size = parts[4] if len(parts) > 4 else 0
            print(f"{name} = {compute(kind, t, nr, size)}")
        return 0
    if len(argv) < 3:
        print(__doc__)
        return 2
    kind, t, nr = argv[0], argv[1], argv[2]
    size = argv[3] if len(argv) > 3 else 0
    print(compute(kind, t, nr, size))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Read-only locale identity samples, not a replacement for the xterm sweep."""
import ctypes
import json
import locale
import subprocess

locale.setlocale(locale.LC_ALL, 'C.UTF-8')
libc = ctypes.CDLL(None)
libc.wcwidth.argtypes = [ctypes.c_wchar]
libc.wcwidth.restype = ctypes.c_int
libc.iswprint.argtypes = [ctypes.c_uint]
libc.iswprint.restype = ctypes.c_int
samples = []
for cp, introduced in [(0x11F02, '15.0'), (0x2FFC, '15.1'), (0x1C89, '16.0')]:
    samples.append({'codepoint': 'U+%04X' % cp, 'introduced': introduced,
                    'width': libc.wcwidth(chr(cp)), 'printable': bool(libc.iswprint(cp))})
print(json.dumps({'schema': 1, 'libc': subprocess.check_output(
    ['getconf', 'GNU_LIBC_VERSION'], text=True).strip(),
    'locale': locale.setlocale(locale.LC_CTYPE), 'samples': samples}, indent=2))

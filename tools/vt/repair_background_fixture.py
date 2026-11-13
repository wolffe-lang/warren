#!/usr/bin/env python3
"""Build the explicit D9 reference fixture from a spec-only background trace.

Only owned, well-formed fuzz/control inputs are accepted (64KiB maximum).
This is not a candidate-output normalizer. The pinned reference builds every
expected cell from the repaired stream; original input remains unchanged.
"""
import argparse
import hashlib
import json
from pathlib import Path

DEFAULT = ('default',)


def background_sgr(value):
    if value[0] == 'default':
        return b'\x1b[49m'
    if value[0] == 'idx':
        return b'\x1b[48;5;%dm' % value[1]
    return b'\x1b[48;2;%d;%d;%dm' % value[1:]


def sgr_background(body, background):
    if any(raw not in b'0123456789;' for raw in body):
        raise ValueError('D9 fixture tracer accepts owned semicolon SGR only')
    values = [int(part or b'0') for part in body.split(b';')]
    at = 0
    while at < len(values):
        code = values[at]
        if code in (38, 48, 58):
            if code == 58:
                raise ValueError('underline colour is outside this fixture subset')
            if at + 1 >= len(values) or values[at + 1] not in (2, 5):
                raise ValueError('unowned colour-argument form')
            count = 1 if values[at + 1] == 5 else 3
            components = values[at + 2:at + 2 + count]
            if len(components) != count or any(not 0 <= value <= 255 for value in components):
                raise ValueError('unowned colour component/domain')
            if code == 48:
                background = tuple(['idx' if count == 1 else 'rgb'] + components)
            at += count + 2
            continue
        if code in (0, 49):
            background = DEFAULT
        elif 40 <= code <= 47:
            background = ('idx', code - 40)
        elif 100 <= code <= 107:
            background = ('idx', code - 100 + 8)
        at += 1
    return background


def repair(data):
    if len(data) > 65536:
        raise ValueError('D9 fixture input exceeds 64KiB')
    output = bytearray()
    events = []
    background = DEFAULT
    saved = [DEFAULT, DEFAULT]
    alternate = False
    at = 0
    while at < len(data):
        start = at
        needs_repair = None
        if data[at] != 27:
            at += 1
            output.append(data[start])
            continue
        if at + 1 >= len(data):
            raise ValueError('incomplete escape in fixture input')
        code = data[at + 1]
        at += 2
        if code in (93, 80, 88, 94, 95):
            osc = code == 93
            while True:
                if at >= len(data):
                    raise ValueError('incomplete control string in fixture input')
                if osc and data[at] == 7:
                    at += 1
                    break
                if data[at:at + 2] == b'\x1b\\':
                    at += 2
                    break
                if data[at] == 27:
                    raise ValueError('unowned control-string escape')
                at += 1
        elif code == 91:
            body_start = at
            while at < len(data) and 0x20 <= data[at] <= 0x3F:
                at += 1
            if at >= len(data) or not 0x40 <= data[at] <= 0x7E:
                raise ValueError('incomplete/unowned CSI in fixture input')
            body, final = data[body_start:at], data[at]
            at += 1
            if final == 109 and not body.startswith((b'?', b'>', b'<', b'=')):
                background = sgr_background(body, background)
            elif final in (104, 108) and body.startswith(b'?'):
                values = body[1:].split(b';')
                if any(not value.isdigit() for value in values):
                    raise ValueError('unowned private mode form')
                for value in map(int, values):
                    if value == 1048:
                        if final == 104:
                            saved[int(alternate)] = background
                        else:
                            background = saved[int(alternate)]
                            needs_repair = '1048l'
                    elif value == 1049:
                        if final == 104:
                            saved[int(alternate)] = background
                            alternate = True
                        else:
                            alternate = False
                            background = saved[0]
                            needs_repair = '1049l'
                    elif value in (47, 1047):
                        alternate = final == 104
            elif not body and final in (115, 117):
                if final == 115:
                    saved[int(alternate)] = background
                else:
                    background = saved[int(alternate)]
                    needs_repair = 'SCORC'
            elif body == b'!' and final == 112:
                background = DEFAULT
        elif code == 55:
            saved[int(alternate)] = background
        elif code == 56:
            background = saved[int(alternate)]
            needs_repair = 'DECRC'
        elif code == 99:
            background, saved, alternate = DEFAULT, [DEFAULT, DEFAULT], False
        elif 0x20 <= code <= 0x2F:
            while at < len(data) and 0x20 <= data[at] <= 0x2F:
                at += 1
            if at >= len(data) or not 0x30 <= data[at] <= 0x7E:
                raise ValueError('incomplete escape-intermediate in fixture input')
            at += 1
        output.extend(data[start:at])
        if needs_repair:
            correction = background_sgr(background)
            output.extend(correction)
            events.append({'original_offset': at, 'restore': needs_repair,
                           'background': list(background), 'injected_hex': correction.hex()})
    return bytes(output), events


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('input', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--meta', type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() in (args.out.resolve(), args.meta.resolve()):
        parser.error('original input must not be overwritten')
    if args.input.stat().st_size > 65536:
        parser.error('D9 fixture input exceeds 64KiB')
    original = args.input.read_bytes()
    fixed, events = repair(original)
    args.out.write_bytes(fixed)
    args.meta.write_text(json.dumps({'schema': 1, 'fixture': 'D9 restored-background repair',
        'tracer_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'original_sha256': hashlib.sha256(original).hexdigest(),
        'repaired_sha256': hashlib.sha256(fixed).hexdigest(), 'injections': events}, indent=2) + '\n')
    print('D9-FIXTURE original-bytes=%d repaired-bytes=%d restores=%d' % (len(original), len(fixed), len(events)))


if __name__ == '__main__':
    main()

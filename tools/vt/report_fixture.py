"""Source-only fixtures for the owned well-formed fuzz subset, never an oracle.

Removing bold is diagnostic evidence only, not an automatic expected frame.
Tab state is derived from independently measured reference cursor columns.
"""
import re


def controls(data, pattern):
    if len(data) > 65536:
        raise ValueError('report fixture input exceeds its finite bound')
    strings = list(re.finditer(rb'\x1b\][^\x1b\x07]*(?:\x07|\x1b\\)', data))
    if len(strings) != data.count(b'\x1b]'):
        raise ValueError('unsupported OSC framing in owned report fixture')
    for match in re.finditer(pattern, data):
        if not any(part.start() <= match.start() < part.end() for part in strings):
            yield match


def without_bold(data):
    output = bytearray()
    edits = []
    end = 0
    for match in controls(data, rb'\x1b\[([0-9:;]*)m'):
        if b':' in match[1]:
            raise ValueError('owned report fixture accepts semicolon SGR only')
        values = [int(part or b'0') for part in match[1].split(b';')]
        kept = []
        at = 0
        while at < len(values):
            code = values[at]
            if code in (38, 48, 58):
                if at + 1 >= len(values) or values[at + 1] not in (2, 5):
                    raise ValueError('unsupported colour arguments')
                length = 3 if values[at + 1] == 5 else 5
                if at + length > len(values):
                    raise ValueError('truncated colour arguments')
                kept.extend(values[at:at + length])
                at += length
                continue
            if code != 1:
                kept.append(code)
            at += 1
        if kept == values:
            continue
        replacement = b'\x1b[' + b';'.join(str(value).encode() for value in kept) + b'm' if kept else b''
        output += data[end:match.start()] + replacement
        edits.append({'offset': match.start(), 'original_hex': match[0].hex(), 'replacement_hex': replacement.hex()})
        end = match.end()
    output += data[end:]
    return bytes(output), edits


def tab_operations(data):
    result = []
    for match in controls(data, rb'\x1bH|\x1bc|\x1b\[([0-9]*)g'):
        if match[0] == b'\x1bH':
            kind = 'set'
        elif match[0] == b'\x1bc':
            kind = 'clear-all'
        else:
            value = int(match[1] or b'0')
            if value not in (0, 3):
                raise ValueError('unsupported owned tab clear')
            kind = 'clear-current' if value == 0 else 'clear-all'
        result.append({'offset': match.start(), 'end': match.end(), 'kind': kind})
    return result


def column_one(operations, measured_columns):
    if len(operations) != len(measured_columns):
        raise ValueError('each tab operation needs its independently measured column')
    present = False
    for operation, col in zip(operations, measured_columns):
        if not isinstance(col, int) or not 1 <= col <= 80:
            raise ValueError('reference column outside this owned fixture size')
        if operation['kind'] == 'clear-all':
            present = False
        elif operation['kind'] == 'set' and col == 1:
            present = True
        elif operation['kind'] == 'clear-current' and col == 1:
            present = False
        elif operation['kind'] not in ('set', 'clear-current'):
            raise ValueError('unknown tab operation')
    return present

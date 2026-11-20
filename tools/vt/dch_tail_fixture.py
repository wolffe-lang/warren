"""D15 reference input: split a DCH whose vacated span starts on a second half.

`CSI n P` at column c, with cells moving, is spelled `CSI n-1 P` then `CSI P`
at the same cursor and pen. The first deletion's vacated span starts one
column further right, on a cell that cannot be a second half (the one before
it is); the second's starts on the last column, a vacated blank. So the
reference never meets the trigger, and every cell lands where one deletion of n
puts it. Only observable triggers are split (n is then at least 2). This is
specification-only reference input: the paired frames still need the per-cell
bound in tests/vt/fresh_expectations.py before either is an expected frame.
"""
from erase_extent_fixture import trace


def repair(data, cols=80, rows=24):
    output = bytearray()
    edits = []
    end = 0
    for found in trace(data, cols, rows)['dch_tail']:
        if not found['observable']:
            continue
        count = found['count']
        if count < 2 or not data[found['offset']:found['end']].endswith(b'P'):
            raise ValueError('D15 trigger is not a DCH of two or more')
        replacement = b'\x1b[%dP\x1b[P' % (count - 1)
        output += data[end:found['offset']] + replacement
        edits.append({'offset': found['offset'], 'original_hex': data[found['offset']:found['end']].hex(),
                      'replacement_hex': replacement.hex()})
        end = found['end']
    output += data[end:]
    return bytes(output), edits

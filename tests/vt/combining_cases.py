"""Owned combining-mark edge inputs; expected frames come from the reference."""
E = b'\x1b'
C = E + b'['
HEAD = E + b']2;probe\x07' + C + b'2 q'
MARK = '́'.encode()


def cases():
    body = C + b'1;5H' + MARK
    data = HEAD + body
    replay = b'warren-rec 1\nsize 12 2\no %d\n' % len(data) + data + b'\nr 6 4\n'
    return {
        'unwritten-primary': (data, 12, 2, {'kind': 'combining-unwritten'}),
        'unwritten-alternate': (HEAD + C + b'?47h' + body, 12, 2, {'kind': 'combining-unwritten-alternate'}),
        'unwritten-resized': (replay, 12, 2, {'kind': 'combining-unwritten-resize', 'target_size': [6, 4]}),
        'column-zero': (HEAD + C + b'1;0H' + MARK, 12, 2, {'kind': 'combining-no-left-cell'}),
        'after-erase': (HEAD + b'abcd' + C + b'1;4H' + C + b'2K' + MARK, 12, 2, {'kind': 'combining-erased-cell'}),
        'wide-trailing-half': (HEAD + '中'.encode() + MARK, 12, 2, {'kind': 'combining-wide-tail'}),
        'last-column-addressed': (HEAD + C + b'1;12H' + MARK, 12, 2, {'kind': 'combining-before-last-column'}),
        'last-column-pending': (HEAD + C + b'1;12HZ' + MARK, 12, 2, {'kind': 'combining-pending-last-column'}),
    }

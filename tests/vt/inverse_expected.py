"""Independent complete written frames for D9's minimal/control sequences.

No reference or candidate frame is read to construct these expectations.
"""
from expectations import blank, text_row

ATTRIBUTES = {
    'inactive-default-reset-then-inverse': 'inverse',
    'inactive-default-reset-then-uninverse': '-',
    'dec-default-restore-then-inverse': 'inverse',
    'dec-default-restore-then-uninverse': '-',
    'dec-palette-rgb-restore-then-uninverse': 'bg=idx:0',
    'dec-palette-rgb-restore-then-inverse': 'inverse,bg=idx:0',
    'repeat-alt-reset-then-uninverse': '-',
    'saved-fg-repeat-alt-then-uninverse': 'fg=idx:15',
    'unsaved-explicit-default-then-inverse': 'inverse',
    'restored-explicit-default-then-inverse': 'inverse',
    'inactive-default-reset-then-bold': 'bold',
    'inactive-default-reset-then-underline': 'underline',
}


def expected(name):
    result = blank(12, 4)
    result['title'] = b'probe'.hex()
    text_row(result, 0, [88], ATTRIBUTES[name])
    result['cursor']['col'] = 2
    return result

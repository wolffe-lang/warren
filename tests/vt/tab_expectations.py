"""Exact source witnesses for a column-1 stop omitted by reference DECTABSR."""
import copy
import re

ANCHORS = {
    'fuzz-0015': b'\x1b[5F\x1b[0K\x1bH',
    'fuzz-0019': b'\r\x08\x1bH',
    'fuzz-0020': b'\r\x1b[0L\x1bH',
    'fuzz-0024': b'\r\n\x1bH',
    'fuzz-0029': b'\r\n\x1bH',
}


def written_fuzz_tabs(name, data, frame):
    result = copy.deepcopy(frame)
    if name not in ANCHORS:
        return [], result
    anchor = data.rfind(ANCHORS[name])
    assert anchor >= 0, ('missing literal column-one witness', name)
    after = anchor + len(ANCHORS[name])
    assert b'\x1bc' not in data[after:], 'RIS would invalidate the stop witness'
    clears = list(re.finditer(rb'\x1b\[(?:3|0)?g', data[after:]))
    if name == 'fuzz-0020':
        assert len(clears) == 1 and clears[0][0] == b'\x1b[g'
        clear_at = after + clears[0].start()
        home = data.rfind(b'\x1b[0`', after, clear_at)
        assert home >= after
        tail = data[home + len(b'\x1b[0`'):clear_at]
        ascii_text = b"*W=AG4'&A|=,;~6sc9Z}"
        assert tail == ascii_text + 'ＡＡ'.encode()
        # CHA0 homes to 1; twenty ASCII columns plus two fullwidth glyphs
        # put this current-stop clear at 25, never at the retained stop1.
        assert 1 + len(ascii_text) + 4 == 25
    else:
        assert not clears, ('a later tab clear needs its own source witness', name)
    assert 1 not in result['tabs']
    result['tabs'] = sorted([1, *result['tabs']])
    return ['RPT-TABS-COLUMN-ONE'], result

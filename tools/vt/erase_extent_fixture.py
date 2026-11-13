#!/usr/bin/env python3
"""Bound D14 from owned input bytes; never inspect candidate output.

This is a finite specification trace of cursor, backgrounds and written bits,
not a renderer or a replacement reference oracle. Only the owned well-formed
fixture/fuzz subset is accepted. The actual reference must independently agree
with every declared reference extent before any field correction is allowed.
"""
from bisect import bisect_right
import copy
from dataclasses import dataclass
import json
from pathlib import Path

from repair_background_fixture import DEFAULT, sgr_background

ROOT = Path(__file__).resolve().parents[2]
RANGES = json.loads((ROOT / 'tests/vt/width-ranges.json').read_text())['ranges']
STARTS = [item[0] for item in RANGES]


def width(cp):
    index = bisect_right(STARTS, cp) - 1
    return RANGES[index][2] if index >= 0 and cp <= RANGES[index][1] else 1


@dataclass
class Cell:
    background: tuple
    width: int = 1
    contract: bool = False
    reference: bool = False
    changed: bool = False


class Row:
    def __init__(self, cols, background=DEFAULT, scroll=False):
        self.fill = background if scroll else None
        self.cells = [Cell(background) for _ in range(cols)]

    def extent(self, kind):
        return max((i + 1 for i, cell in enumerate(self.cells) if getattr(cell, kind)), default=0)


class Trace:
    def __init__(self, cols, rows):
        self.cols, self.rows = cols, rows
        self.events = []
        self.reference_exclusions = []
        self.reset()

    def reset(self):
        self.ri_offset = self.ri_tab_offset = -1
        self.screens = [[Row(self.cols) for _ in range(self.rows)] for _ in range(2)]
        self.alternate = 0
        self.row = self.col = 1
        self.top, self.bottom = 1, self.rows
        self.background = DEFAULT
        self.origin = self.insert = self.pending = self.newline = False
        self.autowrap = True
        self.tabs = set(range(9, self.cols + 1, 8))
        self.saved = [(1, 1, DEFAULT, False, False)] * 2

    @property
    def screen(self):
        return self.screens[self.alternate]

    def clear_mark_uncertainty(self):
        self.ri_offset = self.ri_tab_offset = -1

    def save(self):
        self.saved[self.alternate] = (self.row, self.col, self.background, self.origin, self.pending)

    def restore(self):
        self.clear_mark_uncertainty()
        self.row, self.col, self.background, self.origin, self.pending = self.saved[self.alternate]
        self.row = min(max(1, self.row), self.bottom if self.origin else self.rows)
        self.col = min(max(1, self.col), self.cols)
        self.pending = self.pending and self.col == self.cols

    def scroll(self, first, last, count, up, eligible):
        count = min(count, last - first + 1)
        part = self.screen[first - 1:last]
        blanks = [Row(self.cols, self.background, eligible) for _ in range(count)]
        self.screen[first - 1:last] = part[count:] + blanks if up else blanks + part[:-count]

    def linefeed(self, eligible=True):
        self.clear_mark_uncertainty()
        self.pending = False
        if self.row == self.bottom:
            self.scroll(self.top, self.bottom, 1, True, eligible)
        elif self.row < self.rows:
            self.row += 1
        if self.newline:
            self.col = 1

    def reverse(self, offset=0):
        self.ri_offset, self.ri_tab_offset = offset, -1
        self.pending = False
        if self.row == self.top:
            self.scroll(self.top, self.bottom, 1, False, True)
        elif self.row > 1:
            self.row -= 1

    def blank(self, row, index, preserve=False, background=None):
        old = row.cells[index]
        bg = self.background if background is None else background
        row.cells[index] = Cell(bg, contract=old.contract if preserve else False,
                               reference=old.reference if preserve else False,
                               changed=old.changed or (row.fill is not None and bg != row.fill))

    def break_print_pair(self, row, index):
        cell = row.cells[index]
        if cell.width == 2 and index + 1 < self.cols:
            self.blank(row, index + 1, preserve=index + 2 != self.cols)
        elif cell.width == 0 and index > 0:
            if index + 1 == self.cols:
                self.blank(row, index - 1, preserve=True, background=row.cells[index - 1].background)
            else:
                self.blank(row, index - 1, preserve=True)

    def shift(self, count, insert):
        row = self.screen[self.row - 1]
        first = self.col - 1
        count = min(count, self.cols - first)
        blanks = [Cell(self.background, contract=insert, reference=insert, changed=True) for _ in range(count)]
        if insert:
            row.cells[first:] = blanks + row.cells[first:self.cols - count]
        else:
            row.cells[first:] = row.cells[first + count:] + blanks
        for i, cell in enumerate(row.cells):
            if cell.width == 2 and (i + 1 == self.cols or row.cells[i + 1].width != 0):
                self.blank(row, i, preserve=insert or i + 2 != self.cols)
            elif cell.width == 0 and (i == 0 or row.cells[i - 1].width != 2):
                self.blank(row, i, preserve=True)

    def print(self, cp, offset=0):
        if 0xFFF9 <= cp <= 0xFFFB:
            return
        size = width(cp)
        if size == 0:
            if cp != 0x200D and self.ri_offset >= 0 and self.ri_tab_offset >= 0:
                self.reference_exclusions.append({'name': 'RI-HT-combining-open',
                    'ri_offset': self.ri_offset, 'ht_offset': self.ri_tab_offset,
                    'mark_offset': offset, 'scalar': 'U+%04X' % cp})
            if cp == 0x200D or (self.col == 1 and not self.pending):
                return
            row = self.screen[self.row - 1]
            index = self.col - 1 if self.pending else self.col - 2
            if row.cells[index].width == 0:
                index -= 1
            row.cells[index].contract = row.cells[index].reference = True
            return
        self.clear_mark_uncertainty()
        if self.pending and self.autowrap:
            self.col = 1
            self.linefeed()
        if size == 2 and self.cols == 1:
            size = 1
        if size == 2 and self.col == self.cols:
            if not self.autowrap:
                return
            self.col = 1
            self.linefeed()
        if self.insert:
            self.shift(size, True)
        row = self.screen[self.row - 1]
        first = self.col - 1
        self.break_print_pair(row, first)
        if size == 2:
            self.break_print_pair(row, first + 1)
        for index in range(first, first + size):
            old = row.cells[index]
            row.cells[index] = Cell(self.background, size if index == first else 0, True, True,
                old.changed or (row.fill is not None and self.background != row.fill))
        self.pending = self.col + size > self.cols
        self.col = min(self.cols, self.col + size)

    def erase(self, row_number, first, last, kind, offset):
        row = self.screen[row_number - 1]
        cells = row.cells[first - 1:last]
        guarded = (kind in ('X', 'K') and last < self.cols and row.fill is not None and
                   self.background == row.fill and
                   all(cell.background == row.fill and not cell.changed for cell in cells))
        if guarded:
            self.events.append({'offset': offset, 'screen': self.alternate,
                                'row': row_number, 'first': first, 'last': last,
                                'fill_background': list(row.fill), 'operation': kind})
        if row.cells[first - 1].width == 0 and first > 1:
            self.blank(row, first - 2)
        if row.cells[last - 1].width == 2 and last < self.cols:
            self.blank(row, last)
        for index in range(first - 1, last):
            self.blank(row, index)
            row.cells[index].contract = last < self.cols
            row.cells[index].reference = last < self.cols and not guarded

    def csi(self, body, final, offset):
        if final == 'm' and not body.startswith(('?', '>', '<', '=')):
            self.background = sgr_background(body.encode(), self.background)
            return
        if final == 'q' and body.endswith(' '):
            return
        if final == 'p' and body == '!':
            self.background = DEFAULT
            self.top, self.bottom, self.origin, self.insert = 1, self.rows, False, False
            return
        private = body.startswith('?')
        raw = body[1:] if private else body
        if any(ch not in '0123456789;' for ch in raw):
            raise ValueError('unowned CSI parameter grammar')
        parts = [int(part or 0) for part in raw.split(';')]
        if len(parts) > 32 or any(value > 65535 for value in parts):
            raise ValueError('unowned CSI parameter bound')
        value = parts[0] or 1
        if private and final in ('h', 'l'):
            active = final == 'h'
            for mode in parts:
                if mode == 6:
                    self.clear_mark_uncertainty()
                    self.origin = active
                    self.row, self.col, self.pending = (self.top if active else 1), 1, False
                elif mode == 7:
                    self.autowrap = active
                elif mode == 1048:
                    self.save() if active else self.restore()
                elif mode == 1049:
                    self.clear_mark_uncertainty()
                    if active:
                        self.save()
                        self.alternate = 1
                        self.screens[1] = [Row(self.cols, self.background) for _ in range(self.rows)]
                        self.pending = False
                    else:
                        self.alternate = 0
                        self.restore()
                elif mode in (47, 1047):
                    if mode == 1047 and not active:
                        if self.alternate:
                            self.clear_mark_uncertainty()
                        self.screens[1] = [Row(self.cols, self.background) for _ in range(self.rows)]
                    self.alternate = int(active)
                elif mode not in (1, 12, 25, 45, 66, 69, 1000, 1002, 1003, 1004, 1006, 1007, 1015, 2004, 2026):
                    raise ValueError('unowned private mode')
            return
        if private:
            raise ValueError('unowned private CSI')
        if final in ('h', 'l'):
            if parts == [4]:
                self.insert = final == 'h'
            elif parts == [20]:
                self.newline = final == 'h'
            else:
                raise ValueError('unowned ANSI mode')
        elif final in ('H', 'f', 'd'):
            self.clear_mark_uncertainty()
            self.row = min(max((self.top if self.origin else 1) + value - 1, self.top if self.origin else 1),
                           self.bottom if self.origin else self.rows)
            if final != 'd':
                self.col = min(self.cols, (parts[1] or 1) if len(parts) > 1 else 1)
            self.pending = False
        elif final in 'ABEF':
            self.clear_mark_uncertainty()
            amount = value if final in 'BE' else -value
            low = self.top if amount < 0 and self.row >= self.top else 1
            high = self.bottom if amount > 0 and self.row <= self.bottom else self.rows
            self.row = min(high, max(low, self.row + amount))
            if final in 'EF':
                self.col = 1
            self.pending = False
        elif final in 'CDG`':
            self.clear_mark_uncertainty()
            self.col = min(self.cols, max(1, value if final in 'G`' else self.col + (value if final == 'C' else -value)))
            self.pending = False
        elif final == 'r':
            bottom = min(self.rows, (parts[1] or self.rows) if len(parts) > 1 else self.rows)
            if value < bottom:
                self.clear_mark_uncertainty()
                self.top, self.bottom = value, bottom
                self.row, self.col, self.pending = (value if self.origin else 1), 1, False
        elif final in ('X', 'K', 'J'):
            self.clear_mark_uncertainty()
            self.pending = False
            mode = parts[0]
            if final == 'X':
                self.erase(self.row, self.col, min(self.cols, self.col + value - 1), final, offset)
            elif final == 'K':
                first, last = (self.col, self.cols) if mode == 0 else (1, self.col if mode == 1 else self.cols)
                self.erase(self.row, first, last, final, offset)
            elif mode in (0, 1, 2):
                for row in range(1, self.rows + 1):
                    if mode == 2 or (mode == 0 and row >= self.row) or (mode == 1 and row <= self.row):
                        first = self.col if mode == 0 and row == self.row else 1
                        last = self.col if mode == 1 and row == self.row else self.cols
                        self.erase(row, first, last, final, offset)
        elif final in ('@', 'P'):
            self.clear_mark_uncertainty()
            self.pending = False
            self.shift(value, final == '@')
        elif final in ('L', 'M'):
            if self.top <= self.row <= self.bottom:
                self.clear_mark_uncertainty()
                self.pending, self.col = False, 1
                self.scroll(self.row, self.bottom, value, final == 'M', False)
        elif final in ('S', 'T'):
            self.scroll(self.top, self.bottom, value, final == 'S', True)
        elif final == 'g':
            if parts[0] == 0:
                self.tabs.discard(self.col)
            elif parts[0] == 3:
                self.tabs.clear()
        elif final in ('s', 'u'):
            self.save() if final == 's' else self.restore()
        elif final not in ('c', 'n'):
            raise ValueError('unowned CSI final')


def trace(data, cols=80, rows=24):
    if len(data) > 65536 or not 1 <= cols <= 320 or not 1 <= rows <= 90:
        raise ValueError('D14 source trace bound')
    try:
        data.decode('utf-8')
    except UnicodeDecodeError as error:
        raise ValueError('unowned non-UTF8 input') from error
    state = Trace(cols, rows)
    at = 0
    while at < len(data):
        start, code = at, data[at]
        at += 1
        if code == 27:
            if at == len(data):
                raise ValueError('truncated escape')
            code = data[at]
            at += 1
            if code == 91:
                begin = at
                while at < len(data) and 0x20 <= data[at] <= 0x3F:
                    at += 1
                if at == len(data) or not 0x40 <= data[at] <= 0x7E:
                    raise ValueError('truncated CSI')
                state.csi(data[begin:at].decode('ascii'), chr(data[at]), start)
                at += 1
            elif code == 93:
                while True:
                    if at == len(data):
                        raise ValueError('truncated OSC')
                    if data[at] == 7:
                        at += 1
                        break
                    if data[at:at + 2] == b'\x1b\\':
                        at += 2
                        break
                    at += 1
            elif code == 55:
                state.save()
            elif code == 56:
                state.restore()
            elif code in (68, 69):
                if code == 69:
                    state.col = 1
                state.linefeed(code == 69)
            elif code == 77:
                state.reverse(start)
            elif code == 72:
                state.tabs.add(state.col)
            elif code == 99:
                state.reset()
            elif code not in (61, 62):
                raise ValueError('unowned escape')
        elif code in (10, 11, 12):
            state.linefeed()
        elif code == 13:
            state.clear_mark_uncertainty()
            state.col, state.pending = 1, False
        elif code == 8:
            state.clear_mark_uncertainty()
            state.col, state.pending = max(1, state.col - 1), False
        elif code == 9:
            if state.ri_offset >= 0:
                state.ri_tab_offset = start
            state.col = min((stop for stop in state.tabs if stop > state.col), default=cols)
        elif code < 32 or code == 127:
            continue
        else:
            length = 1 if code < 128 else 2 if code < 224 else 3 if code < 240 else 4
            state.print(ord(data[start:start + length].decode('utf-8')), start)
            at = start + length
    changed = []
    for index, row in enumerate(state.screen):
        reference, contract = row.extent('reference'), row.extent('contract')
        if reference != contract:
            changed.append({'row': index + 1, 'reference_extent': reference, 'contract_extent': contract})
    return {'schema': 1, 'events': state.events, 'rows': changed,
            'reference_exclusions': state.reference_exclusions,
            'cursor': [state.row, state.col], 'active_alternate': bool(state.alternate)}


def apply(data, reference):
    """Permit only the source-declared extent deltas on an independent frame."""
    model = trace(data, *reference['size'])
    result = copy.deepcopy(reference)
    for row in model['rows']:
        index = row['row'] - 1
        if reference['extents'][index] != row['reference_extent']:
            raise ValueError('D14 source/reference extent disagreement')
        result['extents'][index] = row['contract_extent']
    return result, model

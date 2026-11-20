#!/usr/bin/env python3
"""A wide scalar that cannot fit in the last column while autowrap is off.

Every expected cell, rendition, cursor and mode comes from the pinned reference,
dumped live; only D7's unreportable synchronized-output mode is set to its
written reset. warren's frame for the same bytes must equal it cell for cell.

What the reference does, measured: the scalar clears a pending wrap. If the
token just before it was a wide glyph written in the same run of printing,
it replaces that glyph where the glyph starts; after anything else (a narrow
scalar, a mark, a control, an escape or a string, DEL, an encoded C1, or a
wide scalar that was itself dropped) it is dropped, and REP then repeats the
dropped scalar. The reference reads its input in pieces and a piece boundary
breaks the run as well; these streams are written to it whole (warren#28).
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import run as oracle  # noqa: E402
import screen  # noqa: E402

C = '\x1b['
HEAD = '\x1b]2;wide-pending\x1b\\'
OFF = C + '?7l'
ON = C + '?7h'


def at(col, row=1):
    return C + '%d;%dH' % (row, col)


# name: (stream after the title, the reference's pending wrap when the row
# binds it, columns, rows). Columns and rows default to 8 by 3.
CASES = {
    # The minimal streams of the issue, at 80 columns.
    'issue-narrow-pending-wide-80': (OFF + at(80) + 'x中', 0, 80, 24),
    'issue-wide-pending-wide-80': (OFF + at(79, 11) + '文あ', 0, 80, 24),
    # The issue's streams that already agreed.
    'off-narrow-one-before-wide': (OFF + at(7) + 'x中', None),
    'off-wide-fills-edge': (OFF + at(7) + '中', 1),
    'off-wide-at-edge-without-pending': (OFF + at(8) + '中', 0),
    'off-two-wide-from-five': (OFF + at(5) + '中中', 1),
    'off-two-wide-from-six': (OFF + at(6) + '中中', 0),
    'off-ignored-wide-then-narrow': (OFF + at(8) + '中x', 1),
    'on-narrow-pending-wide': (at(8) + 'x中', 0),
    'off-narrow-pending-narrow': (OFF + at(8) + 'xy', 1),
    # A pending wrap, then a wide scalar.
    'off-narrow-pending-wide': (OFF + at(8) + 'x中', 0),
    'off-wide-pending-wide': (OFF + at(7) + '文あ', 0),
    'off-narrow-pending-two-wide': (OFF + at(8) + 'x中あ', 0),
    'off-wide-pending-two-wide': (OFF + at(7) + '文あ中', 0),
    'off-narrow-pending-wide-reenable-print': (OFF + at(8) + 'x中' + ON + 'A', 1),
    'off-wide-pending-wide-reenable-print': (OFF + at(7) + '文あ' + ON + 'A', 1),
    'off-pending-attributed-wide': (OFF + at(7) + C + '31;42m文' + C + '32;44mあ', 0),
    'off-wide-run-of-four': (OFF + at(7) + '文あ中い', 0),
    'off-fullwidth-latin': (OFF + at(7) + 'ＡＢ', 0),
    'off-emoji': (OFF + at(7) + '\U0001F600\U0001F601', 0),
    # Replacement where the wide glyph started, before the last column too.
    'off-wide-before-last-column-wide': (OFF + at(6) + '中あ', 0),
    'off-wide-before-last-column-sgr-wide': (OFF + at(6) + '中' + C + 'mあ', 0),
    'off-wide-before-last-column-mark': (OFF + at(6) + '中あ́', 0),
    'off-three-wide-from-five': (OFF + at(5) + '中あい', 0),
    'off-three-wide-from-four': (OFF + at(4) + '中中あ', 0),
    'off-three-wide-from-six': (OFF + at(6) + '中あい', 0),
    'off-insert-wide-replaced': (OFF + at(6) + 'xyz' + at(6) + C + '4h中あ', 0),
    'off-insert-pending-wide-replaced': (OFF + at(7) + C + '4h文あい', 0),
    'off-wide-mark-after-replacement': (OFF + at(7) + '文あ́', 0),
    'off-alternate-wide-pending-wide': (C + '?1049h' + OFF + at(7) + '文あ', 0),
    'off-alternate-narrow-pending-wide': (C + '?1049h' + OFF + at(8) + 'x中', 0),
    'off-wrapped-row-wide-pending-wide': (at(1) + 'abcdefghij' + OFF + at(7) + '文あ', 0),
    # Anything between the two wide scalars makes the second one dropped.
    'off-wide-sgr-wide': (OFF + at(7) + '文' + C + 'mあ', 0),
    'off-wide-title-wide': (OFF + at(7) + '文\x1b]2;t\x1b\\あ', 0),
    'off-wide-title-bel-wide': (OFF + at(7) + '文\x1b]2;t\x07あ', 0),
    'off-wide-bel-wide': (OFF + at(7) + '文\x07あ', 0),
    'off-wide-nul-wide': (OFF + at(7) + '文\x00あ', 0),
    'off-wide-can-wide': (OFF + at(7) + '文\x18あ', 0),
    'off-wide-sub-wide': (OFF + at(7) + '文\x1aあ', 0),
    'off-wide-del-wide': (OFF + at(7) + '文\x7fあ', 0),
    'off-wide-c1-wide': (OFF + at(7) + '文\u0085あ', 0),
    'off-wide-tab-wide': (OFF + at(7) + '文\tあ', 0),
    'off-wide-mode-wide': (OFF + at(7) + '文' + C + '?25hあ', 0),
    'off-wide-unknown-mode-wide': (OFF + at(7) + '文' + C + '?999hあ', 0),
    'off-wide-ignored-csi-wide': (OFF + at(7) + '文' + C + ';' * 40 + 'mあ', 0),
    'off-wide-designate-wide': (OFF + at(7) + '文\x1b(Bあ', 0),
    'off-wide-escape-nonascii-wide': (OFF + at(7) + '文\x1b中あ', 0),
    'off-wide-csi-nonascii-wide': (OFF + at(7) + '文' + C + '1中あ', 0),
    'off-wide-apc-wide': (OFF + at(7) + '文\x1b_x\x1b\\あ', 0),
    'off-wide-dcs-wide': (OFF + at(7) + '文\x1bPq\x1b\\あ', 0),
    'off-wide-save-restore-wide': (OFF + at(7) + '文\x1b7\x1b8あ', 0),
    'off-wide-mark-wide': (OFF + at(7) + '文́あ', 0),
    'off-wide-vs16-wide': (OFF + at(7) + '文️あ', 0),
    'off-wide-zwj-wide': (OFF + at(7) + '文‍あ', 0),
    'off-wide-annotation-wide': (OFF + at(7) + '文￹あ', 0),
    'off-wide-narrow-wide': (OFF + at(7) + '文x中', 0),
    'off-wide-wide-narrow-wide': (OFF + at(7) + '文あx中', 0),
    'off-wide-sgr-wide-wide': (OFF + at(7) + '文' + C + 'mあ中', 0),
    'off-wide-wide-sgr-wide': (OFF + at(7) + '文あ' + C + 'm中', 0),
    'off-wide-reenable-then-off-wide': (OFF + at(7) + '文' + ON + OFF + 'あ', 0),
    'off-narrow-sgr-wide': (OFF + at(8) + 'x' + C + 'm中', 0),
    'off-narrow-title-wide': (OFF + at(8) + 'x\x1b]2;t\x1b\\中', 0),
    'off-two-narrow-wide': (OFF + at(7) + 'ab中', 0),
    'off-wide-ascii-run-wide': (OFF + at(1) + '中abcde中', 0),
    'off-ascii-run-two-wide': (OFF + at(3) + 'abcde中あ', 0),
    # What a dropped wide scalar leaves behind.
    'off-narrow-pending-wide-mark': (OFF + at(8) + 'x中́', 0),
    'off-dropped-wide-rep': (OFF + at(3) + 'abcde中' + C + 'b', 0),
    'off-narrow-pending-wide-rep': (OFF + at(8) + 'x中' + C + 'b', None),
    # Autowrap on again afterwards: the pending wrap decides the next print.
    'off-wide-sgr-wide-reenable-wide': (OFF + at(7) + '文' + C + 'mあ' + ON + 'い', 0),
    'off-wide-wide-reenable-wide': (OFF + at(7) + '文あ' + ON + 'い', 0),
    'off-wide-narrow-reenable-wide': (OFF + at(7) + '文x' + ON + '中', 0),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='work directory (default target/wide-pending/<runner>)')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error('vt-dump command required')
    runner = 'lupin' if Path(args.command[0]).name == 'lupin' else 'native'
    base = args.out or ROOT / 'target/wide-pending' / runner
    base.mkdir(parents=True, exist_ok=True)
    failed = 0
    with oracle.Display() as display:
        for name, case in CASES.items():
            body, pending = case[0], case[1]
            cols, rows = (case[2], case[3]) if len(case) > 2 else (8, 3)
            work = base / name
            work.mkdir(parents=True, exist_ok=True)
            data = (HEAD + body).encode()
            source = work / 'input.in'
            source.write_bytes(data)
            try:
                expected = oracle.dump(display, source.resolve(), cols, rows, work.resolve())
            except (oracle.OracleError, ValueError, subprocess.TimeoutExpired) as error:
                print('FAIL wide-pending-%s reference %s' % (name, error), flush=True)
                failed += 1
                continue
            if pending is not None and expected['cursor']['pending_wrap'] != pending:
                print('FAIL wide-pending-%s reference-pending-wrap expected %d got %d' % (
                    name, pending, expected['cursor']['pending_wrap']), flush=True)
                failed += 1
                continue
            if expected['modes']['synchronized-output'] != '?':
                print('FAIL wide-pending-%s reference-reports-mode-2026' % name, flush=True)
                failed += 1
                continue
            expected['modes']['synchronized-output'] = 0
            (work / 'reference.json').write_text(json.dumps(expected, indent=1) + '\n')
            result = subprocess.run(args.command + ['vt-dump', '--cols', str(cols), '--rows', str(rows),
                                                    '--history-bytes', '1024'],
                                    input=data, capture_output=True, cwd=ROOT, timeout=300)
            (work / 'actual.screen').write_bytes(result.stdout)
            if result.returncode or result.stderr:
                print('FAIL wide-pending-%s candidate-exit=%d stderr=%r' % (
                    name, result.returncode, result.stderr[:400]), flush=True)
                failed += 1
                continue
            differences = screen.compare(expected, screen.loads(result.stdout.decode()))
            for kind, detail in differences:
                print('FAIL wide-pending-%s %s %s' % (name, kind, detail), flush=True)
            failed += bool(differences)
            if not differences:
                print('PASS wide-pending-%s whole-screen D7 cursor=%d;%d pending=%d' % (
                    name, expected['cursor']['row'], expected['cursor']['col'],
                    expected['cursor']['pending_wrap']), flush=True)
    print('WIDE-PENDING runner=%s cases=%d failed=%d display-retries=%d' % (
        runner, len(CASES), failed, len(display.retries)), flush=True)
    failed += oracle.rate_verdict(display)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

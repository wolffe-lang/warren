#!/usr/bin/env python3
"""The reference runs with jump scroll off, so its answer is one answer.

With jump scroll on, the reference batches the line feeds it has buffered into
one scroll, and whether a later erase counts its cells as written depends on
whether that row's scroll was still waiting in a batch: on where its reads
split the input, which is timing. The same bytes then gave different extents
from run to run, and the D14 divergence was this effect (warren#25). With jump
scroll off, an erase on a row made by a scroll counts its cells as written,
every time, as warren's own contract does.

Each stream is dumped three times through the oracle's own dump. Needs the
pinned image: the reference terminal and a virtual display.
"""
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
for part in ('tools/oracle', 'tests/vt'):
    sys.path.insert(0, str(ROOT / part))
import run as oracle  # noqa: E402
from origin_fixture import dump  # noqa: E402

C = b'\x1b['
SCROLLED = b'\r\n' * 30  # the last seven feeds scroll; row 24 is made by a scroll
ROWS = {
    'erase-on-a-scroll-made-row-counts-written': (SCROLLED + C + b'24;1H' + C + b'5X', 24, 5),
    'erase-after-an-erase-in-display-counts-written': (SCROLLED + C + b'2J' + C + b'24;1H' + C + b'5X', 24, 5),
}
DUMPS = 3


def main():
    failed = []
    scratch = ROOT / 'target/tmp'
    scratch.mkdir(parents=True, exist_ok=True)
    base = Path(tempfile.mkdtemp(prefix='jump-scroll-', dir=scratch))
    try:
        with oracle.Display() as display:
            for name, (data, row, want) in ROWS.items():
                source = base / (name + '.in')
                source.write_bytes(data)
                got = []
                for i in range(DUMPS):
                    try:
                        frame = dump(display, source.resolve(), 80, 24, (base / ('%s-%d' % (name, i))).resolve())
                        got.append(frame['extents'][row - 1])
                    except (oracle.OracleError, OSError, ValueError) as error:
                        got.append('error: %s' % str(error)[:80])
                ok = got == [want] * DUMPS
                print('%s jump-scroll %s row=%d extents=%s want=%d' % ('PASS' if ok else 'FAIL', name, row, got, want),
                      flush=True)
                if not ok:
                    failed.append(name)
    finally:
        shutil.rmtree(base)
    print('PASS jump-scroll-off %s' % ' '.join(ROWS) if not failed else 'FAIL jump-scroll rows: %s' % ' '.join(failed))
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

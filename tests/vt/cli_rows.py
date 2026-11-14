#!/usr/bin/env python3
"""Exercise the real dump CLI over stdin/files and explicit recordings."""
import argparse
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools/oracle'))
import screen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-default', action='store_true')
    parser.add_argument('command', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    assert args.command

    def run(options=(), data=b'', code=0, configured=True):
        command = args.command + ['vt-dump']
        if configured:
            command += ['--history-bytes', '4096']
        result = subprocess.run(command + list(options), cwd=ROOT, input=data,
                                capture_output=True, timeout=180)
        assert result.returncode == code, ('cli-exit', options, result.returncode,
                                            result.stdout[:1000], result.stderr[:1000])
        if code:
            assert not result.stdout, ('cli-error-stdout', options, result.stdout[:1000])
            return result
        assert not result.stderr, result.stderr
        parsed = screen.loads(result.stdout.decode('utf-8'))
        return result.stdout, parsed

    if args.native_default:
        _, default = run(configured=False)
        assert default['size'] == [80, 24]
    raw = b'A\0\xff\xe4\xb8\xad'
    out, parsed = run(['--cols', '8', '--rows', '3'], raw)
    assert parsed['size'] == [8, 3]
    assert [c[1] for c in parsed['rows'][0][:4]] == ['U+0041', 'U+FFFD', 'U+4E2D', '-']
    assert parsed['cursor']['row'] == 1 and parsed['cursor']['col'] == 5
    root = ROOT / 'target/vt-cli-fixtures'
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        directory = Path(temporary)
        source = directory / 'binary.in'
        source.write_bytes(raw)
        file_out, _ = run(['--cols', '8', '--rows', '3', str(source)])
        dash_out, _ = run(['--cols', '8', '--rows', '3', '-'], raw)
        assert out == file_out == dash_out, 'cli-file-stdin-identity'
        long_out, long_screen = run(['--cols', '10', '--rows', '3'], b'x' * 5000 + b'\rZ')
        source.write_bytes(b'x' * 5000 + b'\rZ')
        assert run(['--cols', '10', '--rows', '3', str(source)])[0] == long_out
        assert long_screen['rows'][2][0][1] == 'U+005A'
        # The skipped payload has eight bytes; one is a literal line feed.
        recording = (b'warren-rec 1\nsize 4 1\no 4\na\r\nb\n' +
                     b'i 8\n\x1b[2JNO!\n\n' + b'r 4 3\no 1\nZ\n')
        replay_out, replay = run(['--replay'], recording)
        assert replay['size'] == [4, 3]
        assert replay['rows'][0][0][1] == 'U+0061'
        assert [c[1] for c in replay['rows'][1][:2]] == ['U+0062', 'U+005A']
        assert replay['cursor']['row'] == 2 and replay['cursor']['col'] == 3
        source.write_bytes(recording)
        assert run(['--replay', str(source)])[0] == replay_out
        _, literal = run(['--cols', '20', '--rows', '3'], b'warren-rec 1\n')
        assert literal['rows'][0][0][1] == 'U+0077', 'cli-raw-never-autodetects'
        for options in (['--cols'], ['--cols', '0'], ['--rows', '-1'], ['--cols', '262145'],
                        ['--cols', '9' * 40], ['--unknown'], ['--replay', '--cols', '4'],
                        ['--history-bytes', '-1'], ['--history-bytes', '8388609'],
                        [str(source), str(source)]):
            run(options, code=2)
        run([str(directory / 'missing')], code=1)
        invalid = [b'', b'warren-rec 2\nsize 4 1\n', b'warren-rec 1\nsize 0 1\n',
                   b'warren-rec 1\nsize 4 1\no 4\nab\n',
                   b'warren-rec 1\nsize 4 1\no 1\naX',
                   b'warren-rec 1\nsize 4 1\nx 1\n',
                   b'warren-rec 1\nsize 4 1\nsize 4 1\n',
                   b'warren-rec 1\nsize 4 1\nr 262145 1\n',
                   b'warren-rec 1\nsize 4 1\no ' + b'9' * 80 + b'\n']
        for data in invalid:
            run(['--replay'], data, code=2)
    unknown = subprocess.run(args.command + ['unknown'], cwd=ROOT, capture_output=True, timeout=180)
    assert unknown.returncode == 2 and not unknown.stdout
    # With no arguments warren attaches, which needs a terminal: here there is none.
    bare = subprocess.run(args.command, cwd=ROOT, capture_output=True, timeout=180, stdin=subprocess.DEVNULL)
    assert bare.returncode != 0 and not bare.stdout, bare
    print('PASS vt-cli raw binary stdin file chunks usage replay malformed')


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
"""Stage the pinned wolf, lupin and std into .wolf-bin/; refuse anything else.

Archives are bound to wolf-toolchain.toml by SHA-256, read twice. The std tree
is fetched at its pinned commit with git, which checks the objects against the
commit id; the commit fetched must be the pin. The std the wolf archive
bundles is removed first, so two commits' files are never mixed.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import tarfile
import tomllib

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def git(*args, cwd):
    return subprocess.run(['git', '-c', 'commit.gpgsign=false', *args], cwd=cwd, check=True,
                          capture_output=True, text=True).stdout.strip()


def stage_std(pin, out, work):
    repo = work / 'std-fetch'
    if repo.exists():
        shutil.rmtree(repo)
    repo.mkdir(parents=True)
    git('init', '-q', '.', cwd=repo)
    for attempt in range(3):
        try:
            git('fetch', '-q', '--depth', '1', 'https://github.com/' + pin['repo'], pin['rev'], cwd=repo)
            break
        except subprocess.CalledProcessError as error:
            if attempt == 2:
                raise ValueError('std fetch failed: ' + error.stderr.strip())
    if git('rev-parse', 'FETCH_HEAD', cwd=repo) != pin['rev']:
        raise ValueError('fetched std commit is not the pin')
    if git('rev-parse', 'FETCH_HEAD^{tree}', cwd=repo) != pin['tree']:
        raise ValueError('fetched std tree is not the pin')
    archive = work / 'std.tar'
    with archive.open('wb') as stream:
        subprocess.run(['git', 'archive', 'FETCH_HEAD', 'std'], cwd=repo, check=True, stdout=stream)
    with tarfile.open(archive) as tar:
        tar.extractall(out, filter='data')
    (out / 'std' / 'STD-REV').write_text(pin['rev'] + '\n')
    shutil.rmtree(repo)
    archive.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive-dir', type=Path, help='take archives from here, not the network')
    parser.add_argument('--out', type=Path, default=ROOT / '.wolf-bin')
    args = parser.parse_args()
    arch = {'arm64': 'aarch64', 'aarch64': 'aarch64', 'x86_64': 'x86_64'}[platform.machine()]
    target = arch + ('-apple-darwin' if platform.system() == 'Darwin' else '-unknown-linux-gnu')
    pins = tomllib.loads((ROOT / 'wolf-toolchain.toml').read_text())
    stamp = json.dumps({'target': target, 'pins': pins}, sort_keys=True)
    stamp_file = args.out / 'STAMP'
    if stamp_file.exists() and stamp_file.read_text() == stamp:
        print('PASS toolchain-digests target=%s (already staged)' % target)
        return
    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True)
    downloads = args.out / 'downloads'
    downloads.mkdir()
    result = {'schema': 1, 'target': target, 'tools': {}}
    for name in ('wolf', 'lupin'):
        pin = pins[name]
        filename = f'{name}-{pin["version"]}-{target}.tar.gz'
        archive = downloads / filename
        if args.archive_dir and (args.archive_dir / filename).exists():
            shutil.copy(args.archive_dir / filename, archive)
        else:
            url = f'https://github.com/{pin["repo"]}/releases/download/v{pin["version"]}/{filename}'
            subprocess.run(['curl', '-fLsS', '--retry', '3', '--connect-timeout', '30',
                            '--max-time', '600', url, '-o', str(archive)], check=True)
        first, second = digest(archive), digest(archive)
        if first != pin[target] or second != first:
            raise ValueError('archive digest mismatch: ' + filename)
        staged = args.out / f'{name}-{pin["version"]}-{target}'
        # Archives have a single known root. Reject links/traversal before extraction.
        with tarfile.open(archive) as tar:
            for member in tar.getmembers():
                parts = Path(member.name).parts
                if (not parts or parts[0] != staged.name or '..' in parts or
                        member.name.startswith('/') or not (member.isdir() or member.isfile())):
                    raise ValueError('unsafe archive member: ' + member.name)
            tar.extractall(args.out, filter='data')
        exe = staged / name
        version = subprocess.check_output([str(exe), '--version'], text=True).strip().splitlines()[0]
        if not version.startswith(f'{name} {pin["version"]} '):
            raise ValueError('unexpected binary version: ' + version)
        result['tools'][name] = {'archive_sha256': first, 'root': str(staged.resolve()),
                                 'version': version}
    wolf_root = Path(result['tools']['wolf']['root'])
    bundled = wolf_root / 'std' / 'STD-REV'
    result['bundled_std'] = bundled.read_text().strip() if bundled.exists() else None
    if (wolf_root / 'std').exists():
        shutil.rmtree(wolf_root / 'std')
    stage_std(pins['std'], args.out, downloads)
    result['std'] = {'rev': pins['std']['rev'], 'root': str((args.out / 'std').resolve())}
    shutil.rmtree(downloads)
    (args.out / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')
    stamp_file.write_text(stamp)
    print('PASS toolchain-digests target=%s bundled_std=%s staged_std=%s' % (
        target, result['bundled_std'], pins['std']['rev']))


if __name__ == '__main__':
    main()

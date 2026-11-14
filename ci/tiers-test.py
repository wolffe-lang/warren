#!/usr/bin/env python3
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


def tiers_module():
    sys.path.insert(0, str(ROOT / 'ci'))
    try:
        import tiers
    finally:
        sys.path.pop(0)
    return tiers


class Tiers(unittest.TestCase):
    def plan(self, event, labels='', jobs=''):
        return subprocess.run([sys.executable, '-I', str(ROOT / 'ci/tiers.py'), 'plan',
            '--event', event, '--labels', labels, '--jobs', jobs], capture_output=True, text=True)

    def test_unlabelled_is_local_only(self):
        p = self.plan('pull_request')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout.splitlines()[-1]), {'tier': 'local', 'jobs': ['plan-test']})

    def test_pr_and_full(self):
        p = self.plan('pull_request', 'ci')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout.splitlines()[-1]), {'tier': 'pr', 'jobs': ['plan-test', 'linux']})
        p = self.plan('pull_request', 'full-matrix')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout.splitlines()[-1]), {'tier': 'full', 'jobs': ['plan-test', 'linux', 'macos']})

    def test_nightly_and_release(self):
        for event in ('schedule', 'push', 'workflow_dispatch'):
            p = self.plan(event)
            self.assertEqual(p.returncode, 0, p.stderr)
            self.assertEqual(json.loads(p.stdout.splitlines()[-1])['tier'], 'full')

    def test_unknown_dispatch_job_refused(self):
        self.assertNotEqual(self.plan('workflow_dispatch', jobs='not-a-job').returncode, 0)

    def test_partial_dispatch(self):
        p = self.plan('workflow_dispatch', jobs='macos')
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout.splitlines()[-1]), {'tier': 'partial', 'jobs': ['macos']})

    def test_verdict_rejects_skipped_selected_job(self):
        needs = {'plan': {'result': 'success', 'outputs': {'tier': 'pr', 'jobs': '["linux"]'}},
                 'linux': {'result': 'skipped'}, 'macos': {'result': 'skipped'},
                 'plan-test': {'result': 'success'}}
        p = subprocess.run([sys.executable, '-I', str(ROOT / 'ci/tiers.py'), 'verdict'],
            env=dict(os.environ, NEEDS=json.dumps(needs)), capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('linux', p.stdout + p.stderr)

    def test_plan_prints_what_it_held(self):
        p = subprocess.run([sys.executable, '-I', str(ROOT / 'ci/tiers.py'), 'plan', '--event', 'pull_request',
            '--labels', 'full-matrix', '--action', 'labeled', '--label', 'full-matrix'], capture_output=True, text=True)
        self.assertEqual(p.stdout.splitlines()[0],
            'tiers: event=pull_request action=labeled label=full-matrix labels=full-matrix '
            'tier=full held=plan-test,linux,macos')

    def test_verdict_prints_its_tier(self):
        needs = {'plan': {'result': 'success', 'outputs': {'tier': 'pr', 'jobs': '["plan-test", "linux"]'}},
                 'linux': {'result': 'success'}, 'macos': {'result': 'skipped'},
                 'plan-test': {'result': 'success'}}
        p = subprocess.run([sys.executable, '-I', str(ROOT / 'ci/tiers.py'), 'verdict'],
            env=dict(os.environ, NEEDS=json.dumps(needs)), capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(p.stdout.splitlines()[0], 'tier pr: 2 of 3 job(s) chosen: plan-test linux')

    def verdict(self, needs):
        return subprocess.run([sys.executable, '-I', str(ROOT / 'ci/tiers.py'), 'verdict'],
            env=dict(os.environ, NEEDS=json.dumps(needs)), capture_output=True, text=True)

    def test_verdict_names_a_time_limit(self):
        needs = {'plan': {'result': 'success', 'outputs': {'tier': 'full', 'jobs': '["plan-test", "linux", "macos"]'}},
                 'linux': {'result': 'success', 'outputs': {'limit': 'held'}},
                 'macos': {'result': 'failure', 'outputs': {'limit': 'hit'}},
                 'plan-test': {'result': 'success'}}
        p = self.verdict(needs)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('selected job hit its time limit: macos (gate step 40 minutes)', p.stderr)
        needs['macos'] = {'result': 'cancelled', 'outputs': {}}
        p = self.verdict(needs)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('selected job was cancelled: macos', p.stderr)
        needs['macos'] = {'result': 'failure', 'outputs': {'limit': 'held'}}
        p = self.verdict(needs)
        self.assertIn('selected job did not succeed: macos', p.stderr)

    def limit(self, tmp, outcome, ran, job='macos'):
        start = Path(tmp) / 'gate-start'
        start.write_text('1000\n')
        out = Path(tmp) / 'output'
        out.write_text('')
        p = subprocess.run([sys.executable, '-I', str(ROOT / 'ci/tiers.py'), 'limit', '--job', job,
            '--outcome', outcome, '--since-file', str(start), '--now', str(1000 + ran),
            '--github-output', str(out)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        return p.stdout.strip(), out.read_text()

    def test_limit_step(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            line, out = self.limit(tmp, 'failure', 2400)
            self.assertEqual(out, 'limit=hit\n')
            self.assertTrue(line.startswith('TIME-LIMIT macos: the gate step ran 2400 s'), line)
            self.assertEqual(self.limit(tmp, 'cancelled', 2380)[1], 'limit=hit\n')
            self.assertEqual(self.limit(tmp, 'failure', 600)[1], 'limit=held\n')
            self.assertEqual(self.limit(tmp, 'success', 2399)[1], 'limit=held\n')
            linux = tiers_module().LIMITS['linux'] * 60
            self.assertEqual(self.limit(tmp, 'failure', linux, 'linux')[1], 'limit=hit\n')
            self.assertEqual(self.limit(tmp, 'failure', linux - 60, 'linux')[1], 'limit=held\n')

    def test_workflow_carries_the_limits(self):
        import re
        tiers = tiers_module()
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        for job, minutes in tiers.LIMITS.items():
            block = re.search(r'^  %s:\n(.*?)(?=^  [a-z-]+:\n|\Z)' % re.escape(job), text, re.M | re.S).group(1)
            self.assertIn('    timeout-minutes: %d\n' % (minutes + 10), block, job)
            self.assertIn('      - id: gate\n        timeout-minutes: %d\n' % minutes, block, job)
            self.assertIn('ci/tiers.py limit --job %s ' % job, block, job)
            self.assertIn('limit: ${{ steps.limit.outputs.limit }}', block, job)


if __name__ == '__main__': unittest.main()

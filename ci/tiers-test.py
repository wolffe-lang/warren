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
        # The output's first line is the verdict; the second names the minutes it held.
        lines = out.read_text().splitlines(True)
        self.assertEqual(lines[1:], ['minutes=%d\n' % tiers_module().LIMITS[job]])
        return p.stdout.strip(), lines[0]

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

    def test_nightly_fits_its_limit(self):
        # The nightly's Linux gate at the slowest measured pace: the rest of the
        # gate and every seed of its fresh drive. Its step limit holds twice that
        # (the rule LIMITS follows), and the drive's own deadline, which names a
        # stopped drive, ends it before the step limit would.
        tiers = tiers_module()
        sys.path.insert(0, str(ROOT / 'tests/vt'))
        try:
            import fresh_fuzz
        finally:
            sys.path.pop(0)
        seeds, _ = fresh_fuzz.profile_settings('nightly')
        drive = seeds * tiers.FRESH_SECONDS_PER_SEED
        expected = tiers.GATE_SECONDS_BESIDE_FRESH + drive
        limit = getattr(tiers, 'NIGHTLY_LIMITS', tiers.LIMITS)['linux'] * 60
        deadline = fresh_fuzz.profile_deadline('nightly') if hasattr(fresh_fuzz, 'profile_deadline') else 3600
        self.assertGreaterEqual(limit, 2 * expected, 'nightly limit %d s, expected %d s' % (limit, expected))
        self.assertGreaterEqual(deadline, 2 * drive, 'nightly drive deadline %d s, drive %d s' % (deadline, drive))
        self.assertLessEqual(tiers.GATE_SECONDS_BESIDE_FRESH + deadline, limit,
                             'the drive deadline %d s beside the rest of the gate passes the limit %d s' % (deadline, limit))
        seeds, _ = fresh_fuzz.profile_settings('pull-request')
        deadline = fresh_fuzz.profile_deadline('pull-request') if hasattr(fresh_fuzz, 'profile_deadline') else 3600
        self.assertGreaterEqual(deadline, 2 * seeds * tiers.FRESH_SECONDS_PER_SEED)

    def test_pull_request_fits_its_limit(self):
        # The pull-request profile's Linux gate at the slowest measured pace: the
        # rest of the gate and its 200 seeds. Its step limit holds twice that, the
        # rule LIMITS follows, as the nightly's does.
        tiers = tiers_module()
        sys.path.insert(0, str(ROOT / 'tests/vt'))
        try:
            import fresh_fuzz
        finally:
            sys.path.pop(0)
        seeds, _ = fresh_fuzz.profile_settings('pull-request')
        expected = tiers.GATE_SECONDS_BESIDE_FRESH + seeds * tiers.FRESH_SECONDS_PER_SEED
        limit = tiers.LIMITS['linux'] * 60
        self.assertGreaterEqual(limit, 2 * expected, 'pull-request limit %d s, expected %d s' % (limit, expected))
        self.assertLessEqual(tiers.GATE_SECONDS_BESIDE_FRESH + fresh_fuzz.profile_deadline('pull-request'), limit)

    def test_workflow_carries_the_limits(self):
        import re
        tiers = tiers_module()
        text = (ROOT / '.github/workflows/ci.yml').read_text()
        night = "(github.event_name == 'schedule' || inputs.profile == 'nightly')"
        for job, minutes in tiers.LIMITS.items():
            block = re.search(r'^  %s:\n(.*?)(?=^  [a-z-]+:\n|\Z)' % re.escape(job), text, re.M | re.S).group(1)
            if job in tiers.NIGHTLY_LIMITS:
                nightly = tiers.NIGHTLY_LIMITS[job]
                self.assertIn('    timeout-minutes: ${{ %s && %d || %d }}\n' % (night, nightly + 10, minutes + 10), block, job)
                self.assertIn('      - id: gate\n        timeout-minutes: ${{ %s && %d || %d }}\n' % (night, nightly, minutes), block, job)
                self.assertIn("WARREN_FUZZ_PROFILE: ${{ %s && 'nightly' || 'pull-request' }}" % night, block, job)
                self.assertIn('ci/tiers.py limit --job %s --profile "${{ %s && \'nightly\' || \'pull-request\' }}" ' % (job, night), block, job)
                # A hosted job may run at most six hours.
                self.assertLessEqual(nightly + 10, 360, job)
            else:
                self.assertIn('    timeout-minutes: %d\n' % (minutes + 10), block, job)
                self.assertIn('      - id: gate\n        timeout-minutes: %d\n' % minutes, block, job)
                self.assertIn('ci/tiers.py limit --job %s ' % job, block, job)
            self.assertIn('limit: ${{ steps.limit.outputs.limit }}', block, job)
        self.assertIn("      profile:\n", text)
        self.assertIn("        options: [pull-request, nightly]\n", text)

    def test_limit_step_for_the_nightly(self):
        import tempfile
        nightly = tiers_module().NIGHTLY_LIMITS['linux'] * 60
        pull = tiers_module().LIMITS['linux'] * 60
        with tempfile.TemporaryDirectory() as tmp:
            start = Path(tmp) / 'gate-start'
            start.write_text('1000\n')
            for profile, ran, verdict in (('nightly', nightly, 'hit'), ('nightly', pull, 'held'),
                                          ('pull-request', pull, 'hit')):
                out = Path(tmp) / 'output'
                out.write_text('')
                p = subprocess.run([sys.executable, '-I', str(ROOT / 'ci/tiers.py'), 'limit', '--job', 'linux',
                    '--profile', profile, '--outcome', 'cancelled', '--since-file', str(start),
                    '--now', str(1000 + ran), '--github-output', str(out)], capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertIn('limit=%s\n' % verdict, out.read_text(), (profile, ran))


if __name__ == '__main__': unittest.main()

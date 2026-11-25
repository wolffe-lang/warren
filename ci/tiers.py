#!/usr/bin/env python3
"""Which jobs a run owes: unlabelled PRs the cheap unit gate, `ci` the Linux gate,
`full-matrix`, trunk pushes, the nightly and a plain dispatch everything.

A trunk push leaves `macos` when its commit already has it green. Merges are
fast-forwards, so a push to trunk runs the commit its pull request's run has just
passed. On the runner's own push to trunk (GITHUB_EVENT_NAME, GITHUB_REF; the
plan's event push too) the plan asks the REST API, with the workflow's own
read-only token (PLAN_TOKEN), for this workflow's runs at GITHUB_SHA, and leaves
`macos` only when a completed, successful pull_request or workflow_dispatch run
there tested the same tree (its `plan` job's step `the tree under test is
<tree>`: a pull request's run tests its merge with the base, which is this tree
only when the base is already in the commit) and has, at its latest attempt, the
`macos` job once, green, on its macOS runner. Anything else runs it: no such
run, a lookup that fails, times out, redirects or answers oddly, a jobs listing
short of its count, no token, a checkout that is not the pushed commit. The plan
writes `covered=` (the jobs it left, each with the run, event, commit and tree it
relied on; `{}` otherwise) and one line per macOS job; the verdict accepts a
covered `macos` in place of a green one and names the run."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

JOBS = ['plan-test', 'linux', 'macos']
# Each gate step's limit, in minutes: at least twice the slowest green job
# measured with this gate's steps, so that a slower hosted runner (single
# steps have run 1.5 times slower) still has room. `.github/workflows/ci.yml`
# holds the same numbers on the gate steps and ten minutes more on their
# jobs; tiers-test.py holds the two together.
#   macos: the gate has grown from about 960 s (2026-11-14, when 40 minutes
#          was 2.5 times it) to 1,173 to 1,825 s over 30 green jobs
#          (below); 65 minutes is twice the slowest, 3,650 s, rounded up. On run
#          43575973926 a slower runner reached the first, 20-minute limit with
#          every finished step green.
#   linux: first sized from the measured pace below (the rest of the gate's
#          slowest 2,843 s and the pull-request drive's 200 seeds at 1.49 s,
#          3,141 s in all; 105 minutes was twice it). The slowest green gate
#          step since took 3,293 s (below); 110 minutes is twice it, 6,586 s,
#          rounded up. It was 80 minutes before the panes and the oracle
#          steps grew.
LIMITS = {'linux': 110, 'macos': 65}
# What the Linux gate takes, measured on hosted runs (19 green Linux jobs and
# #15's red one, which ran every step, 2026-11-14 and 11-15), for sizing a
# profile's limit: the fresh drive's slowest pace (298 s for 200 seeds, run
# 43589528422; the median is 233 s), and the rest of the gate's slowest
# (3,097 s less its 254-s drive, run 43640682013, whose image took 1,253 s).
FRESH_SECONDS_PER_SEED = 1.49
GATE_SECONDS_BESIDE_FRESH = 2843
# The nightly profile drives 5,000 seeds, so its Linux gate step takes about
# 2,843 + 5,000 * 1.49 = 10,293 s (172 minutes) at that pace (7,800 s at the
# median). Its limit is twice that, 345 minutes, and the job's 355 stays under
# a hosted job's 360. The drive's own deadline (15,000 s, twice 7,450) ends a
# slow drive by name before the step limit would: 2,843 + 15,000 = 17,843 s
# against 20,700. A workflow dispatch may ask for the nightly profile.
NIGHTLY_LIMITS = {'linux': 345}
# The slowest green gate step each limit has met since, read from the jobs of
# the 40 runs from 2026-11-18 22:45Z to 2026-11-21 13:36Z (the gate step's
# start and end): macOS 30 green jobs, 1,173 to 1,825 s (nightly 44545067049);
# Linux on the pull-request profile 28 green jobs, 1,733 to 3,293 s (trunk push
# 44477665367); the Linux nightly 3 green jobs, 7,084 to 8,495 s (nightly
# 44751135693). The gate has grown since the estimates above: each limit must
# stay at least twice the slowest of these.
SLOWEST_GREEN_GATE_SECONDS = {'linux': 3293, 'macos': 1825}
SLOWEST_GREEN_NIGHTLY_SECONDS = {'linux': 8495}
PROFILES = ('pull-request', 'nightly')
# A gate step that ended this close to its limit, red or cancelled, ran
# into it.
LIMIT_SLACK_SECONDS = 30

# The macOS jobs a trunk push may leave, each with its runner's label.
MACOS = {'macos': 'macos-15'}
WORKFLOW = '.github/workflows/ci.yml'
EVIDENCE_EVENTS = ('pull_request', 'workflow_dispatch')
TREE_STEP = re.compile(r'^the tree under test is ([0-9a-f]{40}|[0-9a-f]{64})$')
MAX_RUNS = 10
MAX_PAGES = 5


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """The plan follows no redirect: the token goes to the API alone."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'a redirect, not followed', headers, fp)


class Api:
    def __init__(self, base, repo, token, timeout):
        self.base, self.repo, self.token, self.timeout = base.rstrip('/'), repo, token, timeout
        self.opener = urllib.request.build_opener(NoRedirect)

    def get(self, path, **query):
        url = '%s/repos/%s/%s?%s' % (self.base, self.repo, path, urllib.parse.urlencode(query))
        req = urllib.request.Request(url, headers={
            'Authorization': 'Bearer ' + self.token,
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'warren-ci-plan',
        })
        with self.opener.open(req, timeout=self.timeout) as r:
            return json.loads(r.read().decode('utf-8'))


def run_jobs(api, run_id):
    """A run's jobs at its latest attempt, every page; None when the listing
    falls short of its own count."""
    jobs = []
    for page in range(1, MAX_PAGES + 1):
        d = api.get('actions/runs/%d/jobs' % run_id, filter='latest', per_page=100, page=page)
        got, total = d['jobs'], int(d['total_count'])
        jobs += got
        if len(jobs) >= total:
            return jobs if len(jobs) == total else None
        if not got:
            return None
    return None


def tested_tree(jobs):
    """The tree a run's `plan` job named, or None."""
    plan = [j for j in jobs if j.get('name') == 'plan']
    if len(plan) != 1 or plan[0].get('conclusion') != 'success':
        return None
    trees = [m.group(1) for s in (plan[0].get('steps') or []) if s.get('conclusion') == 'success'
             for m in [TREE_STEP.match(s.get('name') or '')] if m]
    return trees[0] if len(trees) == 1 else None


def green_kind(jobs, names, label):
    """Whether every job named is in the run once, green, on its macOS runner."""
    found = [[j for j in jobs if j.get('name') == n] for n in names]
    return all(len(f) == 1 and f[0].get('conclusion') == 'success' and label in (f[0].get('labels') or []) for f in found if f)


def git(*args):
    return subprocess.run(['git'] + list(args), capture_output=True, text=True, check=True).stdout.strip()


def trunk_push(event):
    """Whether this is the runner's own push to trunk, and the plan's."""
    return (event == 'push' and os.environ.get('GITHUB_EVENT_NAME') == 'push'
            and os.environ.get('GITHUB_REF') == 'refs/heads/trunk')


def cover(say):
    """-> {macOS job: the run, event, commit and tree it is green in}; {} on any doubt."""
    env = os.environ
    token = env.get('PLAN_TOKEN') or ''
    hide = lambda s: s.replace(token, '<token>') if token else s
    sha, repo = env.get('GITHUB_SHA') or '', env.get('GITHUB_REPOSITORY') or ''
    if not token:
        say('no token for the lookup: every macOS job runs')
        return {}
    if not re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', sha) or not repo:
        say('no pushed commit or repository named: every macOS job runs')
        return {}
    try:
        head, tree = git('rev-parse', 'HEAD'), git('rev-parse', 'HEAD^{tree}')
    except (OSError, subprocess.CalledProcessError) as e:
        say('git could not name the checkout (%s): every macOS job runs' % type(e).__name__)
        return {}
    if head != sha:
        say('the checkout %s is not the pushed commit %s: every macOS job runs' % (head, sha))
        return {}
    say('the pushed commit %s, tree %s' % (sha, tree))
    try:
        api = Api(env.get('GITHUB_API_URL') or 'https://api.github.com', repo, token,
                  float(env.get('PLAN_API_TIMEOUT') or 20))
        listing = api.get('actions/workflows/%s/runs' % os.path.basename(WORKFLOW), head_sha=sha, per_page=100)
        runs = [r for r in listing['workflow_runs']
                if r.get('head_sha') == sha and r.get('path') == WORKFLOW and r.get('status') == 'completed'
                and r.get('conclusion') == 'success' and r.get('event') in EVIDENCE_EVENTS]
        runs.sort(key=lambda r: -int(r['id']))
        found = {}
        for r in runs[:MAX_RUNS]:
            rid = int(r['id'])
            jobs = run_jobs(api, rid)
            if jobs is None:
                say('%s run %d: its jobs listing falls short of its count, not relied on' % (r['event'], rid))
                continue
            t = tested_tree(jobs)
            if t != tree:
                say('%s run %d tested tree %s, not %s: not relied on' % (r['event'], rid, t or '(not named)', tree))
                continue
            for job, label in MACOS.items():
                if job not in found and green_kind(jobs, [job], label):
                    found[job] = {'run': rid, 'event': r['event'], 'sha': sha, 'tree': tree}
        return found
    except Exception as e:  # any failure of the lookup runs every macOS job
        say('the lookup failed (%s: %s): every macOS job runs' % (type(e).__name__, hide(str(e))))
        return {}


def covered_lines(covered, server, repo):
    lines = []
    for job in MACOS:
        c = covered.get(job)
        if c:
            lines.append('skip %s: green in %s run %d at %s, tree %s (%s/%s/actions/runs/%d)' % (
                job, c['event'], c['run'], c['sha'], c['tree'], server, repo, c['run']))
        else:
            lines.append('keep %s: no completed, successful pull_request or workflow_dispatch run of %s at this '
                         'commit tested this tree with it green on %s' % (job, os.path.basename(WORKFLOW), MACOS[job]))
    return lines


def read_covered(out, tier, chosen):
    """The plan's `covered`, checked: only a macOS job, only in tier full, never
    also chosen, each with the run, event, commit and tree it relied on."""
    covered = json.loads(out.get('covered') or '{}')
    if not isinstance(covered, dict):
        raise ValueError('the plan\'s covered is not an object: %r' % out.get('covered'))
    for job, c in covered.items():
        if job not in MACOS:
            raise ValueError('covered names %s, which is no macOS job' % job)
        if tier != 'full':
            raise ValueError('covered %s in tier %s: only a full tier leaves a macOS job' % (job, tier))
        if job in chosen:
            raise ValueError('covered %s and chose it too' % job)
        if not (isinstance(c, dict) and isinstance(c.get('run'), int) and c.get('event') in EVIDENCE_EVENTS
                and all(re.fullmatch(r'[0-9a-f]{40}|[0-9a-f]{64}', str(c.get(k) or '')) for k in ('sha', 'tree'))):
            raise ValueError('covered %s names no run it relied on: %r' % (job, c))
    return covered


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    plan = sub.add_parser('plan')
    plan.add_argument('--event', default=os.environ.get('EVENT', ''))
    plan.add_argument('--labels', default=os.environ.get('LABELS', ''))
    plan.add_argument('--jobs', default=os.environ.get('IN_JOBS', ''))
    plan.add_argument('--action', default=os.environ.get('ACTION', '') or '-')
    plan.add_argument('--label', default=os.environ.get('LABEL', '') or '-')
    plan.add_argument('--github-output')
    sub.add_parser('verdict')
    limit = sub.add_parser('limit')
    limit.add_argument('--job', required=True, choices=sorted(LIMITS))
    limit.add_argument('--profile', choices=PROFILES, default='pull-request')
    limit.add_argument('--outcome', required=True)
    limit.add_argument('--since-file')
    limit.add_argument('--now', type=int)
    limit.add_argument('--github-output')
    args = p.parse_args()
    if args.command == 'limit':
        return limit_step(args)
    if args.command == 'verdict':
        needs = json.loads(os.environ['NEEDS'])
        if needs['plan']['result'] != 'success':
            raise ValueError('plan did not succeed')
        chosen = json.loads(needs['plan']['outputs']['jobs'])
        if not isinstance(chosen, list) or set(chosen) - set(JOBS):
            raise ValueError('invalid planned jobs')
        tier = needs['plan']['outputs']['tier']
        covered = read_covered(needs['plan']['outputs'], tier, chosen)
        if tier == 'full':
            left = [j for j in JOBS if j not in chosen and j not in covered]
            if left:
                raise ValueError('tier full left %s, neither chosen nor covered' % ' '.join(left))
        for job in chosen:
            result = needs.get(job, {}).get('result')
            if result == 'success':
                continue
            outputs = needs.get(job, {}).get('outputs') or {}
            if outputs.get('limit') == 'hit':
                raise ValueError('selected job hit its time limit: %s (gate step %s minutes)' % (
                    job, outputs.get('minutes') or LIMITS[job]))
            if result == 'cancelled':
                raise ValueError('selected job was cancelled: %s (a cancel, or its job limit)' % job)
            raise ValueError('selected job did not succeed: ' + job)
        for job in JOBS:
            if job not in chosen and needs.get(job, {}).get('result', 'skipped') != 'skipped':
                raise ValueError('unselected job ran: ' + job)
        # The run says what its tier held: the audit reads this line, not the code.
        print('tier %s: %d of %d job(s) chosen: %s' % (
            needs['plan']['outputs']['tier'], len(chosen), len(JOBS), ' '.join(chosen)))
        for job, c in sorted(covered.items()):
            print('covered %s: green in %s run %d at %s, tree %s' % (job, c['event'], c['run'], c['sha'], c['tree']))
        print('PASS tier ' + needs['plan']['outputs']['tier'])
        return 0
    labels = set(filter(None, args.labels.split(',')))
    if args.event == 'workflow_dispatch' and args.jobs:
        selected = args.jobs.split()
        if set(selected) - set(JOBS) or len(selected) != len(set(selected)):
            raise ValueError('unknown or duplicate dispatch job')
        result = {'tier': 'partial', 'jobs': selected}
    elif args.event in ('push', 'schedule', 'workflow_dispatch') or labels & {'full-matrix', 'release-matrix'}:
        result = {'tier': 'full', 'jobs': JOBS}
    elif args.event == 'pull_request' and 'ci' in labels:
        result = {'tier': 'pr', 'jobs': ['plan-test', 'linux']}
    elif args.event == 'pull_request':
        result = {'tier': 'local', 'jobs': ['plan-test']}
    else:
        raise ValueError('unknown event: ' + args.event)
    covered, lines = {}, []
    if trunk_push(args.event):
        found = cover(lambda s: lines.append(s))
        covered = {j: c for j, c in found.items() if j in result['jobs']} if result['tier'] == 'full' else {}
        result['jobs'] = [j for j in result['jobs'] if j not in covered]
        env = os.environ
        lines += covered_lines(covered, env.get('GITHUB_SERVER_URL') or 'https://github.com', env.get('GITHUB_REPOSITORY') or '')
    elif args.event == 'push':
        lines.append('not the runner\'s own push to trunk: nothing asked, every macOS job runs')
    if covered:
        result['covered'] = covered
    # A run's event, action and labels are not kept by the run API; this line keeps them.
    print('tiers: event=%s action=%s label=%s labels=%s tier=%s held=%s' % (
        args.event, args.action, args.label, ','.join(sorted(labels)) or '-',
        result['tier'], ','.join(result['jobs'])))
    for line in lines:
        print('tiers: ' + line)
    summary = os.environ.get('GITHUB_STEP_SUMMARY')
    if summary and lines:
        try:
            with Path(summary).open('a') as f:
                f.write('### The trunk push\'s macOS jobs\n\n' + ''.join('- %s\n' % l for l in lines) + '\n')
        except OSError as e:
            print('tiers: the step summary could not be written (%s)' % e)
    print(json.dumps(result))
    if args.github_output:
        with Path(args.github_output).open('a') as f:
            f.write('tier=' + result['tier'] + '\n')
            f.write('jobs=' + json.dumps(result['jobs']) + '\n')
            f.write('covered=' + json.dumps(covered, separators=(',', ':')) + '\n')
    return 0


def limit_minutes(job, profile):
    """A gate step's limit for a fuzz profile: the nightly's own where it has one."""
    if profile == 'nightly' and job in NIGHTLY_LIMITS:
        return NIGHTLY_LIMITS[job]
    return LIMITS[job]


def limit_step(args):
    """After a gate step, whatever its outcome: did it run into its limit?
    Prints one line and writes `limit=hit|held|unknown`; never fails."""
    since = None
    if args.since_file:
        try:
            since = int(Path(args.since_file).read_text().strip())
        except (OSError, ValueError):
            since = None
    now = args.now if args.now is not None else int(time.time())
    minutes = limit_minutes(args.job, args.profile)
    if since is None:
        verdict = 'unknown'
        print('limit %s: the gate step never started (outcome %s)' % (args.job, args.outcome))
    else:
        ran = now - since
        if args.outcome in ('failure', 'cancelled') and ran >= minutes * 60 - LIMIT_SLACK_SECONDS:
            verdict = 'hit'
            print('TIME-LIMIT %s: the gate step ran %d s against its %d-minute limit (outcome %s)' % (
                args.job, ran, minutes, args.outcome))
        else:
            verdict = 'held'
            print('limit %s: the gate step ran %d s of its %d minutes (outcome %s)' % (
                args.job, ran, minutes, args.outcome))
    if args.github_output:
        with Path(args.github_output).open('a') as f:
            f.write('limit=' + verdict + '\n')
            f.write('minutes=%d\n' % minutes)
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (ValueError, KeyError, OSError) as error:
        print('FAIL tier ' + str(error), file=sys.stderr)
        sys.exit(1)

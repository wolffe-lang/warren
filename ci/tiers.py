#!/usr/bin/env python3
"""Which jobs a run owes: unlabelled PRs the cheap unit gate, `ci` the Linux gate,
`full-matrix`, trunk pushes, the nightly and a plain dispatch everything."""
import argparse
import json
import os
from pathlib import Path
import sys
import time

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
#   linux: sized from the measured pace below: the rest of the gate's
#          slowest 2,843 s and the pull-request drive's 200 seeds at 1.49 s,
#          3,141 s in all; 105 minutes is twice it (6,300 s against 6,282).
#          It was 80 minutes, from 2,340 s measured before the panes and the
#          oracle steps grew; the slowest complete gate since took 3,097 s.
LIMITS = {'linux': 105, 'macos': 65}
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
    # A run's event, action and labels are not kept by the run API; this line keeps them.
    print('tiers: event=%s action=%s label=%s labels=%s tier=%s held=%s' % (
        args.event, args.action, args.label, ','.join(sorted(labels)) or '-',
        result['tier'], ','.join(result['jobs'])))
    print(json.dumps(result))
    if args.github_output:
        with Path(args.github_output).open('a') as f:
            f.write('tier=' + result['tier'] + '\n')
            f.write('jobs=' + json.dumps(result['jobs']) + '\n')
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

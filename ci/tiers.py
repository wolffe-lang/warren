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
#   macos: green jobs took 847 s and 913 s before the server's steps (runs
#          43563124431 and 43556256934); on run 43575973926 a slower runner
#          reached the old 20-minute limit with every finished step green.
#          The server's steps took 29 s of a 685 s gate on a second
#          Apple-silicon machine, so about 960 s: 40 minutes is 2.5 times it.
#   linux: green jobs took 1,686 s, 1,879 s and 2,106 s (runs 43575973926,
#          43563124431 and 43231544049). The server's steps took 229 s in the
#          pinned image on two CPUs (compose rows 80 s, session rows 141 s),
#          so about 2,340 s: 80 minutes is twice it.
LIMITS = {'linux': 80, 'macos': 40}
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
            if (needs.get(job, {}).get('outputs') or {}).get('limit') == 'hit':
                raise ValueError('selected job hit its time limit: %s (gate step %d minutes)' % (job, LIMITS[job]))
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
    minutes = LIMITS[args.job]
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
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (ValueError, KeyError, OSError) as error:
        print('FAIL tier ' + str(error), file=sys.stderr)
        sys.exit(1)

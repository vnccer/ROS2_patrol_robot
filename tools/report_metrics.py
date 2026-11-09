#!/usr/bin/env python3
"""Summarize observed records; unfinished and expired events stay visible."""
import argparse
import csv
import json
from pathlib import Path
import statistics

def summarize(path):
    with Path(path).open(encoding='utf-8',newline='') as stream:
        rows = list(csv.DictReader(stream))
    by_kind = {}
    for r in rows:
        by_kind.setdefault(r['kind'],[]).append(r)
    accepted = {r['task_id'] for r in by_kind.get('accepted',[])}
    completed = {r['task_id'] for r in by_kind.get('completed',[])} & accepted
    expired = {r['task_id'] for r in by_kind.get('expired',[])}
    failed = {r['task_id'] for r in by_kind.get('failed',[])} & accepted
    def latency(kind):
        first = {}
        for r in by_kind.get(kind,[]):
            if r['task_id'] in accepted:
                first.setdefault(r['task_id'],float(r['value']))
        values = sorted(first.values())
        return dict(n=len(values),mean_sec=statistics.mean(values) if values else None,
                    max_sec=max(values) if values else None,
                    p95_sec=values[max(0,math_ceil(.95*len(values))-1)] if values else None)
    # Recovery observation: a preempted patrol goal is later dispatched with the same ID.
    preempted,resumed = set(),set()
    for r in rows:
        if r['kind']=='cancel_requested' and r['detail']=='preempt' and r['task_id'].startswith('patrol/'):
            preempted.add(r['task_id'])
        elif r['kind']=='dispatched' and r['task_id'] in preempted:
            resumed.add(r['task_id'])
    return dict(source=str(path),events_accepted=len(accepted),events_completed=len(completed),
        events_failed=len(failed),events_expired=len(expired),
        events_pending_or_interrupted=len(accepted-completed-expired-failed),
        observed_event_completion_ratio=len(completed)/len(accepted) if accepted else None,
        first_dispatch_latency=latency('dispatched'),first_arrival_latency=latency('arrived'),
        patrol_preempted_target_ids=len(preempted),patrol_redispatched_target_ids=len(resumed),
        faults=len(by_kind.get('fault',[])),duplicates=len(by_kind.get('duplicate',[])),
        note='Latencies use local monotonic receipt time; arrival includes travel. Finite observation, not ground-truth response correctness. Patrol redispatch counts target IDs, not interruption attempts.')

def math_ceil(value):
    import math
    return math.ceil(value)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('records',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=summarize(args.records)
    rendered=json.dumps(report,ensure_ascii=False,indent=2)
    if args.output:
        args.output.write_text(rendered+'\n',encoding='utf-8')
    print(rendered)

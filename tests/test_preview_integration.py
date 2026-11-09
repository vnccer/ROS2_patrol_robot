"""Exercise the compiled C++ core through a moving robot, not a duplicate scheduler."""
import os
from pathlib import Path
import sys
import time
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from desktop_demo import Preview

def wait(preview,predicate,seconds=20):
    end = time.monotonic()+seconds
    while time.monotonic()<end:
        state = preview.snapshot()
        if predicate(state):
            return state
        time.sleep(.04)
    pytest.fail('Preview condition timed out: '+str(preview.snapshot()))

def test_shared_core_preemption_recovery_and_sensor_fault():
    binary = ROOT/'tools/bin'/('core_bridge.exe' if os.name=='nt' else 'core_bridge')
    if not binary.exists():
        pytest.skip('Run tools/build_core.py first for compiled-core integration')
    p = Preview(binary,speed=2.)
    try:
        wait(p,lambda s:s['status'].get('state')=='PATROLLING')
        p.submit(dict(action='event',id='low',priority=20,x=2.,y=1.,ttl=120.,handling=2.))
        wait(p,lambda s:s['status'].get('active_id')=='low')
        p.submit(dict(action='event',id='high',priority=100,x=1.5,y=1.5,ttl=120.,handling=.1))
        p.submit(dict(action='event',id='high',priority=100,x=1.5,y=1.5,ttl=120.,handling=.1))
        wait(p,lambda s:s['status'].get('active_id')=='high')
        wait(p,lambda s:s['status'].get('events_completed')==2,30)
        s = wait(p,lambda s:s['status'].get('active_id','').startswith('patrol/'))
        completed = [r['id'] for r in s['records'] if r['kind']=='completed']
        assert completed.index('high')<completed.index('low')
        assert any(r['kind']=='duplicate' and r['id']=='high' for r in s['records'])
        p.submit(dict(action='pause'))
        wait(p,lambda s:s['status'].get('state')=='PAUSED')
        p.submit(dict(action='drop_odom',enabled=True))
        wait(p,lambda s:s['status'].get('state')=='FAULT',4)
        s = p.snapshot()
        assert not s['status']['motion_permitted']
        before = s['robot'][:2]
        time.sleep(.3)
        assert p.snapshot()['robot'][:2]==before
        p.submit(dict(action='drop_odom',enabled=False))
        p.submit(dict(action='recover'))
        wait(p,lambda s:s['status'].get('state')=='PAUSED')
        p.submit(dict(action='resume'))
        wait(p,lambda s:s['status'].get('state')=='PATROLLING')
    finally:
        p.close()

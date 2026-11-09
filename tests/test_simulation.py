import importlib.util
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/patrol_sim'))
sys.path.insert(0,str(ROOT/'tools'))
from patrol_sim.geometry import WALLS, collides, integrate, raycast
from patrol_sim.guard_logic import GuardPolicy
from desktop_demo import route

def live_guard():
    g = GuardPolicy()
    g.permit(True,10)
    g.odom_at = g.scan_at = 10
    g.velocity(.2,.5,10)
    return g

def test_guard_startup_and_limits():
    assert GuardPolicy().output(0)==(0.,0.)
    g = live_guard()
    assert g.output(10)==(.2,.5)
    g.velocity(5.,-10.,10)
    assert g.output(10)==(.26,-1.)

@pytest.mark.parametrize('field',['permit_at','command_at','odom_at','scan_at'])
def test_each_watchdog_is_required(field):
    g = live_guard()
    setattr(g,field,9.)
    assert g.output(10)==(0.,0.)

def test_pause_does_not_replay_old_command():
    g = live_guard()
    g.permit(False,10.1)
    g.permit(True,10.2)
    assert g.output(10.2)==(0.,0.)
    g.velocity(.2,0.,10.2)
    assert g.output(10.2)==(.2,0.)
    g.velocity(math.nan,0.,10.3)
    assert g.output(10.3)==(0.,0.)

def test_collision_and_raycast():
    assert collides(0,0)
    assert not collides(1,1)
    assert raycast(1,1,0)==pytest.approx(6.85)
    assert raycast(1,1,math.pi)==pytest.approx(.85)
    x,y,_,_ = integrate(1,1,math.pi,20,0,1)
    assert x>=.32 and y==pytest.approx(1)

def test_preview_routes_avoid_walls():
    for goal in ((7,1),(7,7),(1,7),(6.5,6.5)):
        path = route((1,1),goal)
        assert path
        assert all(not collides(x,y,radius=.18) for x,y in path)
    assert not route((1,1),(4,2))
    assert not route((1,1),(9,9))

def test_generated_world_and_map_consistency():
    world = ET.parse(ROOT/'src/patrol_bringup/worlds/indoor.world')
    assert len(world.findall('.//model'))==len(WALLS)+1
    pgm = (ROOT/'src/patrol_bringup/maps/indoor.pgm').read_bytes()
    header,pixels = pgm.split(b'255\n',1)
    assert len(pixels)==160*160
    for row in range(160):
        for col in range(160):
            x,y = (col+.5)*.05,8-(row+.5)*.05
            occupied = any(a<=x<=a+w and b<=y<=b+h for a,b,w,h in WALLS)
            assert (pixels[row*160+col]==0)==occupied

def test_mission_waypoints_are_valid():
    p = yaml.safe_load((ROOT/'src/patrol_bringup/config/mission.yaml').read_text(encoding='utf-8'))['mission_manager']['ros__parameters']
    assert len(p['waypoints'])%3==0
    for i in range(0,len(p['waypoints']),3):
        assert not collides(*p['waypoints'][i:i+2],radius=.4)

def test_all_manifests_are_valid_xml():
    for path in (ROOT/'src').glob('*/package.xml'):
        assert ET.parse(path).getroot().findtext('license')=='Apache-2.0'

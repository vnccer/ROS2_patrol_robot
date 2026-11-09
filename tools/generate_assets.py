#!/usr/bin/env python3
"""Regenerate consistent PGM, Gazebo world and derived Humble Nav2 configuration."""
import sys
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/patrol_sim'))
from patrol_sim.geometry import SIZE, RESOLUTION, WALLS

def main():
    target = ROOT/'src/patrol_bringup'
    (target/'maps').mkdir(exist_ok=True)
    (target/'worlds').mkdir(exist_ok=True)
    count = round(SIZE/RESOLUTION)
    pixels = bytearray()
    for row in range(count):
        y = SIZE-(row+.5)*RESOLUTION
        for col in range(count):
            x = (col+.5)*RESOLUTION
            pixels.append(0 if any(a<=x<=a+w and b<=y<=b+h for a,b,w,h in WALLS) else 254)
    (target/'maps/indoor.pgm').write_bytes(f'P5\n{count} {count}\n255\n'.encode()+pixels)
    (target/'maps/indoor.yaml').write_text('image: indoor.pgm\nresolution: 0.05\norigin: [0.0, 0.0, 0.0]\nnegate: 0\noccupied_thresh: 0.65\nfree_thresh: 0.196\n',encoding='utf-8')
    boxes = []
    for i,(x,y,w,h) in enumerate(WALLS):
        shape = f'<geometry><box><size>{w} {h} 1</size></box></geometry>'
        boxes.append(f'<model name="wall_{i}"><static>true</static><pose>{x+w/2} {y+h/2} .5 0 0 0</pose><link name="wall"><collision name="collision">{shape}</collision><visual name="visual">{shape}<material><ambient>.35 .45 .5 1</ambient><diffuse>.35 .45 .5 1</diffuse></material></visual></link></model>')
    world = '''<?xml version="1.0"?>
<sdf version="1.6"><world name="patrol_indoor">
<physics name="default_physics" type="ode"><max_step_size>0.002</max_step_size><real_time_update_rate>500</real_time_update_rate></physics>
<light name="sun" type="directional"><pose>0 0 10 0 0 0</pose><diffuse>.9 .9 .9 1</diffuse><direction>-.3 -.4 -1</direction><cast_shadows>false</cast_shadows></light>
<model name="floor"><static>true</static><link name="floor"><collision name="collision"><geometry><plane><normal>0 0 1</normal><size>30 30</size></plane></geometry></collision><visual name="visual"><geometry><plane><normal>0 0 1</normal><size>30 30</size></plane></geometry><material><ambient>.7 .7 .7 1</ambient></material></visual></link></model>
'''+ '\n'.join(boxes) + '\n</world></sdf>\n'
    (target/'worlds/indoor.world').write_text(world,encoding='utf-8')
    nav = yaml.safe_load((ROOT/'third_party/nav2_params.humble.yaml').read_text(encoding='utf-8'))
    # Modified from Nav2 Humble (Apache-2.0): smaller VM workload and our robot limits.
    def time_mode(item):
        if isinstance(item,dict):
            for key,value in item.items():
                if key=='use_sim_time':
                    item[key] = False
                else:
                    time_mode(value)
    time_mode(nav)
    ctl = nav['controller_server']['ros__parameters']
    ctl['controller_frequency'] = 10.
    ctl['FollowPath'].update(vx_samples=12,vy_samples=1,vtheta_samples=16,debug_trajectory_details=False,
                           trans_stopped_velocity=.05,max_vel_x=.26,max_speed_xy=.26)
    ctl['progress_checker']['required_movement_radius'] = .15
    for key in ('local_costmap','global_costmap'):
        cm = nav[key][key]['ros__parameters']
        cm['robot_radius'] = .18
        cm['update_frequency'],cm['publish_frequency'] = 3.,1.
        cm['inflation_layer']['inflation_radius'] = .4
    amcl = nav['amcl']['ros__parameters']
    amcl.update(min_particles=200,max_particles=600,laser_max_range=10.)
    header = '# Derived from ros-navigation/navigation2 nav2_bringup, humble. Apache-2.0.\n# Modified 2026-11-02: VM workload, radius, stopping threshold and sensor range.\n# Original snapshot and attribution: third_party/ and THIRD_PARTY_NOTICES.md.\n'
    (target/'config/nav2.yaml').write_text(header+yaml.safe_dump(nav,sort_keys=False),encoding='utf-8')
    print('Generated indoor map/world and Nav2 configuration.')

if __name__=='__main__':
    main()

#!/usr/bin/env python3
"""Immediate Windows/Linux preview: shared C++ scheduler + simplified 2D navigation.

This is not ROS2 or Nav2. Use ros2 launch patrol_bringup system.launch.py for those.
"""
import argparse
import copy
import csv
import heapq
import json
import math
import os
from pathlib import Path
import queue
import re
import subprocess
import sys
import threading
import time
import uuid
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src/patrol_sim'))
from patrol_sim.geometry import WALLS, collides, integrate
from patrol_sim.http_api import serve
from build_core import build

def route(start, goal):
    """Small A* preview only; real ROS mode uses Nav2 planning and avoidance."""
    if collides(*goal,radius=.22) or not all(.2<=v<=7.8 for v in goal):
        return []
    step = .2
    key = lambda p:(round(p[0]/step),round(p[1]/step))
    source,target = key(start),key(goal)
    frontier = [(0.,source)]
    previous,cost = {source:None},{source:0.}
    while frontier:
        _,current = heapq.heappop(frontier)
        if current==target:
            path = [goal]
            while current!=source:
                path.append((current[0]*step,current[1]*step))
                current = previous[current]
            return list(reversed(path))
        for dx,dy in ((1,0),(-1,0),(0,1),(0,-1)):
            nxt = current[0]+dx,current[1]+dy
            x,y = nxt[0]*step,nxt[1]*step
            if not (1<=nxt[0]<=39 and 1<=nxt[1]<=39) or collides(x,y,radius=.22):
                continue
            newcost = cost[current]+1
            if newcost<cost.get(nxt,math.inf):
                cost[nxt],previous[nxt] = newcost,current
                heapq.heappush(frontier,(newcost+abs(nxt[0]-target[0])+abs(nxt[1]-target[1]),nxt))
    return []

class Preview:
    def __init__(self, binary, speed=1.):
        self.proc = subprocess.Popen([str(binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                     text=True,bufsize=1,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        self.speed = speed
        self.lock,self.commands = threading.Lock(),queue.Queue(maxsize=100)
        self.stop = threading.Event()
        self.x,self.y,self.yaw = 1.,1.,0.
        self.drop_odom = self.drop_scan = self.blocked = False
        self.bad_odom_since = None
        self.active = None
        self.feedback = ''
        self.state = dict(backend='本机预览 · C++ 核心 / 简化 A*（非 ROS2）',connected=True,
                          robot=[1.,1.,0.],walls=WALLS,route=[],records=[],status={},feedback='')
        directory = ROOT/'preview_runs'/(time.strftime('%Y%m%d_%H%M%S')+'-'+uuid.uuid4().hex[:6])
        directory.mkdir(parents=True,exist_ok=True)
        self.log = (directory/'records.csv').open('w',newline='',encoding='utf-8')
        self.writer = csv.writer(self.log)
        self.writer.writerow(['ros_sec','monotonic_sec','kind','task_id','detail','value'])
        self.thread = threading.Thread(target=self.run,daemon=True)
        self.thread.start()

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.state)

    def submit(self, message):
        if message.get('action') not in ('event','pause','resume','stop','recover','drop_odom','drop_scan','blocked'):
            raise ValueError('unknown action')
        try:
            self.commands.put_nowait(message)
        except queue.Full:
            raise ValueError('control queue full')
        return {'queued':True}

    def ask(self, line):
        self.proc.stdin.write(line+'\n')
        self.proc.stdin.flush()
        data = json.loads(self.proc.stdout.readline())
        self.state['status'] = data['status']
        for e in data['effects']:
            if e['type']==0:
                points = route((self.x,self.y),(e['x'],e['y']))
                self.active = dict(token=e['token'],route=points,yaw=e['yaw'],empty_at=time.monotonic())
            elif e['type']==1:
                self.active = None
                # Preview returns terminal cancellation synchronously; ROS waits for Nav2 result.
                self.ask(f'result {time.monotonic()} {e["token"]} 0')
            else:
                self.state['records'].append(e)
                self.state['records'] = self.state['records'][-100:]
                self.writer.writerow([time.time(),time.monotonic(),e['kind'],e['id'],e['detail'],e['value']])
                self.log.flush()

    def execute(self, m, now):
        action = m['action']
        if action=='event':
            ident = str(m.get('id') or uuid.uuid4().hex[:10])
            if not re.fullmatch(r'[A-Za-z0-9_./-]{1,128}',ident):
                raise ValueError('Preview ID: letters, digits, _ . / - only')
            vals = [float(m[k]) for k in ('x','y','ttl','handling')]
            if not all(math.isfinite(v) for v in vals):
                raise ValueError('finite numbers required')
            x,y,ttl,handling = vals
            self.ask(f'event {now} {ident} {int(m["priority"])} {x} {y} {ttl} {handling}')
        elif action in ('pause','resume'):
            self.ask(f'pause {now} {int(action=="pause")}')
        elif action=='stop':
            self.ask(f'trip {now} operator emergency stop')
        elif action=='recover':
            self.ask(f'recover {now} {int(not self.drop_odom and not self.drop_scan)}')
        else:
            setattr(self,action,bool(m['enabled']))
        self.feedback = '请求已处理，查看任务记录。'

    def run(self):
        last = time.monotonic()
        try:
            while not self.stop.wait(.04):
                now = time.monotonic()
                dt,last = min(now-last,.1),now
                with self.lock:
                    for _ in range(10):
                        try:
                            message = self.commands.get_nowait()
                        except queue.Empty:
                            break
                        try:
                            self.execute(message,now)
                        except (ValueError,KeyError,TypeError) as error:
                            self.feedback = str(error)
                    if self.drop_odom:
                        self.bad_odom_since = self.bad_odom_since or now
                        if now-self.bad_odom_since>1:
                            self.ask(f'trip {now} odometry timeout')
                    else:
                        self.bad_odom_since = None
                    self.ask(f'tick {now} {int(not self.drop_odom)}')
                    if self.active and self.state['status']['motion_permitted'] and not (self.drop_odom or self.drop_scan or self.blocked):
                        a = self.active
                        if not a['route']:
                            if now-a['empty_at']>.2:
                                self.ask(f'result {now} {a["token"]} 0')
                                self.active = None
                        else:
                            x,y = a['route'][0]
                            delta = math.atan2(y-self.y,x-self.x)-self.yaw
                            delta = math.atan2(math.sin(delta),math.cos(delta))
                            v = self.speed if abs(delta)<.4 else 0.
                            w = max(-2.,min(2.,delta*4))
                            self.x,self.y,self.yaw,_ = integrate(self.x,self.y,self.yaw,v,w,dt)
                            if math.hypot(x-self.x,y-self.y)<.1:
                                a['route'].pop(0)
                                if not a['route']:
                                    # Preview simplifies final orientation; real Nav2 enforces goal yaw.
                                    self.yaw = a['yaw']
                                    self.ask(f'result {now} {a["token"]} 1')
                                    self.active = None
                    self.state['robot'] = [self.x,self.y,self.yaw]
                    self.state['route'] = self.active['route'] if self.active else []
                    self.state['feedback'] = self.feedback
        except Exception as error:
            with self.lock:
                self.state['connected'] = False
                self.state['feedback'] = f'Preview stopped: {error}'

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3)
        self.proc.stdin.close()
        try:
            self.proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8765)
    parser.add_argument('--speed',type=float,default=1.)
    parser.add_argument('--no-browser',action='store_true')
    parser.add_argument('--stop',action='store_true',help='Stop an existing local preview')
    args = parser.parse_args()
    url = f'http://127.0.0.1:{args.port}'
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    if args.stop:
        request = urllib.request.Request(url+'/api/action',data=b'{"action":"shutdown"}',
                                         headers={'Content-Type':'application/json'})
        try:
            print(opener.open(request,timeout=3).read().decode())
        except OSError as error:
            print(f'No accessible preview: {error}')
        return
    try:
        existing = json.loads(opener.open(url+'/api/state',timeout=1).read())
    except (OSError,ValueError):
        existing = None
    if existing:
        print(f'An existing control panel is running: {url}')
        if not args.no_browser:
            webbrowser.open(url)
        return
    if not math.isfinite(args.speed) or not 0<args.speed<=2:
        parser.error('--speed must be in (0, 2]')
    binary = ROOT/'tools/bin'/('core_bridge.exe' if os.name=='nt' else 'core_bridge')
    sources = [ROOT/'src/patrol_manager/include/patrol_manager/mission.hpp',ROOT/'tools/core_bridge.cpp']
    if not binary.exists() or any(path.stat().st_mtime>binary.stat().st_mtime for path in sources):
        binary = build()
    preview = Preview(binary,args.speed)
    def submit(message):
        if message.get('action')=='shutdown':
            threading.Thread(target=server.shutdown,daemon=True).start()
            return {'stopping':True}
        return preview.submit(message)
    try:
        server = serve(ROOT/'src/patrol_sim/web',preview.snapshot,submit,args.port)
    except Exception:
        preview.close()
        raise
    print(f'Portable preview (not ROS2): http://127.0.0.1:{args.port}',flush=True)
    if not args.no_browser:
        webbrowser.open(f'http://127.0.0.1:{args.port}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        preview.close()

if __name__=='__main__':
    main()

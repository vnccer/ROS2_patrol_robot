#!/usr/bin/env python3
"""Build and test the ROS-independent C++17 mission core on Windows or Linux."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def compiler():
    for name in ('g++','clang++'):
        path = shutil.which(name)
        if path:
            return [path]
    zig = shutil.which('zig')
    if not zig:
        candidate = ROOT.parent/'tmp/toolchain/ziglang/zig.exe'
        if candidate.exists():
            zig = str(candidate)
    if zig:
        return [zig,'c++']
    raise SystemExit('C++ compiler missing. Ubuntu: sudo apt install g++. Windows: install LLVM/MinGW or zig.')

def build(test=True):
    output = ROOT/'tools/bin'
    output.mkdir(exist_ok=True)
    suffix = '.exe' if os.name=='nt' else ''
    cc = compiler()
    env = os.environ.copy()
    if 'zig' in Path(cc[0]).name:
        env['ZIG_GLOBAL_CACHE_DIR'] = str(ROOT/'.cache/zig-global')
        env['ZIG_LOCAL_CACHE_DIR'] = str(ROOT/'.cache/zig-local')
        temporary = ROOT/'.cache/tmp'
        temporary.mkdir(parents=True,exist_ok=True)
        env['TMP'] = env['TEMP'] = str(temporary)
    base = cc+['-std=c++17','-Wall','-Wextra','-Wpedantic','-I'+str(ROOT/'src/patrol_manager/include')]
    for source,name in [('tools/core_bridge.cpp','core_bridge'),('src/patrol_manager/test/test_mission.cpp','test_mission')]:
        result = subprocess.run(base+[str(ROOT/source),'-o',str(output/(name+suffix))],
                                env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
        (output/(name+'_build.log')).write_text(result.stdout+result.stderr,encoding='utf-8')
        if result.returncode:
            print((result.stdout+result.stderr)[-6000:],file=__import__('sys').stderr)
            result.check_returncode()
    if test:
        subprocess.run([str(output/('test_mission'+suffix))],check=True)
    return output/('core_bridge'+suffix)

if __name__=='__main__':
    build()

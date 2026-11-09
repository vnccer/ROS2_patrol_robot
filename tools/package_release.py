#!/usr/bin/env python3
"""Create a small source+Windows preview delivery, excluding caches and experiments."""
from pathlib import Path
import stat
import zipfile

ROOT = Path(__file__).resolve().parents[1]
output = ROOT.parent/'outputs'
output.mkdir(exist_ok=True)
destination = output/'ROS2_patrol_response_system.zip'
excluded = {'.cache','.pytest_cache','__pycache__','build','install','log','preview_runs','test_results'}
with zipfile.ZipFile(destination,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(ROOT.rglob('*')):
        relative = path.relative_to(ROOT)
        if not path.is_file() or any(part in excluded for part in relative.parts):
            continue
        if path.suffix in ('.pyc','.log','.pdb','.obj'):
            continue
        executable = (path.suffix in ('.sh','.exe') or
                      relative.parent == Path('src/patrol_sim/scripts') or
                      (relative.parent == Path('tools') and path.suffix == '.py'))
        info = zipfile.ZipInfo.from_file(path,(Path('patrol_robot_ws')/relative).as_posix())
        info.create_system = 3
        info.external_attr = (stat.S_IFREG | (0o755 if executable else 0o644)) << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        archive.writestr(info,path.read_bytes())
print(destination)

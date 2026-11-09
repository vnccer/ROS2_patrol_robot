"""Single source for the authored indoor map, Gazebo world and 2D sensors."""
import math

SIZE = 8.0
RESOLUTION = 0.05
WALLS = [
    (0., 0., 8., .15), (0., 7.85, 8., .15),
    (0., 0., .15, 8.), (7.85, 0., .15, 8.),
    (3.9, 1.7, .2, 1.4), (3.9, 4.9, .2, 1.4),
    (5.5, 3.6, .6, .8), (1.8, 3.7, .7, .6),
]

def collides(x, y, radius=.18, walls=None):
    if not math.isfinite(x) or not math.isfinite(y):
        return True
    return any((x-max(a, min(x, a+w)))**2 + (y-max(b, min(y, b+h)))**2 < radius**2
               for a, b, w, h in (WALLS if walls is None else walls))

def raycast(x, y, angle, max_range=10., walls=None):
    dx, dy = math.cos(angle), math.sin(angle)
    distance = max_range
    for a, b, w, h in (WALLS if walls is None else walls):
        low, high = 0., max_range
        for start, direction, lo, hi in ((x, dx, a, a+w), (y, dy, b, b+h)):
            if abs(direction) < 1e-12:
                if not lo <= start <= hi:
                    low = max_range + 1
                    break
            else:
                t1, t2 = (lo-start)/direction, (hi-start)/direction
                low, high = max(low, min(t1, t2)), min(high, max(t1, t2))
        if low <= high:
            distance = min(distance, low)
    return distance

def integrate(x, y, yaw, v, omega, dt, walls=None):
    """Small substeps prevent a fast command crossing a thin wall."""
    steps = max(1, math.ceil(abs(v)*dt/.025))
    moved = False
    for _ in range(steps):
        yaw += omega*dt/steps
        nx, ny = x+v*math.cos(yaw)*dt/steps, y+v*math.sin(yaw)*dt/steps
        if not collides(nx, ny, walls=walls):
            x, y, moved = nx, ny, True
    return x, y, math.atan2(math.sin(yaw), math.cos(yaw)), moved

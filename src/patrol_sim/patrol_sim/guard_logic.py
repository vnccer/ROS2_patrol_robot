"""Dependency-free velocity watchdog policy, shared with unit tests."""
import math

class GuardPolicy:
    def __init__(self, max_linear=.26, max_angular=1., timeout=.5):
        if not all(math.isfinite(v) and v > 0 for v in (max_linear, max_angular, timeout)):
            raise ValueError('guard limits must be finite and positive')
        self.max_linear, self.max_angular, self.timeout = max_linear, max_angular, timeout
        self.command = (0., 0.)
        self.command_at = self.permit_at = self.odom_at = self.scan_at = -math.inf
        self.permitted = False

    def permit(self, value, now):
        if not value or not self.permitted:
            self.command_at = -math.inf
        self.permitted, self.permit_at = value, now

    def velocity(self, v, w, now):
        if not self.permitted or not all(math.isfinite(x) for x in (v, w)):
            self.command_at = -math.inf
            return
        self.command, self.command_at = (v, w), now

    def output(self, now):
        if not self.permitted or any(now-t > self.timeout for t in
                (self.command_at, self.permit_at, self.odom_at, self.scan_at)):
            return 0., 0.
        v, w = self.command
        return max(-self.max_linear, min(v, self.max_linear)), max(-self.max_angular, min(w, self.max_angular))

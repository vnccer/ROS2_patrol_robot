import math
import time
import rclpy
from rclpy.node import Node
from rclpy.clock import Clock, ClockType
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from std_msgs.msg import Bool
from patrol_sim.guard_logic import GuardPolicy
from patrol_sim.runtime import run_node

class VelocityGuard(Node):
    """底盘唯一的速度出口：指令、许可、里程计、激光都新鲜才放行。"""
    def __init__(self):
        super().__init__('velocity_guard')
        self.policy = GuardPolicy(
            self.declare_parameter('max_linear', .26).value,
            self.declare_parameter('max_angular', 1.).value,
            self.declare_parameter('watchdog_sec', .5).value)
        self.pub = self.create_publisher(Twist, 'cmd_vel', 10)
        self.create_subscription(Twist, 'nav_cmd_vel', self.velocity, 10)
        self.create_subscription(Bool, 'patrol/motion_permit', lambda m: self.policy.permit(m.data, time.monotonic()), 10)
        self.create_subscription(Odometry, 'odom', self.odom, qos_profile_sensor_data)
        self.create_subscription(LaserScan, 'scan', self.scan, qos_profile_sensor_data)
        self.clock = Clock(clock_type=ClockType.STEADY_TIME)
        self.create_timer(.05, self.tick, clock=self.clock)

    def velocity(self, m):
        self.policy.velocity(m.linear.x, m.angular.z, time.monotonic())

    def odom(self, m):
        p, q = m.pose.pose.position, m.pose.pose.orientation
        norm = q.x*q.x+q.y*q.y+q.z*q.z+q.w*q.w
        if math.isfinite(p.x) and math.isfinite(p.y) and math.isfinite(norm) and .5 < norm < 1.5:
            self.policy.odom_at = time.monotonic()

    def scan(self, m):
        if m.ranges and any(math.isfinite(x) and x >= m.range_min for x in m.ranges):
            self.policy.scan_at = time.monotonic()

    def tick(self):
        msg = Twist()
        msg.linear.x, msg.angular.z = self.policy.output(time.monotonic())
        self.pub.publish(msg)

def main():
    run_node(VelocityGuard, stop_motion)


def stop_motion(node):
    # run_node keeps the context alive until this last stop command is sent.
    if rclpy.ok():
        node.pub.publish(Twist())

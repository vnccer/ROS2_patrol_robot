import math
import time
import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from geometry_msgs.msg import TransformStamped, Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan
from std_srvs.srv import SetBool
from tf2_ros import TransformBroadcaster
from patrol_sim.geometry import WALLS, integrate, raycast

class Simulator(Node):
    """只模拟底盘和传感器；目标与路径全部交给真正的 Nav2。"""
    def __init__(self):
        super().__init__('lightweight_sim')
        self.x, self.y, self.yaw = 1., 1., 0.
        self.v = self.w = self.command_time = 0.
        self.drop_odom = self.drop_scan = self.blocked = False
        self.last = time.monotonic()
        self.tf = TransformBroadcaster(self)
        self.odom = self.create_publisher(Odometry, 'odom', qos_profile_sensor_data)
        self.scan = self.create_publisher(LaserScan, 'scan', qos_profile_sensor_data)
        self.create_subscription(Twist, 'cmd_vel', self.command, 10)
        for name in ('drop_odom', 'drop_scan', 'blocked'):
            self.create_service(SetBool, f'patrol/sim/{name}', self.switch(name))
        self.create_timer(.02, self.step)
        self.create_timer(.1, self.laser)

    def switch(self, name):
        def callback(req, res):
            setattr(self, name, req.data)
            res.success, res.message = True, f'{name}={req.data}'
            return res
        return callback

    def command(self, msg):
        if math.isfinite(msg.linear.x) and math.isfinite(msg.angular.z):
            self.v, self.w, self.command_time = msg.linear.x, msg.angular.z, time.monotonic()

    def step(self):
        now = time.monotonic()
        dt, self.last = min(now-self.last, .1), now
        v, w = (self.v, self.w) if now-self.command_time < .5 else (0., 0.)
        if self.blocked:
            v = w = 0.
        self.x, self.y, self.yaw, moved = integrate(self.x, self.y, self.yaw, v, w, dt)
        if self.drop_odom:
            return
        stamp = self.get_clock().now().to_msg()
        msg = Odometry()
        msg.header.stamp, msg.header.frame_id, msg.child_frame_id = stamp, 'odom', 'base_link'
        msg.pose.pose.position.x, msg.pose.pose.position.y = self.x, self.y
        msg.pose.pose.orientation.z, msg.pose.pose.orientation.w = math.sin(self.yaw/2), math.cos(self.yaw/2)
        msg.twist.twist.linear.x = v if moved else 0.
        msg.twist.twist.angular.z = w
        self.odom.publish(msg)
        tf = TransformStamped()
        tf.header, tf.child_frame_id = msg.header, 'base_link'
        tf.transform.translation.x, tf.transform.translation.y = self.x, self.y
        tf.transform.rotation = msg.pose.pose.orientation
        self.tf.sendTransform(tf)

    def laser(self):
        if self.drop_scan:
            return
        msg = LaserScan()
        msg.header.stamp, msg.header.frame_id = self.get_clock().now().to_msg(), 'base_scan'
        msg.angle_min, msg.angle_increment = -math.pi, 2*math.pi/180
        msg.angle_max = msg.angle_min + 179*msg.angle_increment
        msg.range_min, msg.range_max, msg.scan_time = .05, 10., .1
        msg.ranges = [float(raycast(self.x, self.y, self.yaw+msg.angle_min+i*msg.angle_increment)) for i in range(180)]
        self.scan.publish(msg)

def main():
    rclpy.init()
    node = Simulator()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

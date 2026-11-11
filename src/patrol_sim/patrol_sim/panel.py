import copy
import math
import queue
import threading
import time
import uuid
import rclpy
from rclpy.node import Node
from ament_index_python.packages import get_package_share_directory
from std_srvs.srv import SetBool, Trigger
from nav_msgs.msg import Path
from patrol_interfaces.msg import Incident, MissionStatus, TaskRecord
from tf2_ros import Buffer, TransformListener, TransformException
from patrol_sim.geometry import WALLS
from patrol_sim.http_api import serve
from patrol_sim.runtime import run_node

class Panel(Node):
    def __init__(self):
        super().__init__('control_panel')
        self.commands = queue.Queue(maxsize=100)
        self.lock = threading.Lock()
        self.state = dict(backend='ROS2 · Nav2', status={'state': 'STARTING'}, robot=[1.,1.,0.],
                          walls=WALLS, route=[], records=[], connected=False, feedback='')
        points = self.declare_parameter('waypoints',[1.,1.,0.,7.,1.,0.,7.,7.,0.,1.,7.,0.]).value
        self.state['waypoints'] = [points[i:i+2] for i in range(0,len(points),3)]
        self.last_status = -math.inf
        self.tf = Buffer()
        self.listener = TransformListener(self.tf, self)
        self.pub = self.create_publisher(Incident, 'patrol/incidents', 10)
        self.create_subscription(MissionStatus, 'patrol/status', self.status, 10)
        self.create_subscription(TaskRecord, 'patrol/records', self.record, 100)
        self.create_subscription(Path, 'plan', self.path, 10)
        self.service_clients = {name: self.create_client(typ, name) for name,typ in (
            ('patrol/set_paused',SetBool), ('patrol/emergency_stop',Trigger), ('patrol/recover',Trigger),
            ('patrol/sim/drop_odom',SetBool), ('patrol/sim/drop_scan',SetBool), ('patrol/sim/blocked',SetBool))}
        self.create_timer(.1, self.tick)
        self.server = serve(get_package_share_directory('patrol_sim')+'/web', self.snapshot, self.submit,
                            self.declare_parameter('port',8765).value)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.get_logger().info('Control panel: http://127.0.0.1:8765 (open inside Ubuntu)')

    def snapshot(self):
        with self.lock:
            result = copy.deepcopy(self.state)
        result['connected'] = time.monotonic()-self.last_status < 2
        return result

    def submit(self, message):
        if message.get('action') not in ('event','pause','resume','stop','recover','drop_odom','drop_scan','blocked'):
            raise ValueError('unknown action')
        try:
            self.commands.put_nowait(message)
        except queue.Full:
            raise ValueError('control queue full')
        return {'queued':True}

    def status(self, m):
        self.last_status = time.monotonic()
        with self.lock:
            self.state['status'] = {f:getattr(m,f) for f in m.get_fields_and_field_types() if f!='stamp'}

    def record(self, m):
        with self.lock:
            self.state['records'].append(dict(kind=m.kind,id=m.task_id,detail=m.detail,value=m.value))
            self.state['records'] = self.state['records'][-100:]

    def path(self, m):
        with self.lock:
            self.state['route'] = [[p.pose.position.x,p.pose.position.y] for p in m.poses]

    def feedback(self, text):
        with self.lock:
            self.state['feedback'] = text

    def completed(self, future):
        try:
            result = future.result()
            self.feedback(f'{result.success}: {result.message}')
        except Exception as error:
            self.feedback(str(error))

    def tick(self):
        try:
            tf = self.tf.lookup_transform('map','base_link',rclpy.time.Time())
            q = tf.transform.rotation
            yaw = math.atan2(2*(q.w*q.z+q.x*q.y),1-2*(q.y*q.y+q.z*q.z))
            with self.lock:
                self.state['robot'] = [tf.transform.translation.x,tf.transform.translation.y,yaw]
        except TransformException:
            pass
        for _ in range(10):
            try:
                cmd = self.commands.get_nowait()
            except queue.Empty:
                break
            try:
                self.execute(cmd)
            except (ValueError,KeyError,TypeError,OverflowError) as error:
                self.feedback(str(error))

    def execute(self, cmd):
        action = cmd['action']
        if action == 'event':
            x,y = float(cmd['x']),float(cmd['y'])
            priority,ttl,handling = int(cmd.get('priority',50)),float(cmd.get('ttl',120)),float(cmd.get('handling',3))
            if not all(math.isfinite(v) for v in (x,y,ttl,handling)) or not 1<=priority<=100 or not 0<ttl<=86400 or not 0<=handling<=3600:
                raise ValueError('invalid incident values')
            m = Incident()
            m.id = str(cmd.get('id') or uuid.uuid4().hex[:10])
            m.priority,m.ttl_sec,m.handling_sec = priority,ttl,handling
            m.target.header.frame_id,m.target.header.stamp = 'map',self.get_clock().now().to_msg()
            m.target.pose.position.x,m.target.pose.position.y,m.target.pose.orientation.w = x,y,1.
            m.description = str(cmd.get('description','control panel alarm'))
            self.pub.publish(m)
            self.feedback(f'Published {m.id}; see accepted/rejected record below.')
            return
        if action in ('pause','resume'):
            name,req = 'patrol/set_paused',SetBool.Request()
            req.data = action=='pause'
        elif action in ('stop','recover'):
            name,req = ('patrol/emergency_stop' if action=='stop' else 'patrol/recover'),Trigger.Request()
        else:
            name,req = 'patrol/sim/'+action,SetBool.Request()
            req.data = bool(cmd['enabled'])
        client = self.service_clients[name]
        if not client.service_is_ready():
            self.feedback(f'{name} unavailable (fault injection requires lightweight simulation)')
            return
        client.call_async(req).add_done_callback(self.completed)

def close_panel(node):
    try:
        node.server.shutdown()
    finally:
        node.server.server_close()
        node.thread.join(timeout=1.)


def main():
    run_node(Panel, close_panel)

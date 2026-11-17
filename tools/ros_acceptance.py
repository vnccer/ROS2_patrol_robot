#!/usr/bin/env python3
"""Black-box ROS2/Nav2 acceptance. Run after lightweight launch, not with desktop preview."""
import json
from pathlib import Path
import time
import uuid
import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from patrol_interfaces.msg import Incident, MissionStatus, TaskRecord
from std_srvs.srv import SetBool, Trigger
from patrol_interfaces.srv import CancelPending

class Acceptance(Node):
    # 等服务 → 填请求 → 发请求 → 等响应 → 返回结果
    def cancel_pending(self, ident):
        client = self.create_client(CancelPending, 'patrol/cancel_pending')
        try:
            assert client.wait_for_service(timeout_sec=5), 'cancel_pending service unavailable'
            request = CancelPending.Request()
            request.id = ident
            future = client.call_async(request)
            self.wait(future.done, 5, 'cancel_pending response')
            return future.result()
        finally:
            self.destroy_client(client)

    # 加入验收方法
    def check_pending_cancellation(self, suffix):
        self.service('patrol/set_paused', SetBool, True)

        # 暂停响应返回后，继续等旧导航真正终结。
        self.wait(
            lambda: self.status.state == 'PAUSED'
            and not self.status.active_id
            and self.status.queue_size == 0,
            10, 'paused with no active task'
        )
        self.wait(
            lambda: self.pub.get_subscription_count() > 0,
            5, 'incident subscriber discovered'
        )

        a = 'cancel-a-' + suffix
        b = 'cancel-b-' + suffix
        c = 'cancel-c-' + suffix

        for ident in (a, b, c):
            self.incident(
                ident, 50, 1.5, 1.5, handling=10, ttl=600
            )

        self.wait(
            lambda: all(self.saw('accepted', ident)
                        for ident in (a, b, c))
            and self.status.queue_size == 3,
            5, 'three incidents queued'
        )

        response = self.cancel_pending(b)
        assert response.success, response.message
        self.wait(
            lambda: self.status.queue_size == 2
            and self.saw('pending_cancelled', b),
            5, 'pending cancellation recorded'
        )

        response = self.cancel_pending(b)
        assert not response.success, \
            'repeated cancellation should fail'

        response = self.cancel_pending('missing-' + suffix)
        assert not response.success, \
            'unknown ID cancellation should fail'

        self.service('patrol/set_paused', SetBool, False)
        self.wait(
            lambda: self.status.active_id == a
            and self.saw('dispatched', a),
            10, 'first remaining incident dispatched'
        )

        response = self.cancel_pending(a)
        assert not response.success, \
            'active task must not be cancelled as pending'

        self.wait(
            lambda: self.saw('completed', a),
            100, 'first incident completed'
        )
        self.wait(
            lambda: self.saw('completed', c),
            100, 'last incident completed'
        )
        self.wait(
            lambda: self.status.state == 'PATROLLING',
            10, 'patrol restored after cancellation scenario'
        )

        assert not self.saw('dispatched', b), \
            'cancelled incident was dispatched'

        dispatched = [
            r.task_id for r in self.records
            if r.kind == 'dispatched' and r.task_id in (a, c)
        ]
        assert dispatched.index(a) < dispatched.index(c), \
            'remaining FIFO order changed'

        cancelled = [
            r for r in self.records
            if r.kind == 'pending_cancelled' and r.task_id == b
        ]
        assert len(cancelled) == 1, \
            'expected exactly one cancellation record'

    def __init__(self):
        super().__init__('patrol_acceptance')
        self.status = None
        self.records = []
        self.velocity = Twist()
        self.velocity_at = 0
        self.create_subscription(MissionStatus,'patrol/status',lambda m:setattr(self,'status',m),10)
        self.create_subscription(TaskRecord,'patrol/records',lambda m:self.records.append(m),100)
        self.create_subscription(Twist,'cmd_vel',self.on_velocity,10)
        self.pub = self.create_publisher(Incident,'patrol/incidents',10)

    def on_velocity(self,m):
        self.velocity,self.velocity_at = m,time.monotonic()

    def wait(self,predicate,timeout=20,label='condition'):
        end = time.monotonic()+timeout
        while time.monotonic()<end:
            rclpy.spin_once(self,timeout_sec=.05)
            if predicate():
                return
        raise AssertionError(f'Timeout: {label}; state={self.status}')

    def service(self,name,typ,value=None):
        client = self.create_client(typ,name)
        try:
            assert client.wait_for_service(timeout_sec=5),name
            req = typ.Request()
            if value is not None:
                req.data = value
            f = client.call_async(req)
            self.wait(f.done,5,name)
            assert f.result().success,f.result().message
        finally:
            self.destroy_client(client)

    def incident(self, ident, priority, x, y, handling=1, ttl=180):
        m = Incident()
        m.id = ident
        m.priority = priority
        m.ttl_sec = float(ttl)
        m.handling_sec = float(handling)
        m.target.header.frame_id = 'map'
        m.target.pose.position.x = float(x)
        m.target.pose.position.y = float(y)
        m.target.pose.orientation.w = 1.0
        self.pub.publish(m)

    def saw(self,kind,ident):
        return any(r.kind==kind and r.task_id==ident for r in self.records)

    def run(self):
        self.wait(lambda:self.status and self.status.state=='PATROLLING',90,'Nav2 startup')
        suffix = uuid.uuid4().hex[:8]
        self.check_pending_cancellation(suffix)
        low,high = 'low-'+suffix,'high-'+suffix
        self.incident(low,20,1.5,1.5)
        self.wait(lambda:self.status.active_id==low,10,'low event dispatch')
        self.incident(high,100,1.2,1.2)
        self.incident(high,100,1.2,1.2)
        self.wait(lambda:self.status.active_id==high,10,'priority preemption')
        self.wait(lambda:self.saw('completed',high),100,'high completion')
        self.wait(lambda:self.saw('completed',low),100,'low resume and completion')
        assert self.saw('duplicate',high),'duplicate was not recorded'
        self.wait(lambda:self.status.active_id.startswith('patrol/'),10,'patrol restoration')
        self.service('patrol/set_paused',SetBool,True)
        self.service('patrol/sim/drop_odom',SetBool,True)
        self.wait(lambda:self.status.state=='FAULT',5,'odometry fault')
        self.wait(lambda:time.monotonic()-self.velocity_at<.3 and abs(self.velocity.linear.x)<1e-9 and
                  abs(self.velocity.angular.z)<1e-9,2,'zero guarded velocity')
        self.service('patrol/sim/drop_odom',SetBool,False)
        self.wait(lambda:self.status.state=='FAULT',2,'latched fault')
        # Allow fresh odometry and terminal cancellation before recovery.
        self.wait(lambda:not self.status.motion_permitted,5,'permit disabled')
        deadline=time.monotonic()+8
        while True:
            try:
                self.service('patrol/recover',Trigger)
                break
            except AssertionError:
                if time.monotonic()>deadline:
                    raise
                rclpy.spin_once(self,timeout_sec=.2)
        self.wait(lambda:self.status.state=='PAUSED',3,'manual pause survives recovery')
        self.service('patrol/set_paused',SetBool,False)
        self.wait(lambda:self.status.state=='PATROLLING',10,'patrol resumed')
        return dict(result='PASS',backend='ROS2 Humble / real Nav2 / lightweight simulator',
                    cases=['startup','event preemption','event completion','nested resume','deduplication',
                           'patrol restore','odometry timeout','zero velocity','latched recovery','pause preserved',
                           'pending cancellation','repeated and unknown cancellation rejected','active task protected',
                           'remaining FIFO preserved','cancelled incident not dispatched'])

def main():
    rclpy.init()
    node=Acceptance()
    result={'result':'FAIL'}
    try:
        result=node.run()
    except Exception as error:
        result = {'result': 'FAIL', 'error': str(error)}
        raise
    finally:
        Path('test_results').mkdir(exist_ok=True)
        Path('test_results/ros_acceptance.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        node.destroy_node()
        rclpy.shutdown()
    print(json.dumps(result,indent=2))

if __name__=='__main__':
    main()

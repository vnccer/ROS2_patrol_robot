#!/usr/bin/env python3
"""Run launch in its own session and stop active navigation before SIGINT."""
from pathlib import Path
import signal
import subprocess
import sys
import time


def shutdown_ros():
    # Run in a short-lived helper so even failed ROS discovery has a deadline.
    import rclpy
    from nav2_msgs.srv import ManageLifecycleNodes
    from std_srvs.srv import Trigger

    rclpy.init(args=[])
    node = rclpy.create_node('patrol_shutdown')

    def call(service_type, name, request, timeout, retry=False):
        client = node.create_client(service_type, name)
        deadline = time.monotonic() + timeout
        try:
            if not client.wait_for_service(timeout_sec=2.):
                print(f'[patrol] Shutdown: {name} unavailable.', flush=True)
                return False
            while time.monotonic() < deadline:
                future = client.call_async(request)
                rclpy.spin_until_future_complete(
                    node, future, timeout_sec=max(0., deadline - time.monotonic()))
                if not future.done() or future.result() is None:
                    break
                if future.result().success:
                    return True
                if not retry:
                    print(f'[patrol] Shutdown: {name} rejected the request.', flush=True)
                    return False
                rclpy.spin_once(node, timeout_sec=.05)
            print(f'[patrol] Shutdown: {name} timed out.', flush=True)
            return False
        finally:
            node.destroy_client(client)

    try:
        # The manager reports ready only after the old action has a terminal
        # result. Keep Nav2 and the motion watchdog running until then.
        paused = call(Trigger, 'patrol/prepare_shutdown', Trigger.Request(), 5., retry=True)
        shutdown = ManageLifecycleNodes.Request()
        shutdown.command = ManageLifecycleNodes.Request.SHUTDOWN
        # Nav2's manager stops its nodes in reverse dependency order: the BT
        # cancels FollowPath while the controller and their contexts still live.
        stopped = call(ManageLifecycleNodes,
                       'lifecycle_manager_patrol/manage_nodes', shutdown, 10.)
        return 0 if paused and stopped else 1
    finally:
        node.destroy_node()
        rclpy.try_shutdown()


def supervise(arguments):
    stopping = False

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    previous = {sig: signal.signal(sig, request_stop)
                for sig in (signal.SIGINT, signal.SIGTERM)}
    process = None
    try:
        # Terminal Ctrl+C reaches this supervisor first, rather than shutting
        # down every ROS context while actions are still running.
        process = subprocess.Popen(
            ['ros2', 'launch', 'patrol_bringup', 'system.launch.py', *arguments],
            start_new_session=True)
        while not stopping:
            try:
                return process.wait(timeout=.2)
            except subprocess.TimeoutExpired:
                pass

        print('\n[patrol] Stopping patrol and shutting down Nav2...', flush=True)
        try:
            result = subprocess.run(
                [sys.executable, str(Path(__file__).resolve()), '--shutdown'],
                start_new_session=True, timeout=20., check=False)
            if result.returncode:
                print('[patrol] Graceful stop incomplete; stopping launch.', flush=True)
        except (OSError, subprocess.TimeoutExpired) as error:
            print(f'[patrol] Graceful stop incomplete: {error}', flush=True)
        if process.poll() is None:
            process.send_signal(signal.SIGINT)
        try:
            result = process.wait(timeout=15.)
        except subprocess.TimeoutExpired:
            print('[patrol] Launch did not exit; sending SIGTERM.', flush=True)
            process.terminate()
            try:
                result = process.wait(timeout=5.)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                return 1
            return result or 1
        return 0 if result in (0, -signal.SIGINT) else result
    finally:
        try:
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=5.)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
        finally:
            for sig, handler in previous.items():
                signal.signal(sig, handler)


if __name__ == '__main__':
    if sys.argv[1:] == ['--shutdown']:
        sys.exit(shutdown_ros())
    sys.exit(supervise(sys.argv[1:]))

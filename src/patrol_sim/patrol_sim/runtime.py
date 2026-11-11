"""Finish callbacks and node cleanup before invalidating the ROS context."""
import signal

import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.signals import SignalHandlerOptions


def run_node(factory, cleanup=None):
    stopping = False

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    previous = {sig: signal.signal(sig, request_stop)
                for sig in (signal.SIGINT, signal.SIGTERM)}
    node = None
    try:
        # The default rclpy signal handler shuts the context down immediately,
        # even if a timer is publishing. Let the current callback finish first.
        rclpy.init(signal_handler_options=SignalHandlerOptions.NO)
        node = factory()
        while not stopping and rclpy.ok():
            rclpy.spin_once(node, timeout_sec=.1)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        try:
            if node is not None:
                try:
                    if cleanup is not None:
                        cleanup(node)
                finally:
                    node.destroy_node()
        finally:
            try:
                if rclpy.ok():
                    rclpy.shutdown()
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)

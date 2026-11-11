"""Regression checks for ROS adapter failures, without requiring ROS on Windows."""
import importlib.util
from pathlib import Path
import signal
import subprocess
import sys
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def stub(monkeypatch, name, **attributes):
    module = ModuleType(name)
    module.__dict__.update(attributes)
    monkeypatch.setitem(sys.modules, name, module)
    return module


def fake_signals(monkeypatch):
    original = {signal.SIGINT: object(), signal.SIGTERM: object()}
    handlers = original.copy()

    def replace(sig, handler):
        old, handlers[sig] = handlers[sig], handler
        return old

    monkeypatch.setattr(signal, 'signal', replace)
    return handlers, original


@pytest.mark.parametrize('exit_signal', [signal.SIGINT, signal.SIGTERM])
def test_signal_during_callback_keeps_ros_alive_through_cleanup(monkeypatch, exit_signal):
    events = []
    context = dict(valid=False)
    handlers, original = fake_signals(monkeypatch)

    def init(**kwargs):
        context['valid'] = True

    def publish(label):
        assert context['valid'], 'publisher context was invalidated too early'
        events.append(label)

    def spin_once(node, **kwargs):
        handlers[exit_signal](exit_signal, None)
        publish('callback finished')

    def shutdown():
        context['valid'] = False
        events.append('context shutdown')

    stub(monkeypatch, 'rclpy', init=init, ok=lambda: context['valid'],
         spin_once=spin_once, shutdown=shutdown)
    stub(monkeypatch, 'rclpy.executors', ExternalShutdownException=type('ExternalStop', (Exception,), {}))
    stub(monkeypatch, 'rclpy.signals', SignalHandlerOptions=SimpleNamespace(NO=0))
    runtime = load('runtime_under_test', 'src/patrol_sim/patrol_sim/runtime.py')
    node = SimpleNamespace(destroy_node=lambda: events.append('node destroyed'))
    runtime.run_node(lambda: node, lambda n: publish('zero velocity'))
    assert events == ['callback finished', 'zero velocity', 'node destroyed', 'context shutdown']
    assert handlers == original


def test_cleanup_failure_still_destroys_node_and_restores_signals(monkeypatch):
    events = []
    handlers, original = fake_signals(monkeypatch)
    stub(monkeypatch, 'rclpy', init=Mock(), ok=lambda: True,
         spin_once=lambda *a, **kw: handlers[signal.SIGINT](signal.SIGINT, None),
         shutdown=lambda: events.append('shutdown'))
    stub(monkeypatch, 'rclpy.executors', ExternalShutdownException=type('ExternalStop', (Exception,), {}))
    stub(monkeypatch, 'rclpy.signals', SignalHandlerOptions=SimpleNamespace(NO=0))
    runtime = load('runtime_under_test', 'src/patrol_sim/patrol_sim/runtime.py')
    node = SimpleNamespace(destroy_node=lambda: events.append('destroy'))

    def fail(node):
        raise RuntimeError('cleanup failed')

    with pytest.raises(RuntimeError, match='cleanup failed'):
        runtime.run_node(lambda: node, fail)
    assert events == ['destroy', 'shutdown']
    assert handlers == original


def test_panel_starts_with_read_only_node_clients_and_routes_commands(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT / 'src/patrol_sim'))
    class Node:
        def __init__(self, name):
            self.created_clients = []

        @property
        def clients(self):
            # rclpy.Node.clients has no setter in Humble.
            return tuple(self.created_clients)

        def create_client(self, typ, name):
            client = Mock()
            self.created_clients.append(client)
            return client

        def declare_parameter(self, name, value):
            return SimpleNamespace(value=value)

        create_publisher = Mock()
        create_subscription = Mock()
        create_timer = Mock()
        get_logger = Mock()

    class Service:
        Request = SimpleNamespace

    stub(monkeypatch, 'rclpy')
    stub(monkeypatch, 'rclpy.node', Node=Node)
    stub(monkeypatch, 'ament_index_python.packages', get_package_share_directory=lambda n: str(ROOT))
    stub(monkeypatch, 'std_srvs.srv', SetBool=Service, Trigger=Service)
    stub(monkeypatch, 'nav_msgs.msg', Path=object)
    stub(monkeypatch, 'patrol_interfaces.msg', Incident=object, MissionStatus=object, TaskRecord=object)
    stub(monkeypatch, 'tf2_ros', Buffer=Mock(), TransformListener=Mock(), TransformException=Exception)
    stub(monkeypatch, 'patrol_sim.runtime', run_node=Mock())
    panel_module = load('panel_under_test', 'src/patrol_sim/patrol_sim/panel.py')
    monkeypatch.setattr(panel_module, 'serve', Mock())
    monkeypatch.setattr(panel_module.threading, 'Thread', Mock())
    panel = panel_module.Panel()
    assert len(panel.clients) == 6
    panel.execute({'action': 'pause'})
    client = panel.service_clients['patrol/set_paused']
    assert client.call_async.call_args.args[0].data is True
    panel.execute({'action': 'drop_scan', 'enabled': True})
    assert panel.service_clients['patrol/sim/drop_scan'].call_async.call_args.args[0].data is True
    panel_module.close_panel(panel)
    panel.server.shutdown.assert_called_once()
    panel.server.server_close.assert_called_once()
    panel.thread.join.assert_called_once()


@pytest.mark.parametrize('helper_result', [0, 1, 'timeout'])
def test_supervisor_runs_shutdown_before_signalling_isolated_launch(monkeypatch, helper_result):
    runner = load('runner_under_test', 'tools/run_system.py')
    events = []
    handlers, original = fake_signals(monkeypatch)
    finished = False

    def wait(timeout):
        nonlocal finished
        if timeout == .2:
            handlers[signal.SIGINT](signal.SIGINT, None)
            raise subprocess.TimeoutExpired('launch', timeout)
        events.append('exit')
        finished = True
        return 0

    process = Mock(wait=wait, poll=lambda: 0 if finished else None,
                   send_signal=lambda sig: events.append('signal'))
    popen = Mock(return_value=process)
    monkeypatch.setattr(runner.subprocess, 'Popen', popen)

    def helper(*args, **kwargs):
        events.append('graceful shutdown')
        assert kwargs['start_new_session'] is True
        if helper_result == 'timeout':
            raise subprocess.TimeoutExpired('shutdown', 20)
        return SimpleNamespace(returncode=helper_result)

    monkeypatch.setattr(runner.subprocess, 'run', helper)
    assert runner.supervise(['rviz:=false', 'panel:=false']) == 0
    assert popen.call_args.kwargs['start_new_session'] is True
    assert popen.call_args.args[0][-2:] == ['rviz:=false', 'panel:=false']
    assert events == ['graceful shutdown', 'signal', 'exit']
    assert handlers == original


def test_supervisor_preserves_unexpected_launch_failure(monkeypatch):
    runner = load('runner_under_test', 'tools/run_system.py')
    handlers, original = fake_signals(monkeypatch)
    monkeypatch.setattr(runner.subprocess, 'Popen', Mock(return_value=Mock(wait=lambda **kw: 7, poll=lambda: 7)))
    helper = Mock()
    monkeypatch.setattr(runner.subprocess, 'run', helper)
    assert runner.supervise([]) == 7
    helper.assert_not_called()
    assert handlers == original


@pytest.mark.parametrize('pause_available', [True, False])
@pytest.mark.parametrize('ready_after', [1, 2])
def test_shutdown_waits_for_navigation_before_nav2_shutdown(monkeypatch, pause_available, ready_after):
    runner = load('runner_under_test', 'tools/run_system.py')
    calls = []

    class Trigger:
        Request = SimpleNamespace

    class ManageLifecycleNodes:
        class Request:
            SHUTDOWN = 4

    def create_client(typ, name):
        def call_async(request):
            calls.append((name, request))
            ready = typ is ManageLifecycleNodes or len(calls) >= ready_after
            return Mock(done=lambda: True, result=lambda: SimpleNamespace(success=ready))

        return Mock(wait_for_service=lambda **kw: pause_available or typ is ManageLifecycleNodes,
                    call_async=call_async)

    node = Mock(create_client=create_client)
    ros = stub(monkeypatch, 'rclpy', init=Mock(), create_node=lambda name: node,
               spin_until_future_complete=Mock(), spin_once=Mock(), try_shutdown=Mock())
    stub(monkeypatch, 'nav2_msgs.srv', ManageLifecycleNodes=ManageLifecycleNodes)
    stub(monkeypatch, 'std_srvs.srv', Trigger=Trigger)
    assert runner.shutdown_ros() == (0 if pause_available else 1)
    if pause_available:
        assert [name for name, _ in calls[:-1]] == ['patrol/prepare_shutdown'] * ready_after
    assert calls[-1][0] == 'lifecycle_manager_patrol/manage_nodes'
    assert calls[-1][1].command == ManageLifecycleNodes.Request.SHUTDOWN
    node.destroy_node.assert_called_once()
    ros.try_shutdown.assert_called_once()

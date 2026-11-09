"""Humble launch: same mission/Nav2/guard with two interchangeable sensor backends."""
from pathlib import Path
import yaml
from ament_index_python.packages import get_package_share_directory as share
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction, SetEnvironmentVariable
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.descriptions import ParameterFile
from nav2_common.launch import RewrittenYaml

def setup(context):
    root = Path(share('patrol_bringup'))
    backend = LaunchConfiguration('backend').perform(context)
    if backend not in ('lightweight', 'gazebo'):
        raise ValueError('backend must be lightweight or gazebo')
    sim_time = backend == 'gazebo'
    mission_path = LaunchConfiguration('mission').perform(context)
    params_path = LaunchConfiguration('nav_params').perform(context)
    mission = yaml.safe_load(Path(mission_path).read_text(encoding='utf-8'))['mission_manager']['ros__parameters']
    nav = yaml.safe_load(Path(params_path).read_text(encoding='utf-8'))
    configured_nav = ParameterFile(RewrittenYaml(source_file=params_path,
        param_rewrites={'use_sim_time':str(sim_time).lower()},convert_types=True))
    nodes = []

    def node(pkg, executable, name=None, parameters=None, **kw):
        return Node(package=pkg, executable=executable, name=name or executable,
                    parameters=parameters or [], output='screen', **kw)

    if not sim_time:
        nodes += [node('patrol_sim','lightweight_sim'),
                  node('tf2_ros','static_transform_publisher',name='map_to_odom',arguments=[
                      '--x','0','--y','0','--z','0','--roll','0','--pitch','0','--yaw','0',
                      '--frame-id','map','--child-frame-id','odom']),
                  node('robot_state_publisher','robot_state_publisher',parameters=[{
                      'robot_description':(root/'urdf/patrol.urdf').read_text(), 'use_sim_time':False}])]
    else:
        # 复用 ROBOTIS Humble 的机器人模型、生成器和关节 TF，不复制模型。
        tb = Path(share('turtlebot3_gazebo'))
        gz = Path(share('gazebo_ros'))
        nodes.append(SetEnvironmentVariable('TURTLEBOT3_MODEL','burger'))
        nodes.append(IncludeLaunchDescription(PythonLaunchDescriptionSource(str(gz/'launch/gzserver.launch.py')),
                     launch_arguments={'world':str(root/'worlds/indoor.world')}.items()))
        if LaunchConfiguration('gui').perform(context).lower()=='true':
            nodes.append(IncludeLaunchDescription(PythonLaunchDescriptionSource(str(gz/'launch/gzclient.launch.py'))))
        nodes += [IncludeLaunchDescription(PythonLaunchDescriptionSource(str(tb/'launch/robot_state_publisher.launch.py')),
                      launch_arguments={'use_sim_time':'true'}.items()),
                  IncludeLaunchDescription(PythonLaunchDescriptionSource(str(tb/'launch/spawn_turtlebot3.launch.py')),
                      launch_arguments={'x_pose':'1.0','y_pose':'1.0'}.items())]

    lifecycle = ['map_server']
    nodes.append(node('nav2_map_server','map_server',parameters=[{
        'yaml_filename':str(root/'maps/indoor.yaml'),'use_sim_time':sim_time}]))
    if sim_time:
        amcl = nav['amcl']['ros__parameters'].copy()
        amcl.update(use_sim_time=True,set_initial_pose=True,
                    initial_pose={'x':1.,'y':1.,'z':0.,'yaw':0.})
        nodes.append(node('nav2_amcl','amcl',parameters=[amcl]))
        lifecycle.append('amcl')
    components = [('nav2_controller','controller_server'),('nav2_smoother','smoother_server'),
                  ('nav2_planner','planner_server'),('nav2_behaviors','behavior_server'),
                  ('nav2_bt_navigator','bt_navigator'),('nav2_velocity_smoother','velocity_smoother')]
    for pkg,name in components:
        remaps = []
        if name == 'controller_server':
            remaps = [('cmd_vel','raw_cmd_vel')]
        elif name == 'velocity_smoother':
            remaps = [('cmd_vel','raw_cmd_vel'),('cmd_vel_smoothed','nav_cmd_vel')]
        elif name == 'behavior_server':
            remaps = [('cmd_vel','nav_cmd_vel')]
        # 整份参数文件保证 global/local costmap 子节点能拿到各自配置。
        nodes.append(node(pkg,name,parameters=[configured_nav],remappings=remaps))
        lifecycle.append(name)
    nodes += [node('nav2_lifecycle_manager','lifecycle_manager',name='lifecycle_manager_patrol',parameters=[{
                  'use_sim_time':sim_time,'autostart':True,'node_names':lifecycle}]),
              node('patrol_manager','mission_manager',parameters=[mission_path,{'use_sim_time':sim_time}]),
              node('patrol_sim','velocity_guard',parameters=[{'use_sim_time':sim_time}])]
    if LaunchConfiguration('panel').perform(context).lower()=='true':
        nodes.append(node('patrol_sim','control_panel',parameters=[{'use_sim_time':sim_time,
                     'waypoints':mission['waypoints']}]))
    if LaunchConfiguration('rviz').perform(context).lower()=='true':
        nodes.append(node('rviz2','rviz2',arguments=['-d',str(root/'rviz/patrol.rviz')],
                          parameters=[{'use_sim_time':sim_time}]))
    return nodes

def generate_launch_description():
    root = Path(share('patrol_bringup'))
    return LaunchDescription([
        DeclareLaunchArgument('backend',default_value='lightweight',description='lightweight | gazebo'),
        DeclareLaunchArgument('rviz',default_value='true'),
        DeclareLaunchArgument('gui',default_value='false',description='Gazebo GUI; headless is easier on VMware'),
        DeclareLaunchArgument('panel',default_value='true'),
        DeclareLaunchArgument('mission',default_value=str(root/'config/mission.yaml')),
        DeclareLaunchArgument('nav_params',default_value=str(root/'config/nav2.yaml')),
        OpaqueFunction(function=setup)])

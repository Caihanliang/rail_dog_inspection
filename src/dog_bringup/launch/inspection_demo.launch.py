"""Offline demo: fake odom + static lidar TF + PCD publish + filter + mission."""

import math
import os
from pathlib import Path

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, OpaqueFunction
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def _workspace_root() -> Path:
    env = os.environ.get('RAIL_DOG_WS')
    if env:
        return Path(env)
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / 'data' / 'raw').is_dir() and (parent / 'src').is_dir():
            return parent
    # source-tree fallback: .../rail_dog_inspection/src/dog_bringup/launch
    return here.parents[3]


def _degrees_to_quaternion(roll_deg, pitch_deg, yaw_deg):
    roll = math.radians(roll_deg)
    pitch = math.radians(pitch_deg)
    yaw = math.radians(yaw_deg)
    cy, sy = math.cos(yaw * 0.5), math.sin(yaw * 0.5)
    cp, sp = math.cos(pitch * 0.5), math.sin(pitch * 0.5)
    cr, sr = math.cos(roll * 0.5), math.sin(roll * 0.5)
    qw = cr * cp * cy + sr * sp * sy
    qx = sr * cp * cy - cr * sp * sy
    qy = cr * sp * cy + sr * cp * sy
    qz = cr * cp * sy - sr * sp * cy
    return qx, qy, qz, qw


def _launch_setup(context, *args, **kwargs):
    bringup_share = get_package_share_directory('dog_bringup')
    inspection_share = get_package_share_directory('dog_inspection')
    ws = _workspace_root()

    pcd_path = LaunchConfiguration('pcd_path').perform(context)
    if not os.path.isabs(pcd_path):
        pcd_path = str(ws / pcd_path)

    records_dir = LaunchConfiguration('records_dir').perform(context)
    if not os.path.isabs(records_dir):
        records_dir = str(ws / records_dir)

    mission_config = str(
        Path(inspection_share) / 'config' / 'mission_points.yaml'
    )
    params_file = str(Path(bringup_share) / 'config' / 'bringup_params.yaml')

    # base_link -> lidar_link (matches config/static_tf.yaml defaults)
    qx, qy, qz, qw = _degrees_to_quaternion(0.0, 0.0, 0.0)

    static_tf = Node(
        package='tf2_ros',
        executable='static_transform_publisher',
        name='lidar_static_tf',
        arguments=[
            '--x', '0.35',
            '--y', '0.0',
            '--z', '0.45',
            '--qx', str(qx),
            '--qy', str(qy),
            '--qz', str(qz),
            '--qw', str(qw),
            '--frame-id', 'base_link',
            '--child-frame-id', 'lidar_link',
        ],
    )

    fake_odom = Node(
        package='dog_bringup',
        executable='fake_odom_publisher',
        name='fake_odom_publisher',
        output='screen',
        parameters=[params_file],
    )

    pcd_publisher = Node(
        package='dog_perception',
        executable='pcd_publisher',
        name='pcd_publisher',
        output='screen',
        parameters=[
            params_file,
            {'pcd_path': pcd_path},
        ],
    )

    cloud_preprocess = Node(
        package='dog_perception',
        executable='cloud_preprocess',
        name='cloud_preprocess',
        output='screen',
        parameters=[params_file],
    )

    mission_manager = Node(
        package='dog_inspection',
        executable='mission_manager',
        name='mission_manager',
        output='screen',
        parameters=[
            params_file,
            {
                'mission_config': mission_config,
                'records_dir': records_dir,
            },
        ],
    )

    return [
        static_tf,
        fake_odom,
        pcd_publisher,
        cloud_preprocess,
        mission_manager,
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument(
            'pcd_path',
            default_value='data/raw/sample_rail_scene.pcd',
            description='Path to PCD file (absolute or relative to workspace root)',
        ),
        DeclareLaunchArgument(
            'records_dir',
            default_value='data/records',
            description='Directory for inspection records',
        ),
        OpaqueFunction(function=_launch_setup),
    ])

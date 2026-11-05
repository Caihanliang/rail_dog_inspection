"""Inspection mission state machine: arrive -> capture cloud -> log -> next."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import rclpy
import yaml
from geometry_msgs.msg import Pose, PoseStamped
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.time import Time
from sensor_msgs.msg import PointCloud2
from tf2_ros import Buffer, TransformException, TransformListener
from tf_transformations import quaternion_from_euler

from dog_interfaces.msg import InspectionRecord, MissionStatus
from dog_interfaces.srv import CaptureNow, StartMission
from dog_perception.pointcloud_utils import cloud_to_points, write_pcd_ascii


class MissionManager(Node):
    def __init__(self):
        super().__init__('mission_manager')

        self.declare_parameter('mission_config', 'config/mission_points.yaml')
        self.declare_parameter('cloud_topic', '/lidar/points_filtered')
        self.declare_parameter('records_dir', 'data/records')
        self.declare_parameter('arrive_pos_tol_m', 1.5)
        self.declare_parameter('arrive_yaw_tol_deg', 30.0)
        self.declare_parameter('auto_advance', True)
        self.declare_parameter('capture_on_arrive', True)
        self.declare_parameter('demo_teleport', True)
        self.declare_parameter('base_frame', 'base_link')
        self.declare_parameter('map_frame', 'map')

        config_path = str(self.get_parameter('mission_config').value)
        self._records_root = Path(str(self.get_parameter('records_dir').value))
        self._arrive_tol = float(self.get_parameter('arrive_pos_tol_m').value)
        self._yaw_tol = math.radians(
            float(self.get_parameter('arrive_yaw_tol_deg').value)
        )
        self._auto_advance = bool(self.get_parameter('auto_advance').value)
        self._capture_on_arrive = bool(
            self.get_parameter('capture_on_arrive').value
        )
        self._demo_teleport = bool(self.get_parameter('demo_teleport').value)
        self._base_frame = str(self.get_parameter('base_frame').value)
        self._map_frame = str(self.get_parameter('map_frame').value)

        self._mission = self._load_mission(config_path)
        self._points: List[Dict[str, Any]] = self._mission.get('points', [])
        self._mission_name = str(self._mission.get('name', 'default_mission'))

        self._state = 'IDLE'
        self._index = 0
        self._latest_cloud: Optional[PointCloud2] = None
        self._session_dir: Optional[Path] = None
        self._report: List[Dict[str, Any]] = []

        cloud_topic = str(self.get_parameter('cloud_topic').value)
        self.create_subscription(PointCloud2, cloud_topic, self._on_cloud, 10)

        self._tf_buffer = Buffer()
        self._tf_listener = TransformListener(self._tf_buffer, self)

        self._status_pub = self.create_publisher(MissionStatus, '/inspection/status', 10)
        self._record_pub = self.create_publisher(
            InspectionRecord, '/inspection/record', 10
        )
        self._teleport_pub = self.create_publisher(
            PoseStamped, '/demo/set_base_pose', 10
        )

        self.create_service(StartMission, '/inspection/start_mission', self._on_start)
        self.create_service(CaptureNow, '/inspection/capture_now', self._on_capture)

        self.create_timer(0.5, self._tick)

        self.get_logger().info(
            f'Mission "{self._mission_name}" loaded with {len(self._points)} points. '
            'Call /inspection/start_mission to begin.'
        )
        self._publish_status('Waiting for StartMission')

    def _load_mission(self, path: str) -> Dict[str, Any]:
        with open(path, 'r', encoding='utf-8') as handle:
            data = yaml.safe_load(handle) or {}
        return data.get('mission', data)

    def _on_cloud(self, msg: PointCloud2):
        self._latest_cloud = msg

    def _on_start(self, request: StartMission.Request, response: StartMission.Response):
        if request.mission_name:
            self._mission_name = request.mission_name
        if request.reset_to_first or self._state in ('IDLE', 'DONE', 'FAULT'):
            self._index = 0
            self._report = []
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self._session_dir = (
                self._records_root / f'{stamp}_{self._mission_name}'
            )
            self._session_dir.mkdir(parents=True, exist_ok=True)

        if not self._points:
            response.success = False
            response.message = 'No mission points configured'
            self._state = 'FAULT'
            return response

        self._state = 'GO_TO_POINT'
        if self._demo_teleport and self._points:
            self._teleport_to_point(self._points[self._index])
        response.success = True
        response.message = (
            f'Started mission {self._mission_name} at index {self._index}'
        )
        self.get_logger().info(response.message)
        self._publish_status(response.message)
        return response

    def _on_capture(self, request: CaptureNow.Request, response: CaptureNow.Response):
        point_id = request.point_id or self._current_point_id()
        if self._state not in ('ARRIVED', 'CAPTURE', 'GO_TO_POINT', 'LOG') and not request.force:
            response.success = False
            response.message = f'Cannot capture in state {self._state} (set force=true)'
            return response

        ok, message, cloud_path, alert, reason = self._capture(point_id)
        response.success = ok
        response.message = message
        response.cloud_path = cloud_path
        response.alert = alert
        response.alert_reason = reason
        return response

    def _current_point_id(self) -> str:
        if not self._points or self._index >= len(self._points):
            return ''
        return str(self._points[self._index]['id'])

    def _tick(self):
        if self._state == 'GO_TO_POINT':
            if self._index >= len(self._points):
                self._finish()
                return
            if self._is_arrived(self._points[self._index]):
                self._state = 'ARRIVED'
                self._publish_status('Arrived at point')
                if self._capture_on_arrive:
                    self._state = 'CAPTURE'
                    self._do_capture_current()
            else:
                self._publish_status('Navigating / waiting near point')
        elif self._state in ('IDLE', 'DONE', 'FAULT', 'ARRIVED', 'LOG', 'NEXT'):
            self._publish_status(self._state)

    def _do_capture_current(self):
        point = self._points[self._index]
        point_id = str(point['id'])
        ok, message, *_ = self._capture(point_id)
        self._state = 'LOG'
        self._publish_status(message)
        if not ok:
            self._state = 'FAULT'
            return

        if self._auto_advance:
            self._index += 1
            if self._index >= len(self._points):
                self._finish()
            else:
                if self._demo_teleport:
                    self._teleport_to_point(self._points[self._index])
                self._state = 'GO_TO_POINT'
                self._publish_status('Advance to next point')
        else:
            self._state = 'ARRIVED'

    def _finish(self):
        self._state = 'DONE'
        if self._session_dir is not None:
            report_path = self._session_dir / 'report.json'
            payload = {
                'mission_name': self._mission_name,
                'records': self._report,
            }
            report_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding='utf-8',
            )
            self.get_logger().info(f'Mission done. Report: {report_path}')
        self._publish_status('Mission complete')

    def _is_arrived(self, point: Dict[str, Any]) -> bool:
        try:
            tf = self._tf_buffer.lookup_transform(
                self._map_frame,
                self._base_frame,
                Time(),
                timeout=Duration(seconds=0.1),
            )
        except TransformException:
            return False

        tx = tf.transform.translation.x
        ty = tf.transform.translation.y
        goal = point['xyz']
        dist = math.hypot(tx - float(goal[0]), ty - float(goal[1]))
        return dist <= self._arrive_tol

    def _teleport_to_point(self, point: Dict[str, Any]):
        xyz = point['xyz']
        yaw = float(point.get('yaw', 0.0))
        qx, qy, qz, qw = quaternion_from_euler(0.0, 0.0, yaw)
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = self._map_frame
        msg.pose.position.x = float(xyz[0])
        msg.pose.position.y = float(xyz[1])
        msg.pose.position.z = float(xyz[2])
        msg.pose.orientation.x = qx
        msg.pose.orientation.y = qy
        msg.pose.orientation.z = qz
        msg.pose.orientation.w = qw
        self._teleport_pub.publish(msg)

    def _capture(self, point_id: str):
        if self._latest_cloud is None:
            return False, 'No point cloud received yet', '', False, ''

        if self._session_dir is None:
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            self._session_dir = self._records_root / f'{stamp}_{self._mission_name}'
            self._session_dir.mkdir(parents=True, exist_ok=True)

        point_cfg = next((p for p in self._points if str(p['id']) == point_id), None)
        stamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        point_dir = self._session_dir / point_id
        point_dir.mkdir(parents=True, exist_ok=True)

        try:
            points = cloud_to_points(self._latest_cloud)
        except ValueError as exc:
            return False, str(exc), '', False, ''

        cloud_path = point_dir / f'{stamp_str}.pcd'
        write_pcd_ascii(cloud_path, points)

        alert, reason = self._check_roi(points, point_cfg)
        pose = self._lookup_pose()

        meta = {
            'mission_name': self._mission_name,
            'point_id': point_id,
            'cloud_path': str(cloud_path),
            'num_points': len(points),
            'alert': alert,
            'alert_reason': reason,
            'pose': pose,
            'stamp': stamp_str,
        }
        meta_path = point_dir / f'{stamp_str}_meta.json'
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding='utf-8'
        )

        self._report.append(meta)
        self._publish_record(meta, pose)

        msg = f'Captured {point_id}: {cloud_path.name}'
        if alert:
            msg += f' [ALERT: {reason}]'
        self.get_logger().info(msg)
        return True, msg, str(cloud_path), alert, reason

    def _check_roi(self, points, point_cfg):
        if not point_cfg or 'roi' not in point_cfg:
            return False, ''
        roi = point_cfg['roi']
        min_xyz = roi['min_xyz']
        max_xyz = roi['max_xyz']
        min_points = int(roi.get('min_points', 50))

        # Cloud is in lidar_link; sample scene cabinets are in roughly map/world
        # meters. For the offline demo the PCD is authored in a corridor frame
        # that matches mission XYZ, so ROI uses the same numeric coordinates.
        count = 0
        for x, y, z, _intensity in points:
            if (
                min_xyz[0] <= x <= max_xyz[0]
                and min_xyz[1] <= y <= max_xyz[1]
                and min_xyz[2] <= z <= max_xyz[2]
            ):
                count += 1

        if count < min_points:
            return True, f'ROI points too few ({count} < {min_points})'
        return False, ''

    def _lookup_pose(self) -> Dict[str, float]:
        try:
            tf = self._tf_buffer.lookup_transform(
                self._map_frame,
                self._base_frame,
                Time(),
                timeout=Duration(seconds=0.1),
            )
            t = tf.transform.translation
            r = tf.transform.rotation
            return {
                'x': t.x, 'y': t.y, 'z': t.z,
                'qx': r.x, 'qy': r.y, 'qz': r.z, 'qw': r.w,
            }
        except TransformException:
            return {}

    def _publish_status(self, message: str):
        msg = MissionStatus()
        msg.mission_name = self._mission_name
        msg.state = self._state
        msg.current_point_id = self._current_point_id()
        msg.current_index = self._index
        msg.total_points = len(self._points)
        msg.message = message
        msg.stamp = self.get_clock().now().to_msg()
        self._status_pub.publish(msg)

    def _publish_record(self, meta: Dict[str, Any], pose_dict: Dict[str, float]):
        msg = InspectionRecord()
        msg.mission_name = meta['mission_name']
        msg.point_id = meta['point_id']
        msg.cloud_path = meta['cloud_path']
        msg.meta_path = str(
            Path(meta['cloud_path']).with_name(
                Path(meta['cloud_path']).stem + '_meta.json'
            )
        )
        msg.alert = bool(meta['alert'])
        msg.alert_reason = meta['alert_reason']
        msg.stamp = self.get_clock().now().to_msg()
        pose = Pose()
        if pose_dict:
            pose.position.x = float(pose_dict.get('x', 0.0))
            pose.position.y = float(pose_dict.get('y', 0.0))
            pose.position.z = float(pose_dict.get('z', 0.0))
            pose.orientation.x = float(pose_dict.get('qx', 0.0))
            pose.orientation.y = float(pose_dict.get('qy', 0.0))
            pose.orientation.z = float(pose_dict.get('qz', 0.0))
            pose.orientation.w = float(pose_dict.get('qw', 1.0))
        msg.pose = pose
        self._record_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = MissionManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

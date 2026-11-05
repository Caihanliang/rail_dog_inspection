"""Range / height crop + simple voxel downsample for PointCloud2 streams."""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Header

from dog_perception.pointcloud_utils import cloud_to_points, points_to_cloud, Point


class CloudPreprocess(Node):
    def __init__(self):
        super().__init__('cloud_preprocess')

        self.declare_parameter('input_topic', '/lidar/points')
        self.declare_parameter('output_topic', '/lidar/points_filtered')
        self.declare_parameter('min_range', 0.5)
        self.declare_parameter('max_range', 30.0)
        self.declare_parameter('min_z', 0.05)
        self.declare_parameter('max_z', 2.5)
        self.declare_parameter('voxel_leaf', 0.08)

        input_topic = str(self.get_parameter('input_topic').value)
        output_topic = str(self.get_parameter('output_topic').value)

        self._pub = self.create_publisher(PointCloud2, output_topic, 10)
        self.create_subscription(PointCloud2, input_topic, self._callback, 10)

        self.get_logger().info(
            f'Preprocess: {input_topic} -> {output_topic}'
        )

    def _callback(self, msg: PointCloud2):
        min_range = float(self.get_parameter('min_range').value)
        max_range = float(self.get_parameter('max_range').value)
        min_z = float(self.get_parameter('min_z').value)
        max_z = float(self.get_parameter('max_z').value)
        leaf = float(self.get_parameter('voxel_leaf').value)

        try:
            raw = cloud_to_points(msg)
        except ValueError as exc:
            self.get_logger().warn(str(exc))
            return

        filtered: List[Point] = []
        for x, y, z, intensity in raw:
            rng = math.hypot(x, y)
            if rng < min_range or rng > max_range:
                continue
            if z < min_z or z > max_z:
                continue
            filtered.append((x, y, z, intensity))

        down = self._voxel_downsample(filtered, leaf) if leaf > 1e-6 else filtered

        header = Header()
        header.stamp = msg.header.stamp
        header.frame_id = msg.header.frame_id
        self._pub.publish(points_to_cloud(down, header))

    @staticmethod
    def _voxel_downsample(points: List[Point], leaf: float) -> List[Point]:
        buckets: Dict[Tuple[int, int, int], Point] = {}
        inv = 1.0 / leaf
        for x, y, z, intensity in points:
            key = (int(math.floor(x * inv)), int(math.floor(y * inv)), int(math.floor(z * inv)))
            # Keep first point in each voxel (fast & deterministic enough for demo)
            if key not in buckets:
                buckets[key] = (x, y, z, intensity)
        return list(buckets.values())


def main(args=None):
    rclpy.init(args=args)
    node = CloudPreprocess()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

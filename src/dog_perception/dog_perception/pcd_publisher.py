"""Load a PCD file and publish it as sensor_msgs/PointCloud2."""

from pathlib import Path

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import PointCloud2
from std_msgs.msg import Header

from dog_perception.pointcloud_utils import points_to_cloud, read_pcd_ascii


class PcdPublisher(Node):
    def __init__(self):
        super().__init__('pcd_publisher')

        self.declare_parameter('pcd_path', 'data/raw/sample_rail_scene.pcd')
        self.declare_parameter('frame_id', 'map')
        self.declare_parameter('topic', '/lidar/points')
        self.declare_parameter('publish_rate_hz', 2.0)
        self.declare_parameter('loop', True)

        pcd_path = str(self.get_parameter('pcd_path').value)
        self._frame_id = str(self.get_parameter('frame_id').value)
        topic = str(self.get_parameter('topic').value)
        rate = float(self.get_parameter('publish_rate_hz').value)
        self._loop = bool(self.get_parameter('loop').value)

        self._points = read_pcd_ascii(pcd_path)
        self._pub = self.create_publisher(PointCloud2, topic, 10)
        self.create_timer(1.0 / max(rate, 0.1), self._on_timer)
        self._published_once = False

        self.get_logger().info(
            f'Loaded {len(self._points)} points from {Path(pcd_path).name}; '
            f'publishing on {topic} (frame={self._frame_id})'
        )

    def _on_timer(self):
        if self._published_once and not self._loop:
            return

        header = Header()
        header.stamp = self.get_clock().now().to_msg()
        header.frame_id = self._frame_id
        self._pub.publish(points_to_cloud(self._points, header))
        self._published_once = True


def main(args=None):
    rclpy.init(args=args)
    node = PcdPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

"""Publish a simple fake odom TF for offline PCD demos without a real dog."""

import math

import rclpy
from geometry_msgs.msg import PoseStamped, TransformStamped
from rclpy.node import Node
from tf2_ros import TransformBroadcaster
from tf_transformations import quaternion_from_euler


class FakeOdomPublisher(Node):
    """Publishes map->odom (identity) and odom->base_link.

    Pose can be changed live via /demo/set_base_pose (PoseStamped in map).
    """

    def __init__(self):
        super().__init__('fake_odom_publisher')

        self.declare_parameter('x', 1.0)
        self.declare_parameter('y', 0.0)
        self.declare_parameter('z', 0.0)
        self.declare_parameter('yaw_deg', 0.0)
        self.declare_parameter('publish_rate_hz', 20.0)

        self._x = float(self.get_parameter('x').value)
        self._y = float(self.get_parameter('y').value)
        self._z = float(self.get_parameter('z').value)
        self._yaw_deg = float(self.get_parameter('yaw_deg').value)

        self._broadcaster = TransformBroadcaster(self)
        self.create_subscription(
            PoseStamped, '/demo/set_base_pose', self._on_set_pose, 10
        )

        rate = float(self.get_parameter('publish_rate_hz').value)
        self.create_timer(1.0 / max(rate, 1.0), self._publish)

        self.get_logger().info(
            'Fake odom TF running. Update pose with /demo/set_base_pose'
        )

    def _on_set_pose(self, msg: PoseStamped):
        self._x = msg.pose.position.x
        self._y = msg.pose.position.y
        self._z = msg.pose.position.z
        # yaw from quaternion (z,w dominant for planar)
        qw = msg.pose.orientation.w
        qz = msg.pose.orientation.z
        self._yaw_deg = math.degrees(2.0 * math.atan2(qz, qw))
        self.get_logger().info(
            f'Teleport base_link -> ({self._x:.2f}, {self._y:.2f}), '
            f'yaw={self._yaw_deg:.1f}°'
        )

    def _publish(self):
        now = self.get_clock().now().to_msg()

        map_to_odom = TransformStamped()
        map_to_odom.header.stamp = now
        map_to_odom.header.frame_id = 'map'
        map_to_odom.child_frame_id = 'odom'
        map_to_odom.transform.rotation.w = 1.0
        self._broadcaster.sendTransform(map_to_odom)

        yaw = math.radians(self._yaw_deg)
        qx, qy, qz, qw = quaternion_from_euler(0.0, 0.0, yaw)

        odom_to_base = TransformStamped()
        odom_to_base.header.stamp = now
        odom_to_base.header.frame_id = 'odom'
        odom_to_base.child_frame_id = 'base_link'
        odom_to_base.transform.translation.x = self._x
        odom_to_base.transform.translation.y = self._y
        odom_to_base.transform.translation.z = self._z
        odom_to_base.transform.rotation.x = qx
        odom_to_base.transform.rotation.y = qy
        odom_to_base.transform.rotation.z = qz
        odom_to_base.transform.rotation.w = qw
        self._broadcaster.sendTransform(odom_to_base)


def main(args=None):
    rclpy.init(args=args)
    node = FakeOdomPublisher()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

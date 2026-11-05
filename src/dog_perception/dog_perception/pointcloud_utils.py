"""Minimal PCD (ASCII xyz[i]) reader and PointCloud2 helpers (no PCL required)."""

from __future__ import annotations

import struct
from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

from sensor_msgs.msg import PointCloud2, PointField
from std_msgs.msg import Header


Point = Tuple[float, float, float, float]  # x, y, z, intensity


def read_pcd_ascii(path: str | Path) -> List[Point]:
    """Read an ASCII PCD with fields x y z [intensity]."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f'PCD not found: {path}')

    points: List[Point] = []
    data_started = False
    with path.open('r', encoding='utf-8', errors='ignore') as handle:
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            if not data_started:
                if line.upper().startswith('DATA'):
                    data_started = True
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            x, y, z = float(parts[0]), float(parts[1]), float(parts[2])
            intensity = float(parts[3]) if len(parts) > 3 else 0.0
            points.append((x, y, z, intensity))
    return points


def points_to_cloud(
    points: Sequence[Point],
    header: Header,
) -> PointCloud2:
    """Pack xyz + intensity into sensor_msgs/PointCloud2."""
    fields = [
        PointField(name='x', offset=0, datatype=PointField.FLOAT32, count=1),
        PointField(name='y', offset=4, datatype=PointField.FLOAT32, count=1),
        PointField(name='z', offset=8, datatype=PointField.FLOAT32, count=1),
        PointField(name='intensity', offset=12, datatype=PointField.FLOAT32, count=1),
    ]
    point_step = 16
    buffer = bytearray()
    for x, y, z, intensity in points:
        buffer.extend(struct.pack('<ffff', x, y, z, intensity))

    msg = PointCloud2()
    msg.header = header
    msg.height = 1
    msg.width = len(points)
    msg.fields = fields
    msg.is_bigendian = False
    msg.point_step = point_step
    msg.row_step = point_step * len(points)
    msg.is_dense = True
    msg.data = bytes(buffer)
    return msg


def cloud_to_points(msg: PointCloud2) -> List[Point]:
    """Unpack PointCloud2 that contains at least x,y,z (optional intensity)."""
    field_map = {f.name: f for f in msg.fields}
    if not all(k in field_map for k in ('x', 'y', 'z')):
        raise ValueError('PointCloud2 must contain x, y, z fields')

    has_intensity = 'intensity' in field_map
    points: List[Point] = []
    data = memoryview(msg.data)

    for i in range(msg.width * msg.height):
        base = i * msg.point_step
        x = struct.unpack_from('<f', data, base + field_map['x'].offset)[0]
        y = struct.unpack_from('<f', data, base + field_map['y'].offset)[0]
        z = struct.unpack_from('<f', data, base + field_map['z'].offset)[0]
        intensity = 0.0
        if has_intensity:
            intensity = struct.unpack_from(
                '<f', data, base + field_map['intensity'].offset
            )[0]
        points.append((x, y, z, intensity))
    return points


def write_pcd_ascii(path: str | Path, points: Iterable[Point]) -> None:
    """Write points to an ASCII PCD file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pts = list(points)
    lines = [
        '# .PCD v0.7 - Point Cloud Data file format',
        'VERSION 0.7',
        'FIELDS x y z intensity',
        'SIZE 4 4 4 4',
        'TYPE F F F F',
        'COUNT 1 1 1 1',
        f'WIDTH {len(pts)}',
        'HEIGHT 1',
        'VIEWPOINT 0 0 0 1 0 0 0',
        f'POINTS {len(pts)}',
        'DATA ascii',
    ]
    with path.open('w', encoding='utf-8') as handle:
        handle.write('\n'.join(lines) + '\n')
        for x, y, z, intensity in pts:
            handle.write(f'{x:.4f} {y:.4f} {z:.4f} {intensity:.2f}\n')

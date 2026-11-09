"""ASCII PCD helpers for Map Studio (no ROS / sensor_msgs dependency)."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable, List, Sequence, Tuple

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


def voxel_downsample(
    points: Sequence[Point],
    voxel: float,
    max_points: int = 100_000,
) -> List[Point]:
    """Keep one point per voxel cell; then optionally stride to max_points."""
    if voxel <= 0:
        sampled = list(points)
    else:
        inv = 1.0 / voxel
        seen: set[Tuple[int, int, int]] = set()
        sampled: List[Point] = []
        for p in points:
            key = (int(p[0] * inv), int(p[1] * inv), int(p[2] * inv))
            if key in seen:
                continue
            seen.add(key)
            sampled.append(p)

    if len(sampled) > max_points:
        # Evenly span the whole voxel list so late objects are not dropped.
        n = len(sampled)
        sampled = [
            sampled[int(i * (n - 1) / (max_points - 1))]
            for i in range(max_points)
        ]
    return sampled


def points_to_flat(points: Iterable[Point]) -> List[float]:
    """Interleaved [x,y,z,intensity, ...] for the browser."""
    flat: List[float] = []
    for x, y, z, intensity in points:
        flat.extend((x, y, z, intensity))
    return flat


def bounds_of(points: Sequence[Point]) -> dict:
    if not points:
        return {
            'min': [0.0, 0.0, 0.0],
            'max': [0.0, 0.0, 0.0],
        }
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    zs = [p[2] for p in points]
    return {
        'min': [min(xs), min(ys), min(zs)],
        'max': [max(xs), max(ys), max(zs)],
    }

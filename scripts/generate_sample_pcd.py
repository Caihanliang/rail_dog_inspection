#!/usr/bin/env python3
"""Generate a synthetic rail-side corridor PCD for offline inspection demos.

Scene (coordinates in map / corridor frame, meters):
  - ground strip along x = 0..40, y = -5..5
  - equipment cabinet near P1 (10, 2)
  - equipment cabinet near P2 (25, 2.5)
  - trackside sign / pole near P3 (35, 0)
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path


def add_box(points, x0, x1, y0, y1, z0, z1, step, intensity, jitter=0.01):
    x = x0
    while x <= x1:
        y = y0
        while y <= y1:
            z = z0
            while z <= z1:
                points.append((
                    x + random.uniform(-jitter, jitter),
                    y + random.uniform(-jitter, jitter),
                    z + random.uniform(-jitter, jitter),
                    intensity + random.uniform(-5.0, 5.0),
                ))
                z += step
            y += step
        x += step


def add_ground(points, x0, x1, y0, y1, step=0.2, intensity=25.0):
    x = x0
    while x <= x1:
        y = y0
        while y <= y1:
            points.append((
                x,
                y,
                random.uniform(-0.01, 0.01),
                intensity + random.uniform(-5.0, 5.0),
            ))
            y += step
        x += step


def add_pole(points, cx, cy, height=3.0, radius=0.08, step=0.08, intensity=60.0):
    z = 0.0
    while z <= height:
        for ang in range(0, 360, 45):
            rad = math.radians(ang)
            points.append((
                cx + radius * math.cos(rad),
                cy + radius * math.sin(rad),
                z,
                intensity,
            ))
        z += step
    # sign plate
    add_box(
        points,
        cx - 0.4, cx + 0.4,
        cy - 0.05, cy + 0.05,
        height - 0.6, height,
        0.05,
        intensity + 10.0,
    )


def write_pcd(path: Path, points):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        '# .PCD v0.7 - Point Cloud Data file format',
        '# sample rail-side scene for dog inspection demo',
        '# frame: map (corridor); units: meters',
        '# cabinets ~ (10,2) and (25,2.5); sign/pole ~ (35,0)',
        'VERSION 0.7',
        'FIELDS x y z intensity',
        'SIZE 4 4 4 4',
        'TYPE F F F F',
        'COUNT 1 1 1 1',
        f'WIDTH {len(points)}',
        'HEIGHT 1',
        'VIEWPOINT 0 0 0 1 0 0 0',
        f'POINTS {len(points)}',
        'DATA ascii',
    ]
    with path.open('w', encoding='utf-8') as handle:
        handle.write('\n'.join(header) + '\n')
        for x, y, z, intensity in points:
            handle.write(f'{x:.4f} {y:.4f} {z:.4f} {intensity:.2f}\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-o', '--output',
        default=str(
            Path(__file__).resolve().parents[1] / 'data' / 'raw' / 'sample_rail_scene.pcd'
        ),
    )
    parser.add_argument('--seed', type=int, default=42)
    args = parser.parse_args()
    random.seed(args.seed)

    points = []
    add_ground(points, 0.0, 40.0, -5.0, 5.0, step=0.25)
    # P1 cabinet
    add_box(points, 9.2, 10.8, 1.4, 2.6, 0.2, 1.6, 0.08, 80.0)
    # P2 cabinet
    add_box(points, 24.2, 25.8, 1.9, 3.1, 0.2, 1.8, 0.08, 85.0)
    # P3 sign/pole
    add_pole(points, 35.0, 0.0, height=3.0)

    out = Path(args.output)
    write_pcd(out, points)
    print(f'Wrote {len(points)} points -> {out}')


if __name__ == '__main__':
    main()

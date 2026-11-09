#!/usr/bin/env python3
"""Synthesize a yard-side PCD inspired by a real inspection photo.

Layout approximates the photo (map / corridor frame, meters):
  - cracked concrete platform (inspection walkway)
  - ballast + dual rails
  - freight boxcars in the background
  - red wayside sign
  - simplified wheeled quadruped silhouette on the platform

This is NOT a depth reconstruction from the RGB image — it is a
hand-authored synthetic scene for offline Map Studio / inspection demos.
"""

from __future__ import annotations

import argparse
import math
import random
from pathlib import Path


def add_box(points, x0, x1, y0, y1, z0, z1, step, intensity, jitter=0.015):
    x = x0
    while x <= x1 + 1e-9:
        y = y0
        while y <= y1 + 1e-9:
            z = z0
            while z <= z1 + 1e-9:
                points.append((
                    x + random.uniform(-jitter, jitter),
                    y + random.uniform(-jitter, jitter),
                    z + random.uniform(-jitter, jitter),
                    intensity + random.uniform(-6.0, 6.0),
                ))
                z += step
            y += step
        x += step


def add_platform(points, x0, x1, y0, y1, step=0.12):
    """Concrete deck with mild crack-like height noise."""
    x = x0
    while x <= x1 + 1e-9:
        y = y0
        while y <= y1 + 1e-9:
            crack = 0.0
            if abs(math.sin(x * 1.7) * math.cos(y * 2.3)) > 0.85:
                crack = -0.02
            z = 0.05 + crack + random.uniform(-0.008, 0.008)
            points.append((
                x,
                y,
                z,
                32.0 + random.uniform(-8.0, 8.0),
            ))
            y += step
        x += step


def add_ballast(points, x0, x1, y0, y1, step=0.1):
    x = x0
    while x <= x1 + 1e-9:
        y = y0
        while y <= y1 + 1e-9:
            z = -0.05 + random.uniform(0.0, 0.12)
            points.append((
                x + random.uniform(-0.03, 0.03),
                y + random.uniform(-0.03, 0.03),
                z,
                55.0 + random.uniform(-10.0, 10.0),
            ))
            y += step
        x += step


def add_rail(points, x0, x1, y_center, step=0.08):
    """Simple rail head + web strip."""
    add_box(
        points,
        x0, x1,
        y_center - 0.04, y_center + 0.04,
        0.08, 0.18,
        step,
        95.0,
        jitter=0.005,
    )
    add_box(
        points,
        x0, x1,
        y_center - 0.015, y_center + 0.015,
        0.0, 0.08,
        step,
        90.0,
        jitter=0.004,
    )


def add_corrugated_car(points, x0, x1, y0, y1, z0, z1, step=0.12):
    """Freight boxcar shell with vertical corrugation along x."""
    # floor / underframe
    add_box(points, x0, x1, y0, y1, z0, z0 + 0.25, step, 40.0)
    # roof
    add_box(points, x0, x1, y0, y1, z1 - 0.15, z1, step, 35.0)
    # side walls with ridges
    x = x0
    while x <= x1 + 1e-9:
        ridge = 0.04 if int(x * 5) % 2 == 0 else 0.0
        add_box(
            points,
            x, min(x + step, x1),
            y0 - ridge, y0 + 0.05,
            z0 + 0.25, z1 - 0.15,
            step,
            28.0 + random.uniform(-4, 4),
            jitter=0.01,
        )
        add_box(
            points,
            x, min(x + step, x1),
            y1 - 0.05, y1 + ridge,
            z0 + 0.25, z1 - 0.15,
            step,
            28.0 + random.uniform(-4, 4),
            jitter=0.01,
        )
        x += step
    # end walls
    add_box(points, x0, x0 + 0.08, y0, y1, z0 + 0.25, z1 - 0.15, step, 30.0)
    add_box(points, x1 - 0.08, x1, y0, y1, z0 + 0.25, z1 - 0.15, step, 30.0)


def add_red_sign(points, cx, cy):
    # post
    add_box(
        points,
        cx - 0.03, cx + 0.03,
        cy - 0.03, cy + 0.03,
        0.05, 1.1,
        0.05,
        70.0,
    )
    # red plate (high intensity proxy)
    add_box(
        points,
        cx - 0.25, cx + 0.25,
        cy - 0.02, cy + 0.02,
        0.85, 1.35,
        0.04,
        120.0,
    )


def add_dog_silhouette(points, cx, cy, yaw=0.4):
    """Very coarse wheeled-quadruped blob for scale reference."""
    c, s = math.cos(yaw), math.sin(yaw)

    def local(lx, ly, lz, intensity):
        x = cx + c * lx - s * ly
        y = cy + s * lx + c * ly
        points.append((
            x + random.uniform(-0.01, 0.01),
            y + random.uniform(-0.01, 0.01),
            lz + random.uniform(-0.01, 0.01),
            intensity,
        ))

    # body
    for lx in frange(-0.45, 0.55, 0.08):
        for ly in frange(-0.18, 0.18, 0.08):
            for lz in frange(0.35, 0.7, 0.08):
                local(lx, ly, lz, 15.0)
    # head / sensor
    for lx in frange(0.55, 0.85, 0.06):
        for ly in frange(-0.12, 0.12, 0.06):
            for lz in frange(0.4, 0.65, 0.06):
                local(lx, ly, lz, 20.0)
    # legs + wheels
    for lx, ly in [(-0.35, -0.2), (-0.35, 0.2), (0.35, -0.2), (0.35, 0.2)]:
        for lz in frange(0.05, 0.4, 0.06):
            local(lx, ly, lz, 18.0)
        for ang in range(0, 360, 40):
            rad = math.radians(ang)
            local(lx + 0.08 * math.cos(rad), ly, 0.1 + 0.08 * math.sin(rad), 25.0)


def frange(a, b, step):
    x = a
    while x <= b + 1e-9:
        yield x
        x += step


def write_pcd(path: Path, points):
    path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        '# .PCD v0.7 - Point Cloud Data file format',
        '# Synthetic yard scene inspired by inspection photo (not depth-from-RGB)',
        '# frame: map; +x along track, +y toward platform, +z up',
        '# platform y~0..4; rails y~-1.9/-0.5; freight y~-5.2..-2.6; dog ~(8,2.2)',
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
        '-o',
        '--output',
        default=str(
            Path(__file__).resolve().parents[1]
            / 'data'
            / 'raw'
            / 'yard_photo_scene.pcd'
        ),
    )
    parser.add_argument('--seed', type=int, default=7)
    args = parser.parse_args()
    random.seed(args.seed)

    points = []

    # Concrete platform (walkway where the dog stands)
    add_platform(points, 0.0, 36.0, 0.2, 4.2, step=0.14)

    # Ballast bed + rails (gauge ~1.435 m)
    add_ballast(points, 0.0, 36.0, -2.4, 0.15, step=0.12)
    add_rail(points, 0.0, 36.0, -0.55)
    add_rail(points, 0.0, 36.0, -1.985)

    # Freight cars behind the track
    car_specs = [
        (0.5, 7.5),
        (8.0, 15.0),
        (15.5, 22.5),
        (23.0, 30.0),
        (30.5, 35.5),
    ]
    for x0, x1 in car_specs:
        add_corrugated_car(
            points,
            x0, x1,
            -5.15, -2.65,
            0.35, 4.1,
            step=0.14,
        )

    # Red wayside sign near platform edge
    add_red_sign(points, 11.5, 0.55)

    # Robot dog silhouette on platform (photo pose reference)
    add_dog_silhouette(points, 8.0, 2.2, yaw=0.55)

    # A few inspection landmarks along the platform edge
    add_box(points, 5.6, 6.4, 3.3, 3.9, 0.1, 1.2, 0.08, 75.0)   # P1-ish cabinet
    add_box(points, 18.5, 19.4, 3.2, 3.95, 0.1, 1.4, 0.08, 78.0)  # P2-ish
    add_box(points, 28.0, 28.2, 1.6, 1.8, 0.1, 2.8, 0.06, 85.0)   # P3-ish pole
    add_box(points, 27.6, 28.6, 1.55, 1.65, 2.3, 2.9, 0.05, 95.0)

    out = Path(args.output)
    write_pcd(out, points)
    print(f'Wrote {len(points)} points -> {out}')


if __name__ == '__main__':
    main()

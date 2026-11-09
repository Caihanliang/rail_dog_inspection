"""Map Studio: offline PCD viewer + mission point editor."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pcd_io import bounds_of, points_to_flat, read_pcd_ascii, voxel_downsample

HERE = Path(__file__).resolve().parent
WS_ROOT = HERE.parents[1]
RAW_DIR = WS_ROOT / 'data' / 'raw'
MAPS_DIR = WS_ROOT / 'data' / 'maps'
MISSION_PATH = (
    WS_ROOT / 'src' / 'dog_inspection' / 'config' / 'mission_points.yaml'
)
STATIC_DIR = HERE / 'static'

app = FastAPI(title='Rail Dog Map Studio', version='0.1.0')


class MissionPoint(BaseModel):
    id: str
    xyz: List[float] = Field(..., min_length=3, max_length=3)
    yaw: float = 0.0
    actions: List[str] = Field(default_factory=lambda: ['save_cloud'])
    roi: Optional[Dict[str, Any]] = None


class MissionPayload(BaseModel):
    name: str = 'yard_line_a'
    points: List[MissionPoint] = Field(default_factory=list)


class RegisterMapRequest(BaseModel):
    name: str
    cloud: str
    note: str = ''


def _safe_cloud_name(name: str) -> str:
    base = Path(name).name
    if base != name or '..' in name or '/' in name or '\\' in name:
        raise HTTPException(status_code=400, detail='Invalid cloud name')
    if not base.lower().endswith('.pcd'):
        raise HTTPException(status_code=400, detail='Only .pcd files allowed')
    return base


def _cloud_path(name: str) -> Path:
    safe = _safe_cloud_name(name)
    path = (RAW_DIR / safe).resolve()
    if not str(path).startswith(str(RAW_DIR.resolve())):
        raise HTTPException(status_code=400, detail='Path escape blocked')
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f'Cloud not found: {safe}')
    return path


def _load_mission_dict() -> Dict[str, Any]:
    if not MISSION_PATH.is_file():
        return {'name': 'default_mission', 'points': []}
    with MISSION_PATH.open('r', encoding='utf-8') as handle:
        data = yaml.safe_load(handle) or {}
    return data.get('mission', data)


def _mission_to_yaml(payload: MissionPayload) -> str:
    points: List[Dict[str, Any]] = []
    for p in payload.points:
        item: Dict[str, Any] = {
            'id': p.id,
            'xyz': [float(p.xyz[0]), float(p.xyz[1]), float(p.xyz[2])],
            'yaw': float(p.yaw),
            'actions': list(p.actions) or ['save_cloud'],
        }
        if p.roi:
            item['roi'] = p.roi
        points.append(item)
    doc = {
        'mission': {
            'name': payload.name,
            'points': points,
        }
    }
    return yaml.safe_dump(doc, allow_unicode=True, sort_keys=False)


@app.get('/api/health')
def health():
    return {
        'ok': True,
        'ws_root': str(WS_ROOT),
        'raw_dir': str(RAW_DIR),
        'mission_path': str(MISSION_PATH),
    }


@app.get('/api/clouds')
def list_clouds():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    clouds = []
    for path in sorted(RAW_DIR.glob('*.pcd')):
        clouds.append(
            {
                'name': path.name,
                'size_bytes': path.stat().st_size,
            }
        )
    return {'clouds': clouds}


@app.get('/api/clouds/{name}/points')
def cloud_points(
    name: str,
    voxel: float = Query(0.1, ge=0.0, le=5.0),
    max_points: int = Query(80_000, ge=1_000, le=200_000),
):
    path = _cloud_path(name)
    try:
        points = read_pcd_ascii(path)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    sampled = voxel_downsample(points, voxel=voxel, max_points=max_points)
    return {
        'name': path.name,
        'source_points': len(points),
        'returned_points': len(sampled),
        'voxel': voxel,
        'bounds': bounds_of(sampled),
        'points': points_to_flat(sampled),
    }


@app.get('/api/mission')
def get_mission():
    mission = _load_mission_dict()
    return {
        'path': str(MISSION_PATH),
        'mission': {
            'name': mission.get('name', 'default_mission'),
            'points': mission.get('points', []),
        },
    }


@app.put('/api/mission')
def put_mission(payload: MissionPayload):
    MISSION_PATH.parent.mkdir(parents=True, exist_ok=True)
    if MISSION_PATH.is_file():
        bak = MISSION_PATH.with_suffix(
            MISSION_PATH.suffix + f'.bak_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        )
        shutil.copy2(MISSION_PATH, bak)
    text = _mission_to_yaml(payload)
    MISSION_PATH.write_text(text, encoding='utf-8')
    return {
        'ok': True,
        'path': str(MISSION_PATH),
        'point_count': len(payload.points),
    }


@app.get('/api/mission/export')
def export_mission_from_disk():
    mission = _load_mission_dict()
    payload = MissionPayload(
        name=str(mission.get('name', 'default_mission')),
        points=[MissionPoint.model_validate(p) for p in mission.get('points', [])],
    )
    return {
        'filename': 'mission_points.yaml',
        'yaml': _mission_to_yaml(payload),
    }


@app.post('/api/mission/yaml')
def mission_yaml(payload: MissionPayload):
    """Render YAML for download without writing to disk."""
    return {
        'filename': 'mission_points.yaml',
        'yaml': _mission_to_yaml(payload),
    }


@app.get('/api/maps')
def list_maps():
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    maps = []
    for meta in sorted(MAPS_DIR.glob('*/map.json')):
        try:
            import json

            data = json.loads(meta.read_text(encoding='utf-8'))
        except Exception:  # noqa: BLE001
            data = {'name': meta.parent.name}
        maps.append(data)
    return {'maps': maps}


@app.post('/api/maps')
def register_map(req: RegisterMapRequest):
    import json
    import re

    name = req.name.strip()
    if not name or not re.fullmatch(r'[A-Za-z0-9_\-]+', name):
        raise HTTPException(
            status_code=400,
            detail='Map name must be alphanumeric / _ / -',
        )
    cloud_path = _cloud_path(req.cloud)
    dest_dir = MAPS_DIR / name
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_pcd = dest_dir / cloud_path.name
    if not dest_pcd.exists() or dest_pcd.resolve() != cloud_path.resolve():
        shutil.copy2(cloud_path, dest_pcd)

    meta = {
        'name': name,
        'cloud': cloud_path.name,
        'cloud_path': str(dest_pcd.relative_to(WS_ROOT)),
        'source_raw': str(cloud_path.relative_to(WS_ROOT)),
        'note': req.note,
        'registered_at': datetime.now().isoformat(timespec='seconds'),
    }
    meta_path = dest_dir / 'map.json'
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    return {'ok': True, 'map': meta}


@app.get('/')
def index():
    index_path = STATIC_DIR / 'index.html'
    if not index_path.is_file():
        raise HTTPException(status_code=404, detail='static/index.html missing')
    return FileResponse(index_path)


app.mount('/static', StaticFiles(directory=str(STATIC_DIR)), name='static')


def main():
    import uvicorn

    uvicorn.run(
        'app:app',
        host='127.0.0.1',
        port=8765,
        reload=False,
        app_dir=str(HERE),
    )


if __name__ == '__main__':
    main()

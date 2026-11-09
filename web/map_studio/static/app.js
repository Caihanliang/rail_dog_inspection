import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const els = {
  cloudSelect: document.getElementById('cloud-select'),
  voxel: document.getElementById('voxel'),
  btnLoad: document.getElementById('btn-load'),
  btnRefresh: document.getElementById('btn-refresh-clouds'),
  btnView2d: document.getElementById('btn-view-2d'),
  btnView3d: document.getElementById('btn-view-3d'),
  markMode: document.getElementById('mark-mode'),
  missionName: document.getElementById('mission-name'),
  btnLoadMission: document.getElementById('btn-load-mission'),
  btnClear: document.getElementById('btn-clear-points'),
  pointsList: document.getElementById('points-list'),
  btnSave: document.getElementById('btn-save-mission'),
  btnExport: document.getElementById('btn-export'),
  mapName: document.getElementById('map-name'),
  mapNote: document.getElementById('map-note'),
  btnRegister: document.getElementById('btn-register-map'),
  status: document.getElementById('status'),
  hudCloud: document.getElementById('hud-cloud'),
  hudView: document.getElementById('hud-view'),
  hudHelp: document.getElementById('hud-help'),
  host: document.getElementById('canvas-host'),
};

/** @type {{id:string, xyz:number[], yaw:number, actions:string[], roi?:object}[]} */
let points = [];
let currentCloud = null;
let pointCloudObj = null;
let markersGroup = null;
/** @type {'2d'|'3d'} */
let viewMode = '2d';
/** @type {{min:number[], max:number[]}|null} */
let cloudBounds = null;
let pointerDown = null;

const raycaster = new THREE.Raycaster();
const pointer = new THREE.Vector2();
const groundPlane = new THREE.Plane(new THREE.Vector3(0, 0, 1), 0);
const hit = new THREE.Vector3();

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x080c0f);

const perspectiveCam = new THREE.PerspectiveCamera(55, 1, 0.1, 500);
perspectiveCam.up.set(0, 0, 1);
perspectiveCam.position.set(20, -28, 22);

const orthoCam = new THREE.OrthographicCamera(-20, 20, 20, -20, 0.1, 500);
orthoCam.up.set(0, 1, 0);
orthoCam.position.set(20, 0, 60);
orthoCam.lookAt(20, 0, 0);

/** @type {THREE.Camera} */
let activeCamera = orthoCam;

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
els.host.appendChild(renderer.domElement);
renderer.domElement.style.touchAction = 'none';
renderer.domElement.addEventListener(
  'wheel',
  (event) => {
    event.preventDefault();
  },
  { passive: false },
);

const controls = new OrbitControls(activeCamera, renderer.domElement);
controls.enableDamping = true;
controls.target.set(20, 0, 0);

scene.add(new THREE.AmbientLight(0xffffff, 0.7));
const key = new THREE.DirectionalLight(0xfff2d0, 0.75);
key.position.set(20, -10, 40);
scene.add(key);

const grid = new THREE.GridHelper(80, 40, 0x3a4a55, 0x1c2830);
grid.rotation.x = Math.PI / 2;
scene.add(grid);

const axes = new THREE.AxesHelper(3);
scene.add(axes);

markersGroup = new THREE.Group();
scene.add(markersGroup);

function setStatus(msg, kind = '') {
  els.status.textContent = msg;
  els.status.className = `status${kind ? ` ${kind}` : ''}`;
}

function formatDetail(detail) {
  if (!detail) return 'request failed';
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => (typeof d === 'string' ? d : d.msg || JSON.stringify(d)))
      .join('; ');
  }
  return JSON.stringify(detail);
}

async function api(path, options) {
  const res = await fetch(path, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(formatDetail(data.detail) || res.statusText || 'request failed');
  }
  return data;
}

function updateHudHelp() {
  if (viewMode === '2d') {
    els.hudHelp.textContent = els.markMode.checked
      ? '2D：拖拽平移 · 滚轮缩放 · 短按左键落点（俯视不倾斜旋转）'
      : '2D：拖拽平移 · 滚轮缩放（俯视不倾斜旋转）';
    els.hudView.textContent = '2D';
  } else {
    els.hudHelp.textContent = els.markMode.checked
      ? '3D：拖拽旋转 · 右键平移 · 滚轮缩放 · 短按左键落点'
      : '3D：拖拽旋转 · 右键平移 · 滚轮缩放';
    els.hudView.textContent = '3D';
  }
}

function syncControlButtons() {
  // Drag always navigates; short left-click (no drag) places a point when mark mode is on.
  if (viewMode === '2d') {
    controls.enableRotate = false;
    controls.enablePan = true;
    controls.screenSpacePanning = true;
    controls.mouseButtons.LEFT = THREE.MOUSE.PAN;
    controls.mouseButtons.MIDDLE = THREE.MOUSE.DOLLY;
    controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
  } else {
    controls.enableRotate = true;
    controls.enablePan = true;
    controls.screenSpacePanning = false;
    controls.mouseButtons.LEFT = THREE.MOUSE.ROTATE;
    controls.mouseButtons.MIDDLE = THREE.MOUSE.DOLLY;
    controls.mouseButtons.RIGHT = THREE.MOUSE.PAN;
  }
  updateHudHelp();
}

function fitOrthoToBounds(bounds) {
  const w = Math.max(els.host.clientWidth, 1);
  const h = Math.max(els.host.clientHeight, 1);
  const aspect = w / h;
  const [xmin, ymin] = bounds.min;
  const [xmax, ymax] = bounds.max;
  const cx = (xmin + xmax) / 2;
  const cy = (ymin + ymax) / 2;
  const spanX = Math.max(xmax - xmin, 1) * 1.2;
  const spanY = Math.max(ymax - ymin, 1) * 1.2;
  const halfH = Math.max(spanY / 2, spanX / 2 / aspect);

  orthoCam.left = -halfH * aspect;
  orthoCam.right = halfH * aspect;
  orthoCam.top = halfH;
  orthoCam.bottom = -halfH;
  orthoCam.position.set(cx, cy, 80);
  orthoCam.up.set(0, 1, 0);
  orthoCam.lookAt(cx, cy, 0);
  orthoCam.updateProjectionMatrix();
  controls.target.set(cx, cy, 0);
}

function frameActiveView() {
  if (!cloudBounds) return;
  const [xmin, ymin, zmin] = cloudBounds.min;
  const [xmax, ymax, zmax] = cloudBounds.max;
  const cx = (xmin + xmax) / 2;
  const cy = (ymin + ymax) / 2;
  const cz = (zmin + zmax) / 2;

  if (viewMode === '2d') {
    fitOrthoToBounds(cloudBounds);
  } else {
    perspectiveCam.up.set(0, 0, 1);
    perspectiveCam.position.set(cx + 8, cy - 22, cz + 18);
    controls.target.set(cx, cy, cz);
  }
  controls.update();
}

function setViewMode(mode) {
  viewMode = mode;
  els.btnView2d.classList.toggle('active', mode === '2d');
  els.btnView3d.classList.toggle('active', mode === '3d');

  if (mode === '2d') {
    scene.fog = null;
    activeCamera = orthoCam;
    if (pointCloudObj?.material) {
      pointCloudObj.material.size = 0.12;
      pointCloudObj.material.sizeAttenuation = false;
    }
  } else {
    scene.fog = new THREE.Fog(0x080c0f, 80, 160);
    activeCamera = perspectiveCam;
    if (pointCloudObj?.material) {
      pointCloudObj.material.size = 0.08;
      pointCloudObj.material.sizeAttenuation = true;
    }
  }

  controls.object = activeCamera;
  frameActiveView();
  syncControlButtons();
  rebuildMarkers();
  resize();
}

async function refreshClouds() {
  const data = await api('/api/clouds');
  els.cloudSelect.innerHTML = '';
  for (const c of data.clouds) {
    const opt = document.createElement('option');
    opt.value = c.name;
    opt.textContent = `${c.name} (${(c.size_bytes / 1024).toFixed(1)} KB)`;
    els.cloudSelect.appendChild(opt);
  }
  if (!data.clouds.length) {
    setStatus('data/raw 下没有 .pcd', 'err');
  }
}

function nextPointId() {
  let n = points.length + 1;
  const used = new Set(points.map((p) => p.id));
  while (used.has(`P${n}`)) n += 1;
  return `P${n}`;
}

function makeMarkerLabel(text) {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = 'rgba(14, 20, 24, 0.85)';
  ctx.strokeStyle = '#d4a017';
  ctx.lineWidth = 4;
  ctx.beginPath();
  ctx.roundRect(8, 8, 112, 48, 8);
  ctx.fill();
  ctx.stroke();
  ctx.fillStyle = '#ffe08a';
  ctx.font = 'bold 28px IBM Plex Sans, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text, 64, 34);
  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: false });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(viewMode === '2d' ? 1.8 : 1.4, viewMode === '2d' ? 0.9 : 0.7, 1);
  return sprite;
}

function rebuildMarkers() {
  while (markersGroup.children.length) {
    const child = markersGroup.children[0];
    markersGroup.remove(child);
    child.traverse?.((obj) => {
      obj.geometry?.dispose?.();
      if (obj.material) {
        if (obj.material.map) obj.material.map.dispose();
        obj.material.dispose();
      }
    });
  }

  for (const p of points) {
    const group = new THREE.Group();
    group.position.set(p.xyz[0], p.xyz[1], p.xyz[2]);

    if (viewMode === '2d') {
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(0.35, 0.55, 28),
        new THREE.MeshBasicMaterial({
          color: 0xd4a017,
          side: THREE.DoubleSide,
          depthTest: false,
        }),
      );
      ring.position.z = 0.05;
      group.add(ring);

      const disc = new THREE.Mesh(
        new THREE.CircleGeometry(0.28, 24),
        new THREE.MeshBasicMaterial({
          color: 0xffe08a,
          side: THREE.DoubleSide,
          depthTest: false,
        }),
      );
      disc.position.z = 0.06;
      group.add(disc);

      const yaw = Number(p.yaw) || 0;
      const dir = new THREE.ArrowHelper(
        new THREE.Vector3(Math.cos(yaw), Math.sin(yaw), 0).normalize(),
        new THREE.Vector3(0, 0, 0.08),
        1.6,
        0x6ec8ff,
        0.35,
        0.22,
      );
      group.add(dir);

      const label = makeMarkerLabel(p.id);
      label.position.set(0, 0.95, 0.2);
      group.add(label);
    } else {
      const stem = new THREE.Mesh(
        new THREE.CylinderGeometry(0.08, 0.12, 1.2, 10),
        new THREE.MeshStandardMaterial({
          color: 0xd4a017,
          metalness: 0.2,
          roughness: 0.55,
        }),
      );
      stem.rotation.x = Math.PI / 2;
      stem.position.z = 0.6;
      group.add(stem);

      const head = new THREE.Mesh(
        new THREE.SphereGeometry(0.22, 14, 12),
        new THREE.MeshStandardMaterial({
          color: 0xffe08a,
          emissive: 0x664400,
          emissiveIntensity: 0.35,
        }),
      );
      head.position.z = 1.25;
      group.add(head);

      const yaw = Number(p.yaw) || 0;
      const dir = new THREE.ArrowHelper(
        new THREE.Vector3(Math.cos(yaw), Math.sin(yaw), 0).normalize(),
        new THREE.Vector3(0, 0, 0.2),
        1.4,
        0x6ec8ff,
        0.28,
        0.18,
      );
      group.add(dir);

      const label = makeMarkerLabel(p.id);
      label.position.set(0, 0, 1.7);
      group.add(label);
    }

    markersGroup.add(group);
  }
  renderPointsList();
}

function renderPointsList() {
  els.pointsList.innerHTML = '';
  points.forEach((p, idx) => {
    const card = document.createElement('div');
    card.className = 'point-card';
    card.innerHTML = `
      <header>
        <span>${p.id}</span>
        <button type="button" data-del="${idx}" class="danger">删除</button>
      </header>
      <div class="coords">
        x=${p.xyz[0].toFixed(2)} y=${p.xyz[1].toFixed(2)} z=${p.xyz[2].toFixed(2)}
      </div>
      <div class="yaw-row">
        <span>yaw (rad)</span>
        <input type="number" step="0.01" value="${Number(p.yaw).toFixed(2)}" data-yaw="${idx}" />
      </div>
    `;
    els.pointsList.appendChild(card);
  });

  els.pointsList.querySelectorAll('[data-del]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const i = Number(btn.getAttribute('data-del'));
      points.splice(i, 1);
      rebuildMarkers();
    });
  });
  els.pointsList.querySelectorAll('[data-yaw]').forEach((input) => {
    input.addEventListener('change', () => {
      const i = Number(input.getAttribute('data-yaw'));
      points[i].yaw = Number(input.value) || 0;
      rebuildMarkers();
    });
  });
}

function disposePointCloud() {
  if (!pointCloudObj) return;
  scene.remove(pointCloudObj);
  pointCloudObj.geometry.dispose();
  pointCloudObj.material.dispose();
  pointCloudObj = null;
}

async function loadCloud() {
  const name = els.cloudSelect.value;
  if (!name) {
    setStatus('请先选择点云', 'err');
    return;
  }
  const voxel = Number(els.voxel.value) || 0.15;
  setStatus(`加载 ${name} …`);
  els.btnLoad.disabled = true;
  try {
    const data = await api(
      `/api/clouds/${encodeURIComponent(name)}/points?voxel=${voxel}&max_points=80000`,
    );
    disposePointCloud();

    const n = data.returned_points;
    const positions = new Float32Array(n * 3);
    const colors = new Float32Array(n * 3);
    const flat = data.points;
    let iMin = Infinity;
    let iMax = -Infinity;
    for (let i = 0; i < n; i += 1) {
      const intensity = flat[i * 4 + 3];
      if (intensity < iMin) iMin = intensity;
      if (intensity > iMax) iMax = intensity;
    }
    const span = Math.max(1e-6, iMax - iMin);
    for (let i = 0; i < n; i += 1) {
      const x = flat[i * 4];
      const y = flat[i * 4 + 1];
      const z = flat[i * 4 + 2];
      const t = (flat[i * 4 + 3] - iMin) / span;
      positions[i * 3] = x;
      positions[i * 3 + 1] = y;
      positions[i * 3 + 2] = z;
      colors[i * 3] = 0.35 + 0.55 * t;
      colors[i * 3 + 1] = 0.42 + 0.35 * t;
      colors[i * 3 + 2] = 0.48 + 0.15 * (1 - t);
    }

    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geometry.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const material = new THREE.PointsMaterial({
      size: viewMode === '2d' ? 0.12 : 0.08,
      vertexColors: true,
      sizeAttenuation: viewMode !== '2d',
    });
    pointCloudObj = new THREE.Points(geometry, material);
    scene.add(pointCloudObj);

    cloudBounds = data.bounds;
    frameActiveView();

    currentCloud = name;
    els.hudCloud.textContent = `${name} · ${n.toLocaleString()} pts`;
    if (!els.mapName.value) {
      els.mapName.value = name.replace(/\.pcd$/i, '');
    }
    setStatus(
      `已加载 ${name}（源 ${data.source_points} → 显示 ${n}，voxel=${voxel}）`,
      'ok',
    );
  } catch (err) {
    setStatus(String(err.message || err), 'err');
  } finally {
    els.btnLoad.disabled = false;
  }
}

async function loadMission() {
  try {
    const data = await api('/api/mission');
    els.missionName.value = data.mission.name || 'yard_line_a';
    points = (data.mission.points || []).map((p) => ({
      id: p.id,
      xyz: [...p.xyz],
      yaw: Number(p.yaw) || 0,
      actions: p.actions || ['save_cloud'],
      ...(p.roi ? { roi: p.roi } : {}),
    }));
    rebuildMarkers();
    setStatus(`已载入任务 ${data.mission.name}（${points.length} 点）`, 'ok');
  } catch (err) {
    setStatus(String(err.message || err), 'err');
  }
}

function missionPayload() {
  return {
    name: els.missionName.value.trim() || 'yard_line_a',
    points: points.map((p) => {
      const item = {
        id: p.id,
        xyz: [Number(p.xyz[0]), Number(p.xyz[1]), Number(p.xyz[2])],
        yaw: Number(p.yaw) || 0,
        actions: p.actions?.length ? p.actions : ['save_cloud'],
      };
      if (p.roi) item.roi = p.roi;
      return item;
    }),
  };
}

async function saveMission() {
  try {
    const body = missionPayload();
    const data = await api('/api/mission', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    setStatus(`已写回 ${data.path}（${data.point_count} 点，已备份 .bak）`, 'ok');
  } catch (err) {
    setStatus(String(err.message || err), 'err');
  }
}

async function exportMission() {
  try {
    const local = missionPayload();
    const data = await api('/api/mission/yaml', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(local),
    });
    const blob = new Blob([data.yaml], { type: 'text/yaml;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = data.filename || 'mission_points.yaml';
    a.click();
    URL.revokeObjectURL(url);
    setStatus(`已下载 ${data.filename}（${local.points.length} 点，未写盘）`, 'ok');
  } catch (err) {
    setStatus(String(err.message || err), 'err');
  }
}

async function registerMap() {
  if (!currentCloud) {
    setStatus('请先加载点云再登记', 'err');
    return;
  }
  const name = els.mapName.value.trim();
  if (!name) {
    setStatus('请填写地图名', 'err');
    return;
  }
  try {
    const data = await api('/api/maps', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name,
        cloud: currentCloud,
        note: els.mapNote.value.trim(),
      }),
    });
    setStatus(`已登记地图 ${data.map.name} → ${data.map.cloud_path}`, 'ok');
  } catch (err) {
    setStatus(String(err.message || err), 'err');
  }
}

function placePointAtClient(clientX, clientY) {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, activeCamera);
  if (!raycaster.ray.intersectPlane(groundPlane, hit)) return false;

  points.push({
    id: nextPointId(),
    xyz: [Number(hit.x.toFixed(3)), Number(hit.y.toFixed(3)), 0.0],
    yaw: 0.0,
    actions: ['save_cloud'],
  });
  rebuildMarkers();
  setStatus(
    `已添加 ${points[points.length - 1].id} @ (${hit.x.toFixed(2)}, ${hit.y.toFixed(2)})`,
  );
  return true;
}

function onPointerDown(event) {
  if (event.button !== 0) return;
  pointerDown = { x: event.clientX, y: event.clientY, mark: els.markMode.checked };
}

function onPointerUp(event) {
  if (!pointerDown || event.button !== 0) return;
  const dx = event.clientX - pointerDown.x;
  const dy = event.clientY - pointerDown.y;
  // Slightly larger threshold so tiny jitters while clicking still count as mark,
  // while real drags navigate the view.
  const moved = Math.hypot(dx, dy) > 8;
  const wantMark = pointerDown.mark;
  pointerDown = null;
  if (!wantMark || moved) return;
  placePointAtClient(event.clientX, event.clientY);
}

function resize() {
  const w = els.host.clientWidth;
  const h = els.host.clientHeight;
  if (w < 1 || h < 1) return;

  const aspect = w / h;
  perspectiveCam.aspect = aspect;
  perspectiveCam.updateProjectionMatrix();

  if (viewMode === '2d' && cloudBounds) {
    // Keep current center; only refresh aspect via frustum height.
    const halfH = (orthoCam.top - orthoCam.bottom) / 2;
    const cx = (orthoCam.left + orthoCam.right) / 2;
    const cy = (orthoCam.top + orthoCam.bottom) / 2;
    // Prefer re-fit if we have bounds and frustum was never set for this aspect
    void cx;
    void cy;
    const centerX = controls.target.x;
    const centerY = controls.target.y;
    orthoCam.left = -halfH * aspect;
    orthoCam.right = halfH * aspect;
    orthoCam.top = halfH;
    orthoCam.bottom = -halfH;
    // Keep looking at same target; position stays above target
    orthoCam.position.x = centerX;
    orthoCam.position.y = centerY;
    orthoCam.updateProjectionMatrix();
  } else if (viewMode === '2d') {
    const halfH = 20;
    orthoCam.left = -halfH * aspect;
    orthoCam.right = halfH * aspect;
    orthoCam.top = halfH;
    orthoCam.bottom = -halfH;
    orthoCam.updateProjectionMatrix();
  }

  renderer.setSize(w, h, true);
}

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, activeCamera);
}

els.btnRefresh.addEventListener('click', () => {
  refreshClouds().catch((e) => setStatus(String(e.message || e), 'err'));
});
els.btnLoad.addEventListener('click', () => {
  loadCloud();
});
els.btnView2d.addEventListener('click', () => setViewMode('2d'));
els.btnView3d.addEventListener('click', () => setViewMode('3d'));
els.markMode.addEventListener('change', () => {
  syncControlButtons();
});
els.btnLoadMission.addEventListener('click', () => {
  loadMission();
});
els.btnClear.addEventListener('click', () => {
  points = [];
  rebuildMarkers();
  setStatus('已清空巡检点');
});
els.btnSave.addEventListener('click', () => {
  saveMission();
});
els.btnExport.addEventListener('click', () => {
  exportMission();
});
els.btnRegister.addEventListener('click', () => {
  registerMap();
});
renderer.domElement.addEventListener('pointerdown', onPointerDown);
renderer.domElement.addEventListener('pointerup', onPointerUp);
window.addEventListener('resize', resize);

setViewMode('2d');
resize();
animate();

(async function boot() {
  try {
    await refreshClouds();
    await loadMission();
    if (els.cloudSelect.value) {
      await loadCloud();
    }
  } catch (err) {
    setStatus(String(err.message || err), 'err');
  }
})();

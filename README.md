# rail_dog_inspection

铁路巡检机器狗二次开发骨架（离线点云可跑通）：读 PCD → 滤波 → 按点位留证 → 写报告。

## 点云放哪？

**放在工作空间的 `data/raw/` 目录。**

| 路径 | 用途 |
|------|------|
| `data/raw/` | **输入**：你的原始点云（`.pcd`）或后续 bag |
| `data/records/` | **输出**：巡检留证（程序自动生成，不要当输入） |
| `data/maps/` | **地图资产**：Map Studio 登记的点云副本与 `map.json` |
| `data/raw/sample_rail_scene.pcd` | 已提供的示例轨旁场景点云 |
| `web/map_studio/` | 离线点云看图 / 标巡检点（写回 `mission_points.yaml`） |

自己的文件示例：`data/raw/my_site_scan.pcd`  
说明见：`data/raw/README.md`

## 包结构

```text
src/
  dog_interfaces/   # 自定义消息 / 服务
  dog_bringup/      # launch、参数、静态 TF、假里程计
  dog_perception/   # PCD 读入发布、裁剪/体素滤波
  dog_inspection/   # 点位任务、留证、ROI 告警、report.json
web/
  map_studio/       # 离线 PCD 三维看图与巡检点标绘
```

## Map Studio（离线看图 / 标点）

不依赖 ROS，用浏览器打开点云、点击标 `P1/P2/…`，可写回任务配置或登记到 `data/maps/`：

```bash
cd web/map_studio
# 推荐：uv（无系统 pip/venv 时也可用）
# curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv .venv
source .venv/bin/activate
uv pip install -r requirements.txt
python -m uvicorn app:app --host 127.0.0.1 --port 8765
```

浏览器打开 [http://127.0.0.1:8765](http://127.0.0.1:8765)。

- 加载 `data/raw/*.pcd`（默认示例 `sample_rail_scene.pcd`）
- **默认 2D 俯视打点**（可切 3D 核对）；开启「标点」后左键落点，右键平移、滚轮缩放
- 可载入 / 写回 `src/dog_inspection/config/mission_points.yaml`（写前自动 `.bak`）
- 「登记到 data/maps」会复制点云并写 `map.json`

## 编译与运行（Ubuntu + ROS 2）

在工作空间根目录（本仓库根）执行：

```bash
cd ~/path/to/rail_dog_inspection   # 或把本仓库拷到 Ubuntu
export RAIL_DOG_WS=$PWD            # 可选：帮助 launch 找到 data/

source /opt/ros/$ROS_DISTRO/setup.bash
rosdep install --from-paths src -y --ignore-src   # 首次
colcon build --symlink-install
source install/setup.bash

ros2 launch dog_bringup inspection_demo.launch.py
```

另开终端启动任务：

```bash
source install/setup.bash
ros2 service call /inspection/start_mission dog_interfaces/srv/StartMission \
  "{mission_name: 'yard_line_a', reset_to_first: true}"
```

查看状态 / 留证结果：

```bash
ros2 topic echo /inspection/status
ls data/records/
```

使用自己的点云：

```bash
ros2 launch dog_bringup inspection_demo.launch.py \
  pcd_path:=data/raw/my_site_scan.pcd
```

重新生成示例点云：

```bash
python3 scripts/generate_sample_pcd.py
```

## 离线 Demo 数据流

```text
sample_rail_scene.pcd
    → pcd_publisher          (/lidar/points, frame=map)
    → cloud_preprocess       (/lidar/points_filtered)
    → mission_manager        到点存 PCD + meta + report.json

fake_odom_publisher: map→odom→base_link（可用 /demo/set_base_pose 传送）
static TF:           base_link→lidar_link
```

任务点配置：`src/dog_inspection/config/mission_points.yaml`（P1/P2/P3 与示例点云中的箱体/立杆对齐）。

## 真机接入时改什么

1. 停用 `pcd_publisher` / `fake_odom_publisher`  
2. 把厂家点云 remap 到 `/lidar/points`，`frame_id` 与 TF 一致  
3. 用厂家外参更新 `config/static_tf.yaml` 与 launch 里的 static TF  
4. 用真实导航目标替换 `demo_teleport`  

业务层（`mission_manager` 状态机与留证）可尽量不动。

# rail_dog_inspection

铁路巡检机器狗二次开发骨架（离线点云可跑通）：读 PCD → 滤波 → 按点位留证 → 写报告。

## 点云放哪？

**放在工作空间的 `data/raw/` 目录。**

| 路径 | 用途 |
|------|------|
| `data/raw/` | **输入**：你的原始点云（`.pcd`）或后续 bag |
| `data/records/` | **输出**：巡检留证（程序自动生成，不要当输入） |
| `data/raw/sample_rail_scene.pcd` | 已提供的示例轨旁场景点云 |

自己的文件示例：`data/raw/my_site_scan.pcd`  
说明见：`data/raw/README.md`

## 包结构

```text
src/
  dog_interfaces/   # 自定义消息 / 服务
  dog_bringup/      # launch、参数、静态 TF、假里程计
  dog_perception/   # PCD 读入发布、裁剪/体素滤波
  dog_inspection/   # 点位任务、留证、ROI 告警、report.json
```

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

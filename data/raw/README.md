# 点云数据放这里

把原始点云文件放在本目录：`rail_dog_inspection/data/raw/`

## 已提供的示例

| 文件 | 说明 |
|------|------|
| `sample_rail_scene.pcd` | 合成轨旁走廊场景（ASCII PCD，含 xyz + intensity） |

场景坐标系为 **map（走廊）**，单位米：

- 地面：`x=0~40`，`y=-5~5`
- 设备箱 1：约 `(10, 2)` → 对应任务点 `P1`
- 设备箱 2：约 `(25, 2.5)` → 对应任务点 `P2`
- 立杆标牌：约 `(35, 0)` → 对应任务点 `P3`

重新生成示例：

```bash
python3 scripts/generate_sample_pcd.py
```

## 你自己的点云怎么放

1. 复制到本目录，例如：`data/raw/my_site_scan.pcd`
2. 启动时指定路径：

```bash
ros2 launch dog_bringup inspection_demo.launch.py \
  pcd_path:=/绝对路径/或相对工作空间根的路径/data/raw/my_site_scan.pcd
```

3. 支持格式（当前读取器）：**ASCII PCD**，字段至少 `x y z`，可选 `intensity`
4. 若是 `ros2 bag`，可先不走 `pcd_publisher`，直接 `ros2 bag play`，并把厂家点云话题 remap 成 `/lidar/points`

## 目录约定

```text
data/
  raw/        # 原始点云 / 录包（输入）← 你的点云放这里
  records/    # 巡检留证输出（程序自动写，勿手改当输入）
  maps/       # 预留：后续建图结果
```

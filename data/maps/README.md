# 地图登记目录

Map Studio「登记为地图」会把选用的点云复制到这里，并写 `map.json` 元数据。

当前仓库仍以 `data/raw/` 作为巡检 Demo 的点云输入；本目录用于沉淀可复用的“地图资产”，供后续选图 / 标点。

## 目录约定

```text
data/maps/
  <map_name>/
    map.json          # 登记元信息
    *.pcd             # 从 data/raw 复制来的点云
```

## map.json 示例

```json
{
  "name": "yard_line_a_map",
  "cloud": "sample_rail_scene.pcd",
  "cloud_path": "data/maps/yard_line_a_map/sample_rail_scene.pcd",
  "source_raw": "data/raw/sample_rail_scene.pcd",
  "note": "示例轨旁走廊",
  "registered_at": "2026-11-09T11:30:00"
}
```

用 Map Studio 登记：

```bash
cd web/map_studio
python3 -m uvicorn app:app --host 127.0.0.1 --port 8765
```

打开 http://127.0.0.1:8765 ，加载点云后填写地图名并点击「登记到 data/maps」。

# v4 配置

## 现行 22 色板（方案 B）

`palette.candidate.json` 是导出用色板。文件名仍带 `candidate`，改名后置。`build_sequence.py` 在最近邻取样和硬 alpha 之后，把不透明像素贴到这 22 色的最近色，不做抖动。透明像素不动。源图留在 `v4/source/`，不改。

在 `prototype/2d_pipeline/v4/` 重跑横斩导出：

```bash
python3 build_sequence.py
```

只改了色板里的 hex / rgb 之后，跑同一条命令即可。脚本要求文件里正好 22 色，且每条 `hex` 与 `rgb` 一致。

现有横斩源是连续调。取样后 01–07 每一帧都有数千个板外色，构建会各打一条 `WARN`，然后仍然贴色并写出 `godot/assets/`。色块宽和帧 06 出血的旧告警照旧。`--strict` 在任一告警（含板外色）时以退出码 1 停住，不写 `godot/assets/`。

```bash
python3 build_sequence.py --strict
```

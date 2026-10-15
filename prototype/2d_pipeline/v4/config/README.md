# v4 配置

## 现行 22 色板（方案 B）

`palette.candidate.json` 是导出用色板。文件名仍带 `candidate`，改名后置。`build_sequence.py` 在最近邻取样和硬 alpha 之后，把不透明像素贴到这 22 色的最近色，不做抖动。透明像素不动。贴色只写导出图，不改源 PNG。

2026-09-26 横斩源已作废（弯刃，与形制图不符），挪到 `v4/source/obsolete-curved-blade/`。现在跑：

```bash
python3 build_sequence.py
```

会直接退出，不写 `godot/assets/`。不要把那批源帧拷回去。下一版源帧换上、并且刀形符合 `docs/美术/形制/初始近战-三视握点.jpg` 之后，同一条命令仍会做最近色、无抖动贴板。脚本要求色板文件里正好 22 色，且每条 `hex` 与 `rgb` 一致。`--strict` 在任一告警（含板外色）时以退出码 1 停住，不写资源。

# 遥遥 3D 角色资源

该目录用于 Blender 角色源文件、建模参考图、可重复的自动化脚本以及网页用 GLB 导出物。

## 当前产物

- `reference/yaoyao-turnaround-v1.png`：基于现有立绘生成的正面、侧面、背面和四分之三视图，仅用于原创角色建模参考。
- `yaoyao-blockout-v1.blend`：第一版低模骨架样机，用于验证独立肢体、动作命名和 GLB 管线，不是最终美术资产。
- `exports/yaoyao-blockout-v1.glb`：网页预览用带骨架动作模型。
- `exports/yaoyao-blockout-preview-v1.png`：样机快照。

老人端启动后可访问 `/companion-3d` 逐个验证动作。该页与主界面隔离，避免低模样机在精修完成前取代现有立绘。

## 重新生成

```bash
blender --background --python assets/blender/scripts/create_yaoyao_blockout.py
```

脚本会重建 `.blend`、GLB 和预览 PNG，不依赖手工操作状态。

## 动作合同

| Blender Action | 页面状态 |
| --- | --- |
| `Idle_Base` | 待机呼吸 |
| `Idle_Wave` | 自动/点击招手 |
| `Listen` | FunASR 录音 |
| `Think` | 模型生成 |
| `Talk` | Fish Speech 播报 |
| `Nod` | 肯定回应 |
| `Cheer` | 积极鼓励 |
| `Concern` | 关切回应 |
| `Alert` | 紧急求助 |

## 最终模型预算

- 三角面：30,000–60,000。
- 材质：不超过 2 个主材质，贴图优先 2048×2048。
- GLB：目标不超过 12 MB。
- 每段动作使用独立 Action，禁止根骨移出展示区。
- 脸部使用 Shape Keys：眼睑、微笑、关切、闭嘴和 A/I/U/E/O 口型。
- 正式模型及动作必须确认创作权和比赛使用权。

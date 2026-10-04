# 遥遥 3D 角色资源

该目录用于 Blender 角色源文件、建模参考图、可重复的自动化脚本以及网页用 GLB 导出物。

## 当前产物

- `reference/yaoyao-turnaround-v1.png`：基于现有立绘生成的正面、侧面、背面和四分之三视图，仅用于原创角色建模参考。
- `reference/{xiaohe,tuantuan,nuannuan}-turnaround-v1.png`：三套兼容同一关节锚点的皮肤建模参考。
- `yaoyao-blockout-v1.blend`：第一版低模骨架样机，用于验证独立肢体、动作命名和 GLB 管线，不是最终美术资产。
- `exports/yaoyao-blockout-v1.glb`：网页预览用带骨架动作模型。
- `exports/yaoyao-blockout-preview-v1.png`：样机快照。

老人端启动后可访问内部地址 `/companion-3d/debug` 逐个验证动作。正式的 `/companion-3d` 只展示已通过美术验收的角色方案，避免低模样机在精修完成前被误当成产品角色。

## 重新生成

```bash
blender --background --python assets/blender/scripts/create_yaoyao_blockout.py
```

脚本会重建 `.blend`、GLB 和预览 PNG，不依赖手工操作状态。可在命令末尾传入 `yaoyao`、`xiaohe`、`tuantuan` 或 `nuannuan`：

```bash
blender --background --python assets/blender/scripts/create_yaoyao_blockout.py -- xiaohe
```

四套皮肤使用完全相同的 18 根骨骼名称、关节位置和 Action 合同；网页只替换 GLB 模型，不重写动作逻辑。

## 动作合同

| Blender Action | 页面状态 |
| --- | --- |
| `Idle_Base` | 持续呼吸、轻微躯干与手臂联动 |
| `Idle_Look` | 自然转头观察，肩胸跟随 |
| `Idle_Shift` | 重心换腿，髋、脊柱与手臂反向平衡 |
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
- 待机状态必须始终播放 `Idle_Base`，每 6–10 秒随机插入 `Idle_Look`、`Idle_Shift`、`Idle_Wave` 或轻微点头，动作间使用 0.2–0.3 秒交叉淡化。
- 正式角色不能只做整体平移；肩、肘、腕、髋、膝、颈部必须有独立骨骼变化，并加入 3–7 秒随机眨眼和轻微目光追踪。
- 脸部使用 Shape Keys：眼睑、微笑、关切、闭嘴和 A/I/U/E/O 口型。
- 正式模型及动作必须确认创作权和比赛使用权。

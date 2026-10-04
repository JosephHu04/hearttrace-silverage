# 小禾正式骨骼候选审查

## 结论

Quaternius 青少年女性基模通过“骨骼、蒙皮、五指、动作重定向”工程验证，但未通过“小禾”正式视觉验收。它只能作为内部建模底座，禁止直接进入老人端或比赛演示。

## 来源与许可

- Universal Base Characters：Quaternius，CC0 1.0 Universal，<https://quaternius.com/packs/universalbasecharacters.html>
- Universal Animation Library：Quaternius，CC0 1.0 Universal，<https://quaternius.com/packs/universalanimationlibrary.html>
- 本地评估输入：`Teen_Female_FullBody.gltf`、`Hair_Buns_Teen.gltf`、`UAL1_Standard.glb`
- 第三方源文件不提交到仓库；候选产物可由脚本在获得合法源文件后重复生成。

## 自动检查结果

| 项目 | 结果 |
| --- | --- |
| Humanoid 骨骼 | 65 根，通过 |
| 五指骨骼 | 左右手完整，通过 |
| 身体与动画骨骼命名 | 完全一致，通过 |
| 双丸子头蒙皮 | 可重绑定到共用骨骼，通过 |
| 导出后动作 | `Idle_Base`、`Idle_Wave`、`Talk`、`Sitting_Idle`、`Sitting_Talk`，通过 |
| GLB 体积 | 约 15 MB，不通过 12 MB 目标 |
| 角色年龄感与比例 | 偏成熟，不符合小禾，不通过 |
| 正式服装 | 缺失，不通过 |
| 眨眼、表情、中文口型 | 缺失，不通过 |

## 下一阶段改造

1. 保留 65 根骨骼、手指权重和五段动作合同。
2. 按 `reference/xiaohe-turnaround-v1.png` 重建头身比例、脸型和双丸子头轮廓。
3. 制作橘杏针织外套、米白衬衫、薄荷绿阔腿裤、袜子与鞋，并重新处理穿插区域权重。
4. 增加眨眼、微笑、关切和 A/I/U/E/O 中文口型 Shape Keys。
5. 合并材质、压缩贴图并重新导出，GLB 必须小于 12 MB。

## 重建命令

```bash
blender --background \
  --python assets/blender/scripts/prepare_xiaohe_rig_base.py -- \
  /path/to/Teen_Female_FullBody.gltf \
  /path/to/Hair_Buns_Teen.gltf \
  /path/to/UAL1_Standard.glb \
  assets/blender/candidates
```

输出目录已加入 `.gitignore`，避免未通过美术验收的大型二进制文件污染 Git 历史。

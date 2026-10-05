# 小禾正式 3D 角色交付门槛

当前 `apps/elder/public/companion/preview/xiaohe-motion-v2.glb` 只用于动作验收。它与 `reference/xiaohe-turnaround-v1.png` 不同，**不得作为正式小禾、老人端首页角色或比赛展示成品**。

## 美术验收（必须人工并排检查）

1. 正面和侧面的头身比、圆润脸型及大眼神态与 `reference/xiaohe-turnaround-v1.png` 接近，不能保留成年女性的脸型和体态。
2. 双丸子头有独立发束和花饰；袖肩、腋下、裤裆、膝盖无明显穿插或断裂。
3. 杏色外套、米白衬衫、绿色阔腿裤、袜子和鞋有明确层次及织物材质，不接受单色圆柱或平面代替。
4. 实测自然待机、招手、说话、坐姿四类状态；眼睛先看、头部后转、肩胸跟随，不能靠整个人平移冒充动作。
5. 至少可见眨眼、微笑、关切三种表情和五个口型；近景播放语音时不应是静止脸。
6. 检查触屏常见尺寸、低端设备帧率、首屏加载和老年用户可读性。

## 自动技术检查

导出的 GLB 必须通过：

```bash
python3 assets/blender/scripts/check_character_asset.py path/to/xiaohe-final.glb
```

它验证文件大小、共享骨骼、五段动作、眨眼/表情/口型。**通过脚本不等于通过美术验收**。只有人工视觉验收和自动技术检查都通过，才替换老人端正式资源。未经验收的第三方素材和实验文件保留在本地候选目录，不直接进入公共仓库。

## 候选调查记录

- Quaternius 基模：动作工程可用，但面部和体态明显偏成年，已否决其正式视觉用途。
- [VRoid Studio 早期 CC0 示例](https://vroid.pixiv.help/hc/en-us/articles/4402614652569-Do-VRoid-Studio-s-sample-models-come-with-conditions-of-use)：具备可编辑的动漫脸，但默认年龄、服装和发型与小禾不符，不能直接替换。
- OpenGameArt 的 [Tiby](https://opengameart.org/content/tiby-3d-rigged-model) 与 [B-chan](https://opengameart.org/content/blender-chan)：前者过于低模，后者风格、年龄和网页性能预算不匹配，均不作为正式小禾。
- [Fab 的免费卡通女孩](https://www.fab.com/listings/fe501f98-a9bb-4acb-b96e-e5b65d8f0d00)：需先接受其最终用户许可协议，且外观仍偏成年；本轮未接受协议或下载素材。

正式路径是基于三视图完成角色建模、绑定、表情键与动画，再进行视觉及性能验收，而不是继续给不合适的成年模型换色。

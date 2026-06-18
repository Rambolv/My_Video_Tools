# VSR 一键使用指南

> Video Subtitle Remover — 视频硬字幕/水印去除工具

## 📥 第一步：下载

### Windows 用户（推荐：预构建包，解压即用）

| 你的显卡 | 下载哪个 |
|---------|---------|
| **NVIDIA GPU** (GTX 1060+) | `vsr-windows-nvidia-cuda-12.6.7z` |
| **NVIDIA 老显卡** (GTX 750~1050) | `vsr-windows-nvidia-cuda-11.8.7z` |
| **NVIDIA RTX 50系** | `vsr-windows-nvidia-cuda-12.8.7z` |
| **AMD / Intel 显卡** | `vsr-windows-directml.7z` |
| **没有独立显卡** | `vsr-windows-cpu.7z` |

**下载地址：**
- ☁️ 百度网盘：[点此下载](https://pan.baidu.com/s/1zR6CjRztmOGBbOkqK8R1Ng?pwd=vsr1) 提取码：`vsr1`
- ☁️ Google Drive：[点此下载](https://drive.google.com/drive/folders/1NRgLNoHHOmdO4GxLhkPbHsYfMOB_3Elr?usp=sharing)

> 💡 不知道自己的显卡型号？按 `Win+R` 输入 `dxdiag`，在「显示」选项卡中查看。

---

## 🚀 第二步：运行

### 方式一：GUI 图形界面（推荐）

```
1. 解压下载的 .7z 文件
2. 双击运行「使用兼容模式运行.cmd」
   （如果不行，试试双击「启动程序.exe」）
3. 程序启动后，点击「选择视频」挑选要处理的视频
4. 用鼠标框选水印/字幕所在的区域
5. 点击「开始处理」
```

### 方式二：Docker（Linux/Mac 用户）

```bash
# NVIDIA 显卡
docker run -it --gpus all eritpchy/video-subtitle-remover:1.4.0-cuda12.6 \
  python backend/main.py -i /input/video.mp4 -o /output/video_no_sub.mp4

# CPU
docker run -it eritpchy/video-subtitle-remover:1.4.0-cpu \
  python backend/main.py -i /input/video.mp4 -o /output/video_no_sub.mp4
```

---

## 🎯 核心功能速览

### 1️⃣ 普通字幕去除

打开软件 → 选框选中字幕区域 → 点「开始处理」

适合：视频底部/顶部的静止字幕

### 2️⃣ 多循环暴力扫除（专治AI水印）

> 针对豆包等AI生成视频的**白色半透明变形水印**

操作步骤：
```
① 点击「多循环暴力扫除」按钮（开启）  
② 设置「扫除次数」（推荐 2~3 次）
③ 点击「开始处理」
```

处理原理：
```
每一轮: 上一轮清理后的视频 → 再次检测 → 再次修复
        逐步磨除残留水印，越清越干净
```

### 3️⃣ 高级设置

在「设置」页面可以调整：
- **处理深度**：0=轻快速，100=极致彻底
- **修复模型**：ProPainter（推荐）、STTN、LaMa、E2FGVI
- **显存监控**：开启后可避免爆显存

---

## ❓ 常见问题

**Q：处理速度很慢？**
- 第一次运行需要加载模型，后续会加快
- 在设置中降低「处理深度」可加速
- 检查是否使用了 GPU（NVIDIA 显卡最快）

**Q：水印去除不干净？**
- 开启「多循环暴力扫除」并增加扫除次数
- 检查水印区域是否框选完整
- 尝试换用 ProPainter 或 LaMa 模型

**Q：提示显存不足？**
- 在设置中开启「显存监控」
- 降低处理深度
- 减少同时处理的任务数

**Q：输出文件在哪里？**
- 默认与输入视频同一目录，文件名带 `_no_sub` 后缀
- 多轮扫除会带轮数标记，如 `视频_3clean_no_sub.mp4`

---

## 🔗 相关链接

- [GitHub 项目主页](https://github.com/Rambolv/Video_Tools)
- [完整功能说明](README.md)
- [问题反馈](https://github.com/Rambolv/Video_Tools/issues)
- QQ群：295894827

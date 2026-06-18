# VSR 发布与打包工具

This directory contains scripts for building and distributing VSR minimal packages.

## 📦 `build_minimal_package.ps1` — 构建最小化安装包

创建一个不包含 AI 模型文件的 Windows 预编译包，模型在首次启动时自动下载。

**前提条件：**
- Windows 系统
- [7-Zip](https://7-zip.org/) 已安装
- 项目已包含完整的 `Python/` 目录（预编译环境）

**使用方法：**
```powershell
cd 项目根目录
powershell -ExecutionPolicy Bypass -File scripts\build_minimal_package.ps1
```

**输出：**
`builds\VSR-Minimal-v1.4.0-windows.7z`

## 📥 `download_models.py` — 模型下载工具

从 GitHub Releases 自动下载所有 AI 模型文件。

**使用方法：**
```bash
# 下载缺失的模型
python scripts/download_models.py

# 强制重新下载所有模型
python scripts/download_models.py --force
```

**模型列表（~700MB 总计）：**

| 模型 | 大小 | 说明 |
|------|------|------|
| big-lama.zip | ~196 MB | LaMa 图像修复模型 |
| propainter.zip | ~190 MB | ProPainter 视频修复模型 |
| sttn-auto.zip | ~63 MB | STTN 自动模式 |
| sttn-det.zip | ~63 MB | STTN 检测模式 |
| ocr-v4-server.zip | ~108 MB | PP-OCRv4 Server 检测模型 |
| ocr-v4-mobile.zip | ~5 MB | PP-OCRv4 Mobile 检测模型 |
| ocr-v5-server.zip | ~84 MB | PP-OCRv5 Server 检测模型 |
| ocr-v5-mobile.zip | ~5 MB | PP-OCRv5 Mobile 检测模型 |

## 🔄 发布流程

1. **构建最小化包：**
   ```powershell
   powershell -ExecutionPolicy Bypass -File scripts\build_minimal_package.ps1
   ```

2. **创建 GitHub Release `v1.4.0`：**
   - 上传 `builds/VSR-Minimal-v1.4.0-windows.7z` 作为 Release 附件

3. **创建模型 Release `models-v1.0`：**
   - 将 `resources/backend/models/` 下各模型目录打包为独立 ZIP
   - 上传至 GitHub Release 标签 `models-v1.0`
   - ZIP 名称需与 `download_models.py` 中的 `MODEL_MANIFEST` 一致

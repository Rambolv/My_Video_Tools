#!/usr/bin/env python3
"""
VoxCPM2 独立 WebUI 启动器 — 使用 audio_studio 集成引擎
不依赖 funasr，通过 Gradio 提供声音克隆/TTS/音色设计/音色转换

用法:
    python launch_voxcpm.py                    # 默认 127.0.0.1:8808
    python launch_voxcpm.py --port 8809        # 自定义端口
"""
import os
import sys
import argparse
import warnings

# ─── 屏蔽第三方库弃用警告 ───
warnings.filterwarnings("ignore", category=FutureWarning,
                       message=".*weight_norm.*")
warnings.filterwarnings("ignore", category=DeprecationWarning,
                       message=".*HTTP_422_UNPROCESSABLE_ENTITY.*")

# ─── 环境修复 ───
os.environ.setdefault("PYTHONNOUSERSITE", "1")
os.environ.setdefault("PYTHONUNBUFFERED", "1")

# ─── 模型缓存内化到本项目（共享 AI 音频模型缓存） ───
_HF_CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                         "..", "..", "..", "vendor", "ai_audio", "models")
os.environ["HF_HOME"] = _HF_CACHE
os.environ["HUGGINGFACE_HUB_CACHE"] = os.path.join(_HF_CACHE, "hub")

# 添加 VoxCPM2 内化路径
_VOX_SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "..", "vendor", "ai_audio", "voxcpm2")
if _VOX_SRC not in sys.path:
    sys.path.insert(0, _VOX_SRC)

# 添加 backend 路径
_BACKEND = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

import gradio as gr
from audio_studio.config import get_config, AudioStudioConfig


def create_voxcpm_ui():
    """创建 VoxCPM2 独立 WebUI（仅人声功能）"""
    import torch
    from audio_studio.core.voice_engine import VoxCPM2Engine, VoiceGenerationParams

    engine = VoxCPM2Engine(device="cuda:0" if torch.cuda.is_available() else "cpu")

    with gr.Blocks(title="VoxCPM2 声音克隆") as demo:
        gr.Markdown(
            "# 🎙 VoxCPM2 声音克隆\n"
            "### 基于 audio_studio 集成引擎 | 原生48kHz无损输出"
        )

        with gr.Tabs():
            # ── TTS ──
            with gr.Tab("📝 文本转语音"):
                with gr.Accordion("❓ 功能说明", open=False):
                    gr.Markdown(
                        """
**文本转语音 (TTS)** 将文字转化为自然流畅的人声。

**使用步骤：**
1. 在「输入文本」框中输入要合成的文字（支持中/英/日/韩等多语种）
2. 调整语速（0.5~2.0，1.0 为正常语速）
3. 选择情感语调（neutral/happy/sad/angry/surprised）
4. 选择输出语言
5. 点击「生成语音」按钮

**参数说明：**
- **语速**：值越小语速越慢，值越大语速越快
- **情感**：影响整体语气色彩，部分语言可能效果不明显
- **语言**：选择与输入文本对应的语言以获得最佳效果

**提示：** 长文本会自动分句合成，无需手动分段。生成结果约 1-3 秒。
                        """
                    )
                with gr.Row():
                    with gr.Column(scale=2):
                        tts_text = gr.Textbox(label="输入文本", lines=5,
                                              placeholder="输入要合成的文本...")
                        with gr.Row():
                            tts_speed = gr.Slider(0.5, 2.0, 1.0, step=0.1, label="语速")
                            tts_emotion = gr.Dropdown(
                                ["neutral", "happy", "sad", "angry", "surprised"],
                                value="neutral", label="情感")
                        tts_lang = gr.Dropdown(
                            ["zh", "en", "ja", "ko", "fr", "de", "es", "ru"],
                            value="zh", label="语言")
                        tts_btn = gr.Button("🎤 生成语音", variant="primary", size="lg")
                    with gr.Column(scale=1):
                        tts_output = gr.Audio(label="生成结果", type="filepath")

                tts_btn.click(
                    fn=lambda text, speed, emo, lang: _do_tts(
                        engine, text, speed, emo, lang
                    ),
                    inputs=[tts_text, tts_speed, tts_emotion, tts_lang],
                    outputs=[tts_output],
                )

            # ── 声音克隆 ──
            with gr.Tab("🎛️ 声音克隆"):
                with gr.Accordion("❓ 功能说明", open=False):
                    gr.Markdown(
                        """
**声音克隆** — 用一段参考音频克隆目标音色，让该音色说出指定文本。

**使用步骤：**
1. 上传一段参考音频（3-30 秒，音色越清晰效果越好）
2. 输入目标文本 — 要让该音色说的内容
3. （可选）勾选「极致克隆模式」以获得更高相似度，此时建议提供参考音频的转录文本
4. 调整语速
5. 点击「开始克隆」

**两种模式对比：**
| 模式 | 特点 | 参考音频要求 |
|------|------|-------------|
| 普通（零样本） | 快速，一次合成 | 任意长度，无需转录 |
| 极致克隆 | 相似度更高，分两步（音色提取→合成） | 需要 5-30 秒清晰人声，建议提供转录文本 |

**提示：** 参考音频请尽量纯净（无背景音乐/噪音），效果更佳。
                        """
                    )
                with gr.Row():
                    with gr.Column():
                        clone_ref = gr.Audio(label="参考音频", type="filepath")
                        clone_text = gr.Textbox(label="目标文本", lines=3,
                                                placeholder="输入要让目标音色说的文本")
                        with gr.Row():
                            clone_ultimate = gr.Checkbox(label="极致克隆模式（需提供转录文本）")
                            clone_speed = gr.Slider(0.5, 2.0, 1.0, step=0.1, label="语速")
                        clone_btn = gr.Button("🎭 开始克隆", variant="primary", size="lg")
                    with gr.Column():
                        clone_output = gr.Audio(label="克隆结果", type="filepath")

                clone_btn.click(
                    fn=lambda ref, text, ult, spd: _do_clone(
                        engine, ref, text, ult, spd
                    ),
                    inputs=[clone_ref, clone_text, clone_ultimate, clone_speed],
                    outputs=[clone_output],
                )

            # ── 音色设计 ──
            with gr.Tab("🎨 声音设计"):
                with gr.Accordion("❓ 功能说明", open=False):
                    gr.Markdown(
                        """
**声音设计** — 无需任何参考音频，仅凭文字描述让 AI 从零创造独一无二的音色。

**使用步骤：**
1. 在「音色描述」中详细描述你想要的音色特征
2. 输入「目标文本」— 要让该音色说的内容
3. 点击「生成音色」

**描述技巧：**
- 包含**性别、年龄、语气、语速**等维度
- 示例：`温柔的年轻女声，语速缓慢，带一点忧郁`
- 示例：`深沉的中年男性播音员，字正腔圆，富有磁性`
- 示例：`活泼的少女音，语速快，元气满满，带笑意`
- 越详细越好！还可以描述**场景**（如「深夜电台主播」）

**提示：** 每次生成的结果可能不同，可多次尝试直到满意。
                        """
                    )
                with gr.Row():
                    with gr.Column(scale=2):
                        design_desc = gr.Textbox(
                            label="音色描述", lines=3,
                            placeholder="如: 温柔的年轻女声，语速缓慢，带一点忧郁"
                        )
                        design_text = gr.Textbox(
                            label="目标文本", lines=3,
                            placeholder="输入要让该音色说的文本"
                        )
                        design_btn = gr.Button("✨ 生成音色", variant="primary", size="lg")
                    with gr.Column(scale=1):
                        design_output = gr.Audio(label="生成结果", type="filepath")

                design_btn.click(
                    fn=lambda desc, text: _do_design(engine, desc, text),
                    inputs=[design_desc, design_text],
                    outputs=[design_output],
                )

            # ── 音色转换 ──
            with gr.Tab("🔄 音色转换"):
                with gr.Accordion("❓ 功能说明", open=False):
                    gr.Markdown(
                        """
**音色转换** — 用参考音色重新演绎指定文本内容。

**使用步骤：**
1. 上传「目标音色参考」— 希望模仿的声音（3-15 秒纯净人声）
2. 填写要生成的内容文本
3. 选择模式：voice=说话声, song=歌声
4. 点击「开始转换」

**提示：**
- 参考音频越清晰，音色还原越准确
- 内容文本是最终输出的文字内容
- 源音频仅作预览参考，不参与模型推理
                        """
                    )
                with gr.Row():
                    with gr.Column():
                        conv_ref = gr.Audio(label="目标音色参考音频", type="filepath")
                        conv_text = gr.Textbox(label="要生成的内容文本（必填）",
                                              placeholder="输入要让目标音色说的文字…",
                                              lines=3)
                        conv_mode = gr.Radio(["voice", "song"], value="voice",
                                            label="模式")
                        conv_btn = gr.Button("🔄 开始转换", variant="primary", size="lg")
                    with gr.Column():
                        conv_output = gr.Audio(label="转换结果", type="filepath")

                conv_btn.click(
                    fn=lambda ref, text, mode: _do_convert(
                        engine, None, ref, mode, text
                    ),
                    inputs=[conv_ref, conv_text, conv_mode],
                    outputs=[conv_output],
                )

        gr.Markdown("---\nPowered by VoxCPM2 + Audio Studio")

    return demo


def _do_tts(engine, text, speed, emotion, lang):
    try:
        path = engine.tts(text, VoiceGenerationParams(
            speed=speed, emotion=emotion, language=lang))
        return path
    except Exception as e:
        raise gr.Error(f"TTS 失败: {e}")


def _do_clone(engine, ref, text, ultimate, speed):
    if not ref:
        raise gr.Error("请上传参考音频")
    try:
        path = engine.clone_voice(text, ref, ultimate=ultimate,
                                  params=VoiceGenerationParams(speed=speed))
        return path
    except Exception as e:
        raise gr.Error(f"克隆失败: {e}")


def _do_design(engine, description, text):
    if not description or not text:
        raise gr.Error("请填写音色描述和目标文本")
    try:
        path = engine.design_voice(text, description)
        return path
    except Exception as e:
        raise gr.Error(f"声音设计失败: {e}")


def _do_convert(engine, src, ref, mode, text=""):
    if not ref:
        raise gr.Error("请上传目标音色参考音频")
    if not text.strip():
        raise gr.Error("请填写要生成的内容文本")
    try:
        path = engine.convert_voice(src, ref, mode=mode, text=text)
        return path
    except Exception as e:
        raise gr.Error(f"音色转换失败: {e}")


def _find_free_port(start: int, max_attempts: int = 20) -> int:
    """从 start 开始扫描可用端口"""
    import socket
    for port in range(start, start + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    raise RuntimeError(f"无法找到可用端口 (范围: {start}-{start + max_attempts - 1})")


def main():
    parser = argparse.ArgumentParser(description="VoxCPM2 WebUI")
    parser.add_argument("--port", type=int, default=8808, help="监听端口")
    parser.add_argument("--host", default="127.0.0.1", help="监听地址")
    args = parser.parse_args()

    # 自动检测可用端口
    try:
        args.port = _find_free_port(args.port)
    except RuntimeError as e:
        print(f"⚠️  {e}")
        sys.exit(1)

    print(f"""
{'='*60}
  🎙 VoxCPM2 声音克隆 WebUI
{'='*60}
  📡 地址: http://{args.host}:{args.port}
  🖥  Python: {sys.executable}
  📂 模型: {_VOX_SRC}
  ⚡ Gradio 启动中...
{'='*60}
""")
    # 允许 Gradio 访问输出目录
    from audio_studio.config import get_config
    _cfg = get_config()
    demo = create_voxcpm_ui()
    demo.launch(server_name=args.host, server_port=args.port, show_error=True,
                allowed_paths=[_cfg.ace_output_dir],
                theme=gr.themes.Soft(),
                css="""
        .accordion.open .accordion-body {max-height: 55vh; overflow-y: auto;}
        .info-text {white-space: normal; word-break: break-word;}
        """)


if __name__ == "__main__":
    main()

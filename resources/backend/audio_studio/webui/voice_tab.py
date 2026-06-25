"""
Gradio 人声标签页 — TTS / 声音克隆 / 音色设计 / 音色转换 / LoRA训练
"""
import os
import tempfile
import gradio as gr
from typing import Optional
from ..core.voice_engine import VoxCPM2Engine, VoiceGenerationParams


def build_voice_tabs(engine: Optional[VoxCPM2Engine] = None) -> gr.Tab:
    """构建人声处理标签页组"""
    if engine is None:
        engine = VoxCPM2Engine()

    with gr.Tab("🎙 文本转语音 (TTS)") as tts_tab:
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
                tts_text = gr.Textbox(
                    label="输入文本", lines=5,
                    placeholder="在此输入要合成的文本...",
                    info="支持中英日韩等多语种，长文本自动分句"
                )
                with gr.Row():
                    tts_speed = gr.Slider(0.5, 2.0, 1.0, step=0.1, label="语速")
                    tts_emotion = gr.Dropdown(
                        ["neutral", "happy", "sad", "angry", "surprised"],
                        value="neutral", label="情感"
                    )
                tts_lang = gr.Dropdown(
                    ["zh", "en", "ja", "ko", "fr", "de", "es", "ru"],
                    value="zh", label="语言"
                )
            with gr.Column(scale=1):
                tts_btn = gr.Button("🎤 生成语音", variant="primary", size="lg")
                tts_output = gr.Audio(label="生成结果", type="filepath")

        tts_btn.click(
            fn=lambda text, speed, emotion, lang: _safe_tts(
                engine, text, speed, emotion, lang
            ),
            inputs=[tts_text, tts_speed, tts_emotion, tts_lang],
            outputs=[tts_output],
        )

    with gr.Tab("🎛️ 声音克隆") as clone_tab:
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
                clone_ref_audio = gr.Audio(label="参考音频", type="filepath")
                clone_ref_text = gr.Textbox(
                    label="参考音频转录文本（极致克隆需要）", lines=2,
                    placeholder="可留空（零样本模式自动跳过）"
                )
                clone_text = gr.Textbox(
                    label="目标文本", lines=3,
                    placeholder="输入要让目标音色说的文本"
                )
                with gr.Row():
                    clone_ultimate = gr.Checkbox(
                        label="极致克隆模式（需要提供转录文本）"
                    )
                    clone_speed = gr.Slider(0.5, 2.0, 1.0, step=0.1, label="语速")
                clone_btn = gr.Button("🎭 开始克隆", variant="primary", size="lg")
                clone_output = gr.Audio(label="克隆结果", type="filepath")

        clone_btn.click(
            fn=lambda ref_audio, ref_text, text, ultimate, speed: _safe_clone(
                engine, ref_audio, ref_text, text, ultimate, speed
            ),
            inputs=[clone_ref_audio, clone_ref_text, clone_text,
                    clone_ultimate, clone_speed],
            outputs=[clone_output],
        )

    with gr.Tab("🎨 声音设计") as design_tab:
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
            fn=lambda desc, text: _safe_design(engine, desc, text),
            inputs=[design_desc, design_text],
            outputs=[design_output],
        )

    with gr.Tab("🔄 音色转换") as convert_tab:
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
                convert_ref = gr.Audio(
                    label="目标音色参考音频", type="filepath"
                )
                convert_text = gr.Textbox(
                    label="要生成的内容文本（必填）",
                    placeholder="输入要让目标音色说的文字…",
                    lines=3,
                )
                convert_mode = gr.Radio(
                    ["voice", "song"], value="voice",
                    label="模式: voice=说话声, song=歌声"
                )
                convert_btn = gr.Button("🔄 开始转换", variant="primary", size="lg")
            with gr.Column():
                convert_output = gr.Audio(label="转换结果", type="filepath")

        convert_btn.click(
            fn=lambda ref, text, mode: _safe_convert(engine, None, ref, mode, text),
            inputs=[convert_ref, convert_text, convert_mode],
            outputs=[convert_output],
        )

    return tts_tab


# ─── 安全调用封装 ───

def _safe_tts(engine, text, speed, emotion, lang):
    try:
        path = engine.tts(text, VoiceGenerationParams(
            speed=speed, emotion=emotion, language=lang
        ))
        return path
    except Exception as e:
        raise gr.Error(f"TTS 失败: {e}")


def _safe_clone(engine, ref_audio, ref_text, text, ultimate, speed):
    if not ref_audio:
        raise gr.Error("请上传参考音频")
    try:
        path = engine.clone_voice(
            text, ref_audio, ref_text or None,
            ultimate=ultimate,
            params=VoiceGenerationParams(speed=speed),
        )
        return path
    except Exception as e:
        raise gr.Error(f"声音克隆失败: {e}")


def _safe_design(engine, description, text):
    if not description or not text:
        raise gr.Error("请填写音色描述和目标文本")
    try:
        path = engine.design_voice(text, description)
        return path
    except Exception as e:
        raise gr.Error(f"声音设计失败: {e}")


def _safe_convert(engine, src, ref, mode, text=""):
    if not ref:
        raise gr.Error("请上传目标音色参考音频")
    if not text.strip():
        raise gr.Error("请填写要生成的内容文本")
    try:
        path = engine.convert_voice(src, ref, mode=mode, text=text)
        return path
    except Exception as e:
        raise gr.Error(f"音色转换失败: {e}")

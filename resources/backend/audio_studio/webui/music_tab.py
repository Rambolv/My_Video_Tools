"""
Gradio 音乐标签页 — 文生音乐 / 歌词生成 / 续写 / 重绘 / 分离
"""
import os
import tempfile
import gradio as gr
from typing import Optional
from ..core.music_engine import AceStepEngine, MusicGenerationParams


# ─── 风格与语言选项 ───
_GENRE_LIST = [
    "pop", "rock", "jazz", "electronic", "classical",
    "hip-hop", "folk", "rnb", "blues", "metal",
]
_LANG_LIST = ["zh", "en", "ja", "ko", "unknown"]


def build_music_tabs(engine: Optional[AceStepEngine] = None) -> gr.Tab:
    """构建音乐处理标签页组"""
    if engine is None:
        engine = AceStepEngine()

    with gr.Tab("🎵 文生音乐") as text2music_tab:
        with gr.Accordion("❓ 功能说明 — 点击展开详细指南", open=False):
            gr.Markdown(
                """
**文生音乐（Text-to-Music）** — 用自然语言描述你想要的音乐，AI 从零生成完整歌曲。

### 使用步骤
1. 在「音乐描述」框中详细描述你想要的音乐
2. 调整时长（10~600 秒）和扩散步数
3. 选择是否纯器乐、是否启用 CoT 推理
4. 点击「生成音乐」等待完成

### 提示词技巧
| 要素 | 说明 | 示例 |
|------|------|------|
| **风格** | pop / rock / jazz / classical 等 |「轻快的 **流行** 情歌」|
| **情绪** | 快乐 / 忧郁 / 史诗 / 慵懒 |「**史诗级** 电影配乐」|
| **乐器** | 钢琴 / 管弦乐团 / 萨克斯 |「**萨克斯** 主导的爵士」|
| **速度** | BPM 数值 |「**120BPM**，C大调」|
| **人声** | 男声 / 女声 / 合唱 |「**女声**，温柔嗓音」|

✅ **推荐格式：** `[风格] + [情绪] + [乐器] + [BPM/调性]`

### 参数说明
- **时长**：越长生成越慢，建议从 30 秒起步测试
- **扩散步数**：`4`=Turbo 极速（推荐），`8~16`=高质量，`32+`=极致（很慢）
- **纯器乐**：勾选后不生成人声
- **CoT 推理**：启用后 AI 会先规划音乐结构再生成，质量更高但稍慢

### 首次使用建议
1. 先用默认参数（30 秒、4 步、Turbo）测试 → 确认效果
2. 满意后再增加时长和步数以获得更高质量
                """
            )
        with gr.Row():
            with gr.Column(scale=2):
                music_caption = gr.Textbox(
                    label="音乐描述", lines=3,
                    placeholder="描述你想要的音乐风格、情绪、乐器..."
                )
                with gr.Row():
                    music_duration = gr.Slider(10, 600, 30, step=5,
                                               label="时长(秒)")
                    music_steps = gr.Slider(1, 100, 4, step=1,
                                            label="扩散步数 (4=turbo)")
                with gr.Row():
                    music_instrumental = gr.Checkbox(label="纯器乐（无人声）")
                    music_thinking = gr.Checkbox(label="启用CoT推理", value=True)
                music_btn = gr.Button("🎶 生成音乐", variant="primary", size="lg")
            with gr.Column(scale=1):
                music_output = gr.Audio(label="生成结果", type="filepath")

        music_btn.click(
            fn=lambda cap, dur, steps, inst, think: _safe_text2music(
                engine, cap, dur, steps, inst, think
            ),
            inputs=[music_caption, music_duration, music_steps,
                    music_instrumental, music_thinking],
            outputs=[music_output],
        )

    with gr.Tab("📝 歌词→歌曲") as lyrics_tab:
        with gr.Accordion("❓ 功能说明 — 点击展开详细指南", open=False):
            gr.Markdown(
                """
**歌词→歌曲（Lyrics-to-Music）** — 输入歌词，AI 自动匹配旋律、编曲和人声演唱。

### 使用步骤
1. 在「歌词」框中输入你的歌词（每行一段，空行分隔主歌/副歌）
2. 选择音乐风格和演唱语言
3. 调整目标时长
4. 点击「生成歌曲」

### 歌词写作建议
- 歌词会直接影响旋律走向，建议写得有节奏感
- 用空行分隔**主歌（Verse）**和**副歌（Chorus）**
- 每行长度建议 5~20 字，太长的句子会被自动切分
- 支持中文、英文、日文、韩文等 50+ 语言

### 示例歌词结构
```
主歌 1
微风轻轻吹过 那片金色的麦田
回忆在空气中 慢慢飘散

副歌
多想回到那个夏天 牵着你的手
看夕阳落下 听海浪的声音

主歌 2
...
```

### 纯器乐模式
在歌词框输入 `[Instrumental]`（或留空），则生成纯音乐，无人声演唱。

### 参数说明
- **风格**：决定编曲的乐器配置和节奏型
- **演唱语言**：歌词的语言，影响发音和韵律
- **时长**：建议 30~120 秒，过长可能导致结构松散
                """
            )
        with gr.Row():
            with gr.Column(scale=2):
                lyrics_text = gr.Textbox(
                    label="歌词", lines=8,
                    placeholder="在此输入你的歌词...\n\n"
                                "（留空或写 [Instrumental] 则生成纯器乐）"
                )
                with gr.Row():
                    lyrics_genre = gr.Dropdown(
                        _GENRE_LIST, value="pop", label="风格"
                    )
                    lyrics_lang = gr.Dropdown(
                        _LANG_LIST, value="zh", label="演唱语言"
                    )
                    lyrics_duration = gr.Slider(10, 600, 30, step=5,
                                                label="时长(秒)")
                lyrics_btn = gr.Button("🎤 生成歌曲", variant="primary", size="lg")
            with gr.Column(scale=1):
                lyrics_output = gr.Audio(label="生成结果", type="filepath")

        lyrics_btn.click(
            fn=lambda ly, genre, lang, dur: _safe_lyrics(
                engine, ly, genre, dur
            ),
            inputs=[lyrics_text, lyrics_genre, lyrics_lang, lyrics_duration],
            outputs=[lyrics_output],
        )

    with gr.Tab("✂️ 音乐编辑") as edit_tab:
        gr.Markdown("## 音乐编辑工具集")
        with gr.Tabs():
            with gr.Tab("🔄 续写扩写"):
                with gr.Accordion("❓ 功能说明 — 点击展开", open=False):
                    gr.Markdown(
                        """
**续写扩写（Continue）** — 上传一段短音频片段，AI 理解其风格后续写为完整歌曲。

### 使用步骤
1. 上传一段 10 秒以上的音频片段
2. 设定目标总时长
3. 点击「续写」

### 适用场景
- 把一段灵感旋律发展为完整歌曲
- 延长现有音乐（如短视频 BGM 加长）
- 基于喜欢的风格生成更多内容

### 注意事项
- 输入片段越长，风格还原越准确
- 建议片段至少 10 秒，包含明确的旋律和节奏
- 目标时长包含原片段长度
                        """
                    )
                with gr.Row():
                    with gr.Column():
                        cont_audio = gr.Audio(
                            label="参考音频（短片段）", type="filepath"
                        )
                        cont_duration = gr.Slider(
                            30, 600, 120, step=10, label="目标总时长(秒)"
                        )
                        cont_btn = gr.Button("🔄 续写", variant="primary")
                    with gr.Column():
                        cont_output = gr.Audio(label="续写结果", type="filepath")

                cont_btn.click(
                    fn=lambda audio, dur: _safe_continue(engine, audio, dur),
                    inputs=[cont_audio, cont_duration],
                    outputs=[cont_output],
                )

            with gr.Tab("🎨 局部重绘"):
                with gr.Accordion("❓ 功能说明 — 点击展开", open=False):
                    gr.Markdown(
                        """
**局部重绘（Repaint）** — 指定音频的某段时间重新生成，保留其余部分不变。

### 使用步骤
1. 上传源音频
2. 设置「重绘起始」和「重绘结束」时间（秒）
3. 点击「重绘」

### 适用场景
- 替换不满意的一段旋律
- 修复生成中的瑕疵部分
- 在保留整体结构的前提下修改细节

### 参数说明
- **起始(秒)**：从第几秒开始重绘
- **结束(秒)**：到第几秒结束重绘（-1 表示到结尾）
- 重绘区域前后的音频保持不变，用于衔接

### 提示
- 重绘区域越小，越容易与原音频衔接自然
- 建议从 5~10 秒的片段开始尝试
                        """
                    )
                with gr.Row():
                    with gr.Column():
                        repaint_audio = gr.Audio(
                            label="源音频", type="filepath"
                        )
                        with gr.Row():
                            repaint_start = gr.Number(
                                label="重绘起始(秒)", value=10, minimum=0
                            )
                            repaint_end = gr.Number(
                                label="重绘结束(秒)", value=20, minimum=-1
                            )
                        repaint_btn = gr.Button("🎨 重绘", variant="primary")
                    with gr.Column():
                        repaint_output = gr.Audio(
                            label="重绘结果", type="filepath"
                        )

                repaint_btn.click(
                    fn=lambda audio, start, end: _safe_repaint(
                        engine, audio, start, end
                    ),
                    inputs=[repaint_audio, repaint_start, repaint_end],
                    outputs=[repaint_output],
                )

            with gr.Tab("🧑‍🎤 翻唱生成"):
                with gr.Accordion("❓ 功能说明 — 点击展开", open=False):
                    gr.Markdown(
                        """
**翻唱生成（Cover）** — 给定一首歌，以全新的音乐风格重新演绎。

### 使用步骤
1. 上传原曲音频
2. （可选）描述目标风格，留空则自动选择风格
3. 点击「翻唱」

### 风格提示词示例
- 「改成 **爵士** 风格，萨克斯代替原旋律」
- 「**摇滚** 版，失真吉他，强劲鼓点」
- 「改为 **钢琴独奏**，慢速，抒情」
- 「**电子舞曲** 风格，140BPM」

### 提示
- 风格描述越具体，翻唱效果越好
- 不填写风格描述会尽量保留原曲风格
- 翻唱会保留原曲的旋律轮廓，改变编曲和节奏
                        """
                    )
                with gr.Row():
                    with gr.Column():
                        cover_audio = gr.Audio(
                            label="原曲", type="filepath"
                        )
                        cover_style = gr.Textbox(
                            label="目标风格描述（可选）",
                            placeholder="如: 「改成爵士风格」"
                        )
                        cover_btn = gr.Button("🎤 翻唱", variant="primary")
                    with gr.Column():
                        cover_output = gr.Audio(
                            label="翻唱结果", type="filepath"
                        )

                cover_btn.click(
                    fn=lambda audio, style: _safe_cover(engine, audio, style),
                    inputs=[cover_audio, cover_style],
                    outputs=[cover_output],
                )

            with gr.Tab("🔊 人声伴奏分离"):
                with gr.Accordion("❓ 功能说明 — 点击展开", open=False):
                    gr.Markdown(
                        """
**人声伴奏分离（Vocal Separation）** — 将混合音频中的人声和伴奏分离为独立音轨。

### 使用步骤
1. 上传混合音频（MP3 / WAV / FLAC 等格式）
2. 点击「分离」
3. 等待处理完成，结果分为人声和伴奏两个音轨

### 适用场景
- 提取歌曲中的人声用于声音克隆
- 获取纯伴奏用于 K 歌或混音
- 分离播客中的人声和背景音乐

### 注意事项
- 分离质量取决于原音频的清晰度
- 背景噪音会影响分离效果
- 处理后的人声和伴奏可能存在轻微的串音
                        """
                    )
                with gr.Row():
                    with gr.Column():
                        sep_audio = gr.Audio(
                            label="上传混合音频", type="filepath"
                        )
                        sep_btn = gr.Button("🔊 分离", variant="primary")
                    with gr.Column():
                        sep_vocals = gr.Audio(label="人声", type="filepath")
                        sep_inst = gr.Audio(label="伴奏", type="filepath")

                sep_btn.click(
                    fn=lambda audio: _safe_separate(engine, audio),
                    inputs=[sep_audio],
                    outputs=[sep_vocals, sep_inst],
                )

    return text2music_tab


# ─── 安全调用封装 ───

def _safe_text2music(engine, caption, duration, steps, instrumental, thinking):
    try:
        params = MusicGenerationParams(
            caption=caption, duration=duration,
            inference_steps=steps, instrumental=instrumental,
            thinking=thinking,
        )
        result = engine.text_to_music(caption, params)
        return result.audio_path
    except Exception as e:
        raise gr.Error(f"音乐生成失败: {e}")


def _safe_lyrics(engine, lyrics, genre, duration):
    try:
        result = engine.lyrics_to_song(lyrics, genre,
                                       MusicGenerationParams(duration=duration))
        return result.audio_path
    except Exception as e:
        raise gr.Error(f"歌词生成失败: {e}")


def _safe_continue(engine, audio, duration):
    if not audio:
        raise gr.Error("请上传参考音频")
    try:
        result = engine.continue_music(audio, int(duration))
        return result.audio_path
    except Exception as e:
        raise gr.Error(f"续写失败: {e}")


def _safe_repaint(engine, audio, start, end):
    if not audio:
        raise gr.Error("请上传源音频")
    try:
        result = engine.repaint(audio, float(start), float(end))
        return result.audio_path
    except Exception as e:
        raise gr.Error(f"重绘失败: {e}")


def _safe_cover(engine, audio, style):
    if not audio:
        raise gr.Error("请上传原曲")
    try:
        result = engine.cover_song(audio, style or "")
        return result.audio_path
    except Exception as e:
        raise gr.Error(f"翻唱失败: {e}")


def _safe_separate(engine, audio):
    if not audio:
        raise gr.Error("请上传音频")
    try:
        vocals, no_vocals = engine.separate(audio)
        return vocals, no_vocals
    except Exception as e:
        raise gr.Error(f"分离失败: {e}")

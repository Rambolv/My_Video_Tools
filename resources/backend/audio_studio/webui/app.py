"""
Gradio 主应用 — 声音自由生成修改大师 WebUI
"""
import os
import sys
import logging
import gradio as gr
from typing import Optional

from ..config import get_config
from ..core.voice_engine import VoxCPM2Engine
from ..core.music_engine import AceStepEngine
from .voice_tab import build_voice_tabs
from .music_tab import build_music_tabs

logger = logging.getLogger(__name__)

# 页脚
_FOOTER = """
---
<div style="text-align: center; color: #888; font-size: 12px;">
    🔊 声音自由生成修改大师 v1.0.0 |
    人声底座: VoxCPM2 (48kHz) |
    音乐底座: ACE-Step 1.5 |
    <a href="http://127.0.0.1:8000/docs" target="_blank">REST API 文档</a>
</div>
"""


def create_ui(voice_engine: Optional[VoxCPM2Engine] = None,
              music_engine: Optional[AceStepEngine] = None) -> gr.Blocks:
    """创建 Gradio 主界面"""
    cfg = get_config()

    with gr.Blocks(
        title="声音自由生成修改大师",
    ) as demo:
        # ── 顶部横幅 ──
        gr.Markdown(
            "# 🎵 声音自由生成修改大师\n"
            "### 本地化AI音频工作站 — 人声(VoxCPM2) + 音乐(ACE-Step 1.5)\n"
            "> ⚠️ **合规提示**: 本系统仅用于合法用途。禁止用于诈骗、冒充他人、伪造证据等违法行为。"
            "生成内容将嵌入不可见水印以便溯源。"
        )

        # ── 设备信息 ──
        with gr.Row():
            device_status = f"🖥 设备: {cfg.device.upper()} | 精度: {cfg.dtype.upper()}"
            device_status += f" | 显存限制: {cfg.vram_limit_gb}GB"
            gr.Markdown(f"`{device_status}`")

        # ── 主标签页 ──
        with gr.Tabs():
            # 人声处理
            build_voice_tabs(voice_engine)
            # 音乐处理
            build_music_tabs(music_engine)
            # 工具标签
            with gr.Tab("🔧 音频工具"):
                gr.Markdown("## 通用音频处理工具")
                with gr.Row():
                    with gr.Column():
                        tool_input = gr.Audio(label="输入音频", type="filepath")
                        tool_task = gr.Radio(
                            ["降噪", "音量归一化", "格式转WAV", "重采样48kHz"],
                            value="降噪", label="处理任务"
                        )
                        tool_btn = gr.Button("⚡ 执行", variant="primary")
                    with gr.Column():
                        tool_output = gr.Audio(label="处理结果", type="filepath")

                tool_btn.click(
                    fn=_run_audio_tool,
                    inputs=[tool_input, tool_task],
                    outputs=[tool_output],
                )

            # ⚙️ 路径设置
            with gr.Tab("⚙️ 路径设置"):
                gr.Markdown("## 自定义模型与输出路径")
                gr.Markdown(
                    "修改后点击「保存设置」立即生效。"
                    "模型路径变更后需要重新下载/复制模型文件到新目录。"
                )
                with gr.Row():
                    with gr.Column():
                        set_checkpoints = gr.Textbox(
                            label="ACE 模型文件夹",
                            value=cfg.ace_checkpoints_dir,
                            placeholder="存放 ACE 模型权重的目录…",
                        )
                        set_output = gr.Textbox(
                            label="ACE 生成物存放文件夹",
                            value=cfg.ace_output_dir,
                            placeholder="存放生成音频的目录…",
                        )
                    with gr.Column():
                        set_models = gr.Textbox(
                            label="通用模型文件夹",
                            value=cfg.models_dir,
                            placeholder="存放其他模型文件的目录…",
                        )
                        set_vox_path = gr.Textbox(
                            label="VoxCPM2 源码路径",
                            value=cfg.voxcpm2_path,
                            placeholder="vendor/ai_audio/voxcpm2",
                        )
                with gr.Row():
                    save_btn = gr.Button("💾 保存设置", variant="primary", size="lg")
                    reset_btn = gr.Button("↩️ 恢复默认", size="lg")
                    save_status = gr.Markdown("", visible=True)

                def _save_settings(checkpoints, output, models, vox_path):
                    from ..config import get_config, save_config
                    cfg = get_config()
                    cfg.ace_checkpoints_dir = checkpoints.strip()
                    cfg.ace_output_dir = output.strip()
                    cfg.models_dir = models.strip()
                    cfg.voxcpm2_path = vox_path.strip()
                    # 确保目录存在
                    for d in [cfg.ace_checkpoints_dir, cfg.ace_output_dir, cfg.models_dir]:
                        os.makedirs(d, exist_ok=True)
                    save_config()
                    return "✅ 设置已保存！部分变更需要重启 WebUI 后生效。"

                def _reset_settings():
                    from ..config import get_config, save_config
                    import json, os
                    cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "user_config.json")
                    if os.path.exists(cfg_path):
                        os.remove(cfg_path)
                    # 重建默认配置
                    from ..config import AudioStudioConfig
                    default = AudioStudioConfig()
                    cfg = get_config()
                    cfg.ace_checkpoints_dir = default.ace_checkpoints_dir
                    cfg.ace_output_dir = default.ace_output_dir
                    cfg.models_dir = default.models_dir
                    cfg.voxcpm2_path = default.voxcpm2_path
                    save_config()
                    return (
                        default.ace_checkpoints_dir,
                        default.ace_output_dir,
                        default.models_dir,
                        default.voxcpm2_path,
                        "✅ 已恢复默认设置！重启 WebUI 后完全生效。",
                    )

                save_btn.click(
                    fn=_save_settings,
                    inputs=[set_checkpoints, set_output, set_models, set_vox_path],
                    outputs=[save_status],
                )
                reset_btn.click(
                    fn=_reset_settings,
                    inputs=[],
                    outputs=[set_checkpoints, set_output, set_models, set_vox_path, save_status],
                )

            # 关于
            with gr.Tab("📖 关于"):
                gr.Markdown(f"""
                ## 声音自由生成修改大师 v1.0.0

                ### 技术架构
                | 模块 | 底座 | 架构 |
                |------|------|------|
                | 🎙 人声处理 | VoxCPM2 | AudioVAE V2 + LocEnc → TSLM → RALM → LocDiT |
                | 🎵 音乐生成 | ACE-Step 1.5 | LM规划器(CoT) + DiT扩散解码器 |

                ### 硬件要求
                - **最低**: 8GB VRAM (人声全功能) / 4GB VRAM (音乐基础功能)
                - **推荐**: RTX 4090 24GB (全功能)
                - **平台**: Windows 10/11, Linux (CUDA 12+)

                ### 合规声明
                本系统所有AI模型均在本地运行，音频数据不上传任何服务器。
                生成内容嵌入不可见水印，请遵守相关法律法规。
                """)

        # ── 页脚 ──
        gr.Markdown(_FOOTER)

        # ── 合规提示前置 ──
        gr.Markdown(
            "> ⚠️ **使用前请确认**: 本系统生成的内容（包括但不限于语音、音乐）仅供合法用途。"
            "用户对生成内容的使用负全部法律责任。系统内置隐式水印用于内容溯源。"
        )

    return demo


def _run_audio_tool(audio_path, task):
    """运行音频工具"""
    from ..utils.audio_chain import AudioToolChain as AudioTool
    if not audio_path:
        raise gr.Error("请上传音频文件")
    tool = AudioTool()
    if task == "降噪":
        return tool.denoise(audio_path)
    elif task == "音量归一化":
        return tool.normalize(audio_path)
    elif task == "格式转WAV":
        return tool.convert_format(audio_path, "wav")
    elif task == "重采样48kHz":
        return tool.resample(audio_path, 48000)
    return audio_path


def launch_gradio(host: str = "127.0.0.1", port: int = 7865,
                  share: bool = False, debug: bool = False):
    """启动 Gradio WebUI"""
    logger.info(f"🚀 声音自由生成修改大师启动: http://{host}:{port}")
    from ..config import get_config
    cfg = get_config()
    demo = create_ui()
    import gradio as gr
    demo.launch(
        server_name=host,
        server_port=port,
        share=share,
        debug=debug,
        allowed_paths=[cfg.ace_output_dir],
        theme=gr.themes.Soft(
            primary_hue="blue",
            neutral_hue="slate",
            font=gr.themes.GoogleFont("Noto Sans SC"),
        ),
        css="""
        footer {visibility: hidden}
        .warning-message {background: #fff3cd; color: #856404; padding: 12px; border-radius: 8px;}
        /* 功能说明折叠面板内容滚动 */
        .accordion:not(.open) .accordion-body {display: none;}
        .accordion.open .accordion-body {max-height: 60vh; overflow-y: auto;}
        .has-info-container .info-icon {cursor: help;}
        /* Gradio 组件提示文字换行 */
        .info-text {white-space: normal; word-break: break-word;}
        """,
    )

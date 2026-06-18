import os
import sys
import subprocess
from backend.config import config, BASE_DIR
from backend.tools.common_tools import merge_big_file_if_not_exists
from backend.tools.constant import SubtitleDetectMode


# LVBOBO_markdown_BUG - 新增：首次启动自动检测并下载缺失模型
def _ensure_models_downloaded():
    """Check if models exist; if not, prompt user to download."""
    models_dir = os.path.join(BASE_DIR, 'models')
    if not os.path.isdir(models_dir):
        os.makedirs(models_dir, exist_ok=True)

    # Check essential model directories
    essential = [
        os.path.join(models_dir, 'big-lama'),
        os.path.join(models_dir, 'sttn-auto'),
        os.path.join(models_dir, 'sttn-det'),
        os.path.join(models_dir, 'propainter'),
        os.path.join(models_dir, 'V4', 'ch_det'),
        os.path.join(models_dir, 'V4', 'ch_det_fast'),
        os.path.join(models_dir, 'V5', 'ch_det'),
        os.path.join(models_dir, 'V5', 'ch_det_fast'),
    ]

    missing = [d for d in essential if not os.path.isdir(d) or
               not any(f for f in os.listdir(d) if f != 'fs_manifest.csv')]

    if not missing:
        return  # All models present

    print("=" * 60)
    print("  ⚠️  AI models not found in the minimal package.")
    print("  Models must be downloaded before first use.")
    print("=" * 60)

    # Try automatic download via scripts/download_models.py
    script_path = os.path.join(os.path.dirname(BASE_DIR), 'scripts', 'download_models.py')
    if os.path.isfile(script_path):
        print("\n📥 Auto-downloading models (this may take a while)...")
        print("   Download size: ~700 MB")
        try:
            result = subprocess.run(
                [sys.executable, script_path],
                cwd=os.path.dirname(BASE_DIR),
                capture_output=True, text=True, timeout=1800
            )
            if result.returncode == 0:
                print("✅ All models downloaded successfully!")
                return
            else:
                print(f"❌ Auto-download failed:\n{result.stderr}")
        except subprocess.TimeoutExpired:
            print("❌ Download timed out (30 min limit)")
        except Exception as e:
            print(f"❌ Download error: {e}")
    else:
        print(f"\n📋 Download script not found at: {script_path}")

    # Fallback: manual instructions
    print("\n" + "-" * 60)
    print("  Manual download instructions:")
    print(f"  1. Visit: https://github.com/Rambolv/My_Video_Tools/releases")
    print(f"     and download the latest model package (models-v1.0)")
    print(f"  2. Extract all zip files to: {models_dir}")
    print(f"  3. Restart the application")
    print("-" * 60)


class ModelConfig:
    def __init__(self):
        # Ensure models are downloaded before proceeding
        _ensure_models_downloaded()

        self.LAMA_MODEL_DIR = os.path.join(BASE_DIR, 'models', 'big-lama')
        self.STTN_AUTO_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'sttn-auto', 'infer_model.pth')
        self.STTN_DET_MODEL_PATH = os.path.join(BASE_DIR, 'models', 'sttn-det', 'sttn.pth')
        self.PROPAINTER_MODEL_DIR = os.path.join(BASE_DIR,'models', 'propainter')
        if config.subtitleDetectMode.value == SubtitleDetectMode.PP_OCRv5_MOBILE:
            self.DET_MODEL_DIR = os.path.join(BASE_DIR,'models', 'V5', 'ch_det_fast')
        elif config.subtitleDetectMode.value == SubtitleDetectMode.PP_OCRv5_SERVER:
            self.DET_MODEL_DIR = os.path.join(BASE_DIR, 'models', 'V5', 'ch_det')
        elif config.subtitleDetectMode.value == SubtitleDetectMode.PP_OCRv4_MOBILE:
            self.DET_MODEL_DIR = os.path.join(BASE_DIR,'models', 'V4', 'ch_det_fast')
        elif config.subtitleDetectMode.value == SubtitleDetectMode.PP_OCRv4_SERVER:
            self.DET_MODEL_DIR = os.path.join(BASE_DIR, 'models', 'V4', 'ch_det')
        elif config.subtitleDetectMode.value in (
            SubtitleDetectMode.SAM2_TINY, SubtitleDetectMode.SAM2_SMALL,
            SubtitleDetectMode.SAM2_BASE, SubtitleDetectMode.SAM2_LARGE,
        ):
            # SAM2 使用独立模型，不需要 DET_MODEL_DIR
            self.DET_MODEL_DIR = os.path.join(BASE_DIR, 'models', 'V4', 'ch_det')  # fallback for OCR
        else:
            raise ValueError(f"Invalid subtitle detect mode: {config.subtitleDetectMode.value}")

        merge_big_file_if_not_exists(self.LAMA_MODEL_DIR, 'big-lama.pt')
        merge_big_file_if_not_exists(self.PROPAINTER_MODEL_DIR, 'ProPainter.pth')
        merge_big_file_if_not_exists(self.DET_MODEL_DIR, 'inference.onnx')
    
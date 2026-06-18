"""
VSR Model Downloader
Downloads AI models from GitHub Releases on first launch.

Models are downloaded from:
  https://github.com/Rambolv/My_Video_Tools/releases/download/models-v1.0/

Usage:
    python scripts/download_models.py
    python scripts/download_models.py --force   # Re-download even if exists
"""

import os
import sys
import json
import hashlib
import urllib.request
import urllib.error
import zipfile
import tarfile
import shutil
import time
import argparse

# ---------- Configuration ----------
REPO_OWNER = "Rambolv"
REPO_NAME = "My_Video_Tools"
RELEASE_TAG = "models-v1.0"
BASE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/releases/download/{RELEASE_TAG}"

# Resolve project root: scripts/ is one level below root
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
MODELS_DIR = os.path.join(PROJECT_ROOT, "resources", "backend", "models")

MODEL_MANIFEST = {
    "big-lama.zip": {
        "dir": "big-lama",
        "description": "LaMa inpainting model (~196MB)",
        "size_mb": 196.3,
    },
    "propainter.zip": {
        "dir": "propainter",
        "description": "ProPainter inpainting model (~190MB)",
        "size_mb": 190.0,
    },
    "sttn-auto.zip": {
        "dir": "sttn-auto",
        "description": "STTN Auto inpainting model (~63MB)",
        "size_mb": 63.2,
    },
    "sttn-det.zip": {
        "dir": "sttn-det",
        "description": "STTN Det inpainting model (~63MB)",
        "size_mb": 63.2,
    },
    "ocr-v4-server.zip": {
        "dir": os.path.join("V4", "ch_det"),
        "description": "PP-OCRv4 Server detection model (~108MB)",
        "size_mb": 108.2,
    },
    "ocr-v4-mobile.zip": {
        "dir": os.path.join("V4", "ch_det_fast"),
        "description": "PP-OCRv4 Mobile detection model (~5MB)",
        "size_mb": 4.6,
    },
    "ocr-v5-server.zip": {
        "dir": os.path.join("V5", "ch_det"),
        "description": "PP-OCRv5 Server detection model (~84MB)",
        "size_mb": 84.0,
    },
    "ocr-v5-mobile.zip": {
        "dir": os.path.join("V5", "ch_det_fast"),
        "description": "PP-OCRv5 Mobile detection model (~5MB)",
        "size_mb": 4.6,
    },
}


def print_progress(current, total, bar_length=40):
    """Print a simple progress bar."""
    percent = current / total if total > 0 else 0
    filled = int(bar_length * percent)
    bar = "█" * filled + "░" * (bar_length - filled)
    sys.stdout.write(f"\r  [{bar}] {percent:.1%} ({current:.1f}/{total:.1f} MB)")
    sys.stdout.flush()


class DownloadProgress:
    """Report download progress."""
    def __init__(self):
        self.downloaded = 0
        self.last_report = 0

    def __call__(self, block_count, block_size, total_size):
        self.downloaded = block_count * block_size / (1024 * 1024)
        total_mb = total_size / (1024 * 1024) if total_size > 0 else 0
        if self.downloaded - self.last_report > 1 or self.downloaded >= total_mb:
            print_progress(self.downloaded, total_mb)
            self.last_report = self.downloaded


def download_file(url, dest_path, desc="Downloading"):
    """Download a file with progress reporting."""
    print(f"\n📥 {desc}")
    print(f"   From: {url}")
    print(f"   To:   {dest_path}")
    try:
        urllib.request.urlretrieve(url, dest_path, DownloadProgress())
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"\n   ✅ Done ({size_mb:.1f} MB)")
        return True
    except urllib.error.HTTPError as e:
        print(f"\n   ❌ HTTP Error {e.code}: {e.reason}")
        return False
    except urllib.error.URLError as e:
        print(f"\n   ❌ Network Error: {e.reason}")
        return False
    except Exception as e:
        print(f"\n   ❌ Error: {e}")
        return False


def extract_zip(zip_path, extract_dir):
    """Extract a zip file to the target directory."""
    print(f"   📦 Extracting to {extract_dir}...")
    try:
        os.makedirs(extract_dir, exist_ok=True)
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)
        print(f"   ✅ Extracted successfully")
        return True
    except Exception as e:
        print(f"   ❌ Extraction failed: {e}")
        return False


def verify_model_dir(model_dir, expected_file=None):
    """Check if a model directory contains the expected file."""
    if not os.path.isdir(model_dir):
        return False
    if expected_file:
        return os.path.isfile(os.path.join(model_dir, expected_file))
    # Check if directory has any files (excluding manifest)
    files = [f for f in os.listdir(model_dir) if f != "fs_manifest.csv"]
    return len(files) > 0


def download_all_models(force=False):
    """Download all missing models."""
    print("=" * 60)
    print("  VSR Model Downloader")
    print("=" * 60)
    print(f"\n📂 Models will be saved to: {MODELS_DIR}")
    print(f"🔗 Repository: {REPO_OWNER}/{REPO_NAME}")
    print()

    os.makedirs(MODELS_DIR, exist_ok=True)
    total_models = len(MODEL_MANIFEST)
    downloaded = 0
    skipped = 0
    failed = 0

    for idx, (zip_name, info) in enumerate(MODEL_MANIFEST.items(), 1):
        model_dir = os.path.join(MODELS_DIR, info["dir"])
        print(f"\n[{idx}/{total_models}] {info['description']}")

        # Check if already exists
        if not force and verify_model_dir(model_dir):
            print(f"   ⏭️  Already exists, skipping")
            skipped += 1
            continue

        # Ensure parent directory exists
        os.makedirs(os.path.dirname(model_dir), exist_ok=True)

        # Download
        url = f"{BASE_URL}/{zip_name}"
        zip_path = os.path.join(MODELS_DIR, zip_name)
        
        if download_file(url, zip_path, desc=f"Downloading {zip_name}"):
            # Extract
            if extract_zip(zip_path, model_dir):
                downloaded += 1
            else:
                failed += 1
            # Clean up zip
            try:
                os.remove(zip_path)
            except:
                pass
        else:
            failed += 1

    # Summary
    print("\n" + "=" * 60)
    print(f"  Summary: {downloaded} downloaded, {skipped} skipped, {failed} failed")
    print("=" * 60)
    
    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="VSR Model Downloader")
    parser.add_argument("--force", action="store_true",
                       help="Re-download models even if they already exist")
    parser.add_argument("--model", type=str, default=None,
                       help="Download a specific model only (zip name without .zip)")
    args = parser.parse_args()

    success = download_all_models(force=args.force)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

"""
视频加密/解密脚本 (v2.0 — AES 文件级加密)

用法:
    py cli.py

依赖 Config/config.ini 中的:
    VIDEO_PATH       — 原始视频路径
    IMG_VIDEO_PATH   — 输出目录
    MODE             — encrypt 或 decrypt（可选，默认 encrypt）
    PASSWORD         — 加密/解密密码
"""

import os
import sys
import getpass

sys.path.append(os.path.join(os.path.split(os.path.realpath(__file__))[0], 'Config'))
from config import global_config

# 导入统一处理管线
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import warnings
warnings.filterwarnings('ignore', category=DeprecationWarning)
from core import process_video


def main():
    print("=" * 60)
    print("CLI — Video Encryption Tool v2.0")
    print("=" * 60)

    video_path = global_config.getRaw('config', 'VIDEO_PATH')
    output_dir = global_config.getRaw('config', 'IMG_VIDEO_PATH')

    mode = global_config.getOpt('config', 'MODE', fallback='encrypt')
    if mode in ('obfuscate', 'deobfuscate'):
        mode = 'encrypt' if mode == 'obfuscate' else 'decrypt'

    password = global_config.getOpt('config', 'PASSWORD', fallback='').strip()
    if not password:
        password = getpass.getpass("Enter password: ")

    mode_label = 'Encrypt' if mode == 'encrypt' else 'Decrypt'
    print(f"Input:  {video_path}")
    print(f"Output: {output_dir}")
    print(f"Mode:   {mode_label}")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video file not found: {video_path}")

    output_path = os.path.join(output_dir, 'result.ve2' if mode == 'encrypt' else 'result.mp4')

    result = process_video(
        input_path=video_path,
        output_path=output_path,
        mode=mode,
        password=password,
    )

    if mode == 'encrypt':
        print(f"\nEncryption complete. Remember your password!")

    print(f"\nOutput: {output_path}")
    print("=" * 60)

    return output_path


if __name__ == '__main__':
    main()

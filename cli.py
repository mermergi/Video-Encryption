"""
视频合成脚本 —— 从原视频直接流式读取 + 混淆 + 输出
无需中间图片文件，可选处理音频。

用法:
    py cli.py

依赖 Config/config.ini 中的:
    VIDEO_PATH       — 原始视频路径
    IMG_VIDEO_PATH   — 输出目录
"""

import os
import sys

sys.path.append(os.path.join(os.path.split(os.path.realpath(__file__))[0], 'Config'))
from config import global_config

# 导入统一处理管线
sys.path.append(os.path.dirname(os.path.realpath(__file__)))
from core import process_video


def main():
    print("=" * 60)
    print("CLI — 视频混淆 (流式处理)")
    print("=" * 60)

    video_path = global_config.getRaw('config', 'VIDEO_PATH')
    output_dir = global_config.getRaw('config', 'IMG_VIDEO_PATH')

    print(f"输入视频: {video_path}")
    print(f"输出目录: {output_dir}")

    if not os.path.exists(video_path):
        raise FileNotFoundError(f"视频文件不存在: {video_path}")

    output_path = os.path.join(output_dir, '0422Result.mp4')

    process_video(
        input_path=video_path,
        output_path=output_path,
        mode='obfuscate',
        keep_audio=True,          # 保留并混淆音频
        block_size=16,
        seed=42,
    )

    print(f"\n输出文件: {output_path}")
    print("=" * 60)
    print("CLI execute End !")
    print("=" * 60)

    return output_path


if __name__ == '__main__':
    main()

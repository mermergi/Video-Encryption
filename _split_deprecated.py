"""
注意: 此脚本已被弃用。
新版 obfuscation.py 支持直接从原视频流式读取帧，
不再需要将帧写入磁盘。请使用 openCVImg2VedioScript.py 代替。
"""

import warnings
warnings.warn(
    "此脚本已弃用。openCVImg2VedioScript.py 现已支持直接从原视频流式处理。",
    DeprecationWarning,
    stacklevel=2
)

import cv2
import os
import string
import sys
sys.path.append(os.path.join(os.path.split(os.path.realpath(__file__))[0]+'\\Config'))
from config import global_config

def delFile(path):
    """清空目录下的所有文件"""
    if not os.path.exists(path):
        return
    ls = os.listdir(path)
    for i in ls:
        c_path = os.path.join(path, i)
        if os.path.isdir(c_path):
            delFile(c_path)
            os.rmdir(c_path)
        else:
            os.remove(c_path)

def main():
    """视频分割主函数 - 保持所有帧以维持原始帧率"""
    print("="*60)
    print("openCVVedio2ImgScript execute Start !")
    print("保存所有帧以保持原始帧率")
    print("="*60)
    
    videoPath = global_config.getRaw('config', 'VIDEO_PATH')
    savePath = global_config.getRaw('config', 'SAVE_PATH')
    
    print(f"视频路径: {videoPath}")
    print(f"保存路径: {savePath}")
    
    # 检查视频文件是否存在
    if not os.path.exists(videoPath):
        print(f"错误: 视频文件不存在: {videoPath}")
        raise FileNotFoundError(f"视频文件不存在: {videoPath}")
    
    # 打开视频
    cap = cv2.VideoCapture(videoPath)
    if not cap.isOpened():
        print(f"错误: 无法打开视频文件: {videoPath}")
        raise ValueError(f"无法打开视频文件: {videoPath}")
    
    # 获取视频信息
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    duration = total_frames / fps if fps > 0 else 0
    
    print(f"视频信息: 总帧数={total_frames}, FPS={fps:.2f}, 时长={duration:.2f}s")
    
    if total_frames == 0:
        cap.release()
        raise ValueError("视频没有帧数据")
    
    # 创建保存目录 - 使用绝对路径
    savePath = os.path.abspath(savePath)
    if os.path.exists(savePath):
        print(f"清空已有目录: {savePath}")
        delFile(savePath)
    else:
        print(f"创建目录: {savePath}")
    
    os.makedirs(savePath, exist_ok=True)
    
    # 验证目录创建成功
    if not os.path.exists(savePath):
        raise IOError(f"无法创建目录: {savePath}")
    
    print("-" * 60)
    print(f"开始保存所有帧...")
    
    frame_count = 0
    saved_count = 0
    
    # 保存所有帧
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        
        frame_count += 1
        saved_count += 1
        
        # 保存图片
        img_filename = f"{saved_count}.jpg"
        img_path = os.path.join(savePath, img_filename)
        
        # 保存图片（使用高质量设置）
        success = cv2.imwrite(img_path, frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
        
        if success:
            if saved_count % 100 == 0 or saved_count <= 5:
                print(f"已保存: {img_filename} ({saved_count}帧)")
        else:
            print(f"警告: 保存 {img_filename} 失败")
    
    cap.release()
    
    print("-" * 60)
    print(f"视频分割完成!")
    print(f"共处理 {frame_count} 帧")
    print(f"保存 {saved_count} 张图片")
    print(f"原始帧率: {fps}fps")
    
    # 验证图片是否成功保存
    saved_files = [f for f in os.listdir(savePath) if f.endswith('.jpg')]
    print(f"目录验证: 找到 {len(saved_files)} 个jpg文件")
    
    if len(saved_files) == 0:
        raise RuntimeError("没有成功保存任何图片!")
    
    print("="*60)
    print("openCVVedio2ImgScript execute End !")
    print("="*60)
    
    return saved_count


if __name__ == '__main__':
    main()

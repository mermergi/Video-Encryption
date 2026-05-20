"""
视频混淆与解混淆模块
使用可逆算法：
  - 视频：像素块置换 + 颜色通道交换
  - 音频：时间段置换
"""

import cv2
import numpy as np
import random
import os
import subprocess
import json as _json
import wave
import tempfile
import shutil


# ============================================================
# 视频混淆
# ============================================================

class VideoObfuscator:
    """视频混淆器 —— 块置换 + 通道交换"""

    def __init__(self, block_size=16, seed=42):
        self.block_size = block_size
        self.seed = seed
        self.width = None
        self.height = None
        self.num_blocks_x = None
        self.num_blocks_y = None
        self.permutation = None
        self.inv_permutation = None
        self._rng = random.Random(seed)

    def _generate_permutation(self, num_blocks):
        perm = list(range(num_blocks))
        self._rng.shuffle(perm)
        return perm

    def _generate_inv_permutation(self, permutation):
        inv = [0] * len(permutation)
        for i, p in enumerate(permutation):
            inv[p] = i
        return inv

    def _split_into_blocks(self, frame):
        blocks = []
        for y in range(self.num_blocks_y):
            for x in range(self.num_blocks_x):
                y_start = y * self.block_size
                x_start = x * self.block_size
                y_end = min(y_start + self.block_size, self.height)
                x_end = min(x_start + self.block_size, self.width)
                block = frame[y_start:y_end, x_start:x_end]
                blocks.append(block)
        return blocks

    def _merge_blocks(self, blocks):
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        for i, block in enumerate(blocks):
            y = i // self.num_blocks_x
            x = i % self.num_blocks_x
            y_start = y * self.block_size
            x_start = x * self.block_size
            y_end = min(y_start + self.block_size, self.height)
            x_end = min(x_start + self.block_size, self.width)
            tgt_h = y_end - y_start
            tgt_w = x_end - x_start
            src_h = min(block.shape[0], tgt_h)
            src_w = min(block.shape[1], tgt_w)
            frame[y_start:y_end, x_start:x_end] = 0
            frame[y_start:y_start+src_h, x_start:x_start+src_w] = block[:src_h, :src_w]
        return frame

    @staticmethod
    def _swap_channels(frame):
        """BGR -> BRG"""
        result = np.zeros_like(frame)
        result[:, :, 0] = frame[:, :, 0]
        result[:, :, 1] = frame[:, :, 2]
        result[:, :, 2] = frame[:, :, 1]
        return result

    @staticmethod
    def _restore_channels(frame):
        """BRG -> BGR (与 _swap_channels 相同，对称操作)"""
        result = np.zeros_like(frame)
        result[:, :, 0] = frame[:, :, 0]
        result[:, :, 1] = frame[:, :, 2]
        result[:, :, 2] = frame[:, :, 1]
        return result

    def _auto_adjust_block_size(self, h, w):
        """将 block_size 调整为能同时整除宽高的最大值（保证无损置换）。"""
        bs = min(self.block_size, w, h)
        while bs > 1 and (w % bs != 0 or h % bs != 0):
            bs -= 1
        if bs != self.block_size:
            self.block_size = bs
            self._rng = random.Random(self.seed)

    def obfuscate_frame(self, frame):
        if self.width is None:
            self.height, self.width = frame.shape[:2]
            self._auto_adjust_block_size(self.height, self.width)
            self.num_blocks_x = self.width // self.block_size
            self.num_blocks_y = self.height // self.block_size
            num_blocks = self.num_blocks_x * self.num_blocks_y
            self.permutation = self._generate_permutation(num_blocks)
            self.inv_permutation = self._generate_inv_permutation(self.permutation)

        blocks = self._split_into_blocks(frame)
        permuted = [blocks[i] for i in self.permutation]
        result = self._merge_blocks(permuted)
        result = self._swap_channels(result)
        return result

    def deobfuscate_frame(self, frame):
        if self.inv_permutation is None:
            self.height, self.width = frame.shape[:2]
            self._auto_adjust_block_size(self.height, self.width)
            self.num_blocks_x = self.width // self.block_size
            self.num_blocks_y = self.height // self.block_size
            num_blocks = self.num_blocks_x * self.num_blocks_y
            self.permutation = self._generate_permutation(num_blocks)
            self.inv_permutation = self._generate_inv_permutation(self.permutation)

        result = self._restore_channels(frame)
        blocks = self._split_into_blocks(result)
        restored = [blocks[i] for i in self.inv_permutation]
        result = self._merge_blocks(restored)
        return result


# ============================================================
# 音频混淆
# ============================================================

class AudioObfuscator:
    """音频混淆器 —— 时间段置换（可逆）"""

    def __init__(self, seed=42, segment_duration_ms=50):
        self.seed = seed
        self.segment_duration_ms = segment_duration_ms
        self.permutation = None
        self.inv_permutation = None
        self._rng = random.Random(seed)

    def _generate_permutation(self, num_segments):
        perm = list(range(num_segments))
        self._rng.shuffle(perm)
        return perm

    @staticmethod
    def _generate_inv_permutation(permutation):
        inv = [0] * len(permutation)
        for i, p in enumerate(permutation):
            inv[p] = i
        return inv

    def _split_segments(self, pcm, segment_size):
        segments = []
        for i in range(0, len(pcm), segment_size):
            seg = pcm[i:i + segment_size]
            if len(seg) < segment_size:
                pad = np.zeros(segment_size - len(seg), dtype=pcm.dtype)
                seg = np.concatenate([seg, pad])
            segments.append(seg)
        return segments

    def _init_for_length(self, num_samples, sample_rate):
        seg_size = int(sample_rate * self.segment_duration_ms / 1000)
        num_segments = (num_samples + seg_size - 1) // seg_size
        self.permutation = self._generate_permutation(num_segments)
        self.inv_permutation = self._generate_inv_permutation(self.permutation)

    def obfuscate(self, pcm_data, sample_rate):
        """
        混淆 PCM 音频数据。

        Args:
            pcm_data: np.int16 一维数组
            sample_rate: 采样率 (Hz)

        Returns:
            混淆后的 np.int16 一维数组（长度与输入相同）
        """
        seg_size = int(sample_rate * self.segment_duration_ms / 1000)
        num_segments = (len(pcm_data) + seg_size - 1) // seg_size
        self.permutation = self._generate_permutation(num_segments)
        self.inv_permutation = self._generate_inv_permutation(self.permutation)

        segments = self._split_segments(pcm_data, seg_size)
        permuted = [segments[i] for i in self.permutation]
        result = np.concatenate(permuted)
        return result[:len(pcm_data)]

    def deobfuscate(self, pcm_data, sample_rate):
        """
        解混淆 PCM 音频数据。

        Args:
            pcm_data: np.int16 一维数组
            sample_rate: 采样率 (Hz)

        Returns:
            还原后的 np.int16 一维数组
        """
        if self.inv_permutation is None:
            self._init_for_length(len(pcm_data), sample_rate)

        seg_size = int(sample_rate * self.segment_duration_ms / 1000)
        segments = self._split_segments(pcm_data, seg_size)
        restored = [segments[i] for i in self.inv_permutation]
        result = np.concatenate(restored)
        return result[:len(pcm_data)]


# ============================================================
# ffmpeg 辅助
# ============================================================

FFMPEG_AVAILABLE = None


def _check_ffmpeg():
    global FFMPEG_AVAILABLE
    if FFMPEG_AVAILABLE is not None:
        return FFMPEG_AVAILABLE

    # 尝试从常用路径搜索 ffmpeg
    _common_paths = [
        r'C:\tools\ffmpeg\bin',
        r'C:\ffmpeg\bin',
        r'C:\Program Files\ffmpeg\bin',
    ]
    for p in _common_paths:
        exe = os.path.join(p, 'ffmpeg.exe')
        if os.path.exists(exe):
            os.environ.setdefault('PATH', '')
            os.environ['PATH'] = p + os.pathsep + os.environ['PATH']
            break

    try:
        subprocess.run(['ffmpeg', '-version'],
                       capture_output=True, timeout=10)
        FFMPEG_AVAILABLE = True
    except Exception:
        FFMPEG_AVAILABLE = False
    return FFMPEG_AVAILABLE


def has_audio_stream(video_path):
    """检查视频是否包含音频轨道"""
    if not _check_ffmpeg():
        return False
    try:
        result = subprocess.run(
            ['ffprobe', '-i', video_path, '-show_streams',
             '-select_streams', 'a', '-loglevel', 'error',
             '-print_format', 'json'],
            capture_output=True, text=True, timeout=30
        )
        data = _json.loads(result.stdout)
        return len(data.get('streams', [])) > 0
    except Exception:
        return False


def extract_audio(video_path, output_wav_path):
    """从视频中提取音频为 WAV (PCM 16-bit 44.1kHz)"""
    subprocess.run([
        'ffmpeg', '-i', video_path, '-vn',
        '-acodec', 'pcm_s16le', '-ar', '44100', '-ac', '2',
        '-y', output_wav_path
    ], check=True, capture_output=True, timeout=300)


def read_wav(wav_path):
    """读取 WAV 文件，返回 (pcm: np.int16 一维数组, sample_rate)"""
    with wave.open(wav_path, 'rb') as wf:
        sample_rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
        pcm = np.frombuffer(frames, dtype=np.int16)
    return pcm, sample_rate


def write_wav(wav_path, pcm_data, sample_rate, channels=2):
    """将 PCM 数据写入 WAV 文件"""
    with wave.open(wav_path, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_data.astype(np.int16).tobytes())


# ============================================================
# 统一处理入口
# ============================================================

def process_video(input_path, output_path, mode='obfuscate',
                  fps=None, keep_audio=True, block_size=16, seed=42,
                  progress_callback=None):
    """
    统一视频处理管线（流式帧处理 + 可选音频混淆）。

    Args:
        input_path:  输入视频路径
        output_path: 输出视频路径
        mode:        'obfuscate' 或 'deobfuscate'
        fps:         输出帧率 (None = 保持原始帧率)
        keep_audio:  是否处理音频 (需 ffmpeg)
        block_size:  像素块大小
        seed:        随机种子（保证可逆）
        progress_callback: 可选回调 fn(percent: float, message: str)
    """
    def report(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)
        else:
            print(f"[{pct:.0f}%] {msg}")

    # 1. 打开输入视频
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise ValueError(f"无法打开视频: {input_path}")

    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    output_fps = fps if fps is not None else original_fps

    report(0, f"输入: {width}x{height}, {output_fps:.2f}fps, {total_frames}帧, "
              f"模式={'混淆' if mode == 'obfuscate' else '解混淆'}")

    temp_dir = tempfile.mkdtemp(prefix='vo_')
    try:
        # 2. 音频处理
        has_audio = False
        temp_audio_orig = os.path.join(temp_dir, 'audio_orig.wav')
        temp_audio_proc = os.path.join(temp_dir, 'audio_proc.wav')

        if keep_audio:
            if _check_ffmpeg():
                has_audio = has_audio_stream(input_path)
                if has_audio:
                    report(2, "提取音频...")
                    extract_audio(input_path, temp_audio_orig)

                    pcm_data, sample_rate = read_wav(temp_audio_orig)
                    report(4, f"音频: {sample_rate}Hz, {len(pcm_data)} 采样点")

                    audio_obf = AudioObfuscator(seed=seed)
                    if mode == 'obfuscate':
                        processed = audio_obf.obfuscate(pcm_data, sample_rate)
                    else:
                        processed = audio_obf.deobfuscate(pcm_data, sample_rate)

                    write_wav(temp_audio_proc, processed, sample_rate)
                    report(6, "音频处理完成")
                else:
                    report(2, "视频无音频轨道，跳过音频处理")
            else:
                report(2, "ffmpeg 未安装，跳过音频处理（仅混淆视频画面）")

        # 3. 视频帧编码（ffmpeg pipe → libx264）
        ob = VideoObfuscator(block_size=block_size, seed=seed)
        frame_count = 0

        # 构造 ffmpeg 命令
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{width}x{height}',
            '-pix_fmt', 'bgr24',
            '-r', f'{output_fps:.6f}',
            '-i', '-',                  # 从 stdin 读原始帧
        ]
        if has_audio:
            ffmpeg_cmd += ['-i', temp_audio_proc]
        ffmpeg_cmd += [
            '-c:v', 'libx264',
            '-crf', '23',
            '-preset', 'medium',
            '-pix_fmt', 'yuv420p',
        ]
        if has_audio:
            ffmpeg_cmd += ['-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0']
        ffmpeg_cmd.append(output_path)

        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if mode == 'obfuscate':
                processed = ob.obfuscate_frame(frame)
            else:
                if frame_count == 0:
                    ob.height, ob.width = frame.shape[:2]
                    ob._auto_adjust_block_size(ob.height, ob.width)
                    ob.num_blocks_x = ob.width // ob.block_size
                    ob.num_blocks_y = ob.height // ob.block_size
                    n = ob.num_blocks_x * ob.num_blocks_y
                    ob.permutation = ob._generate_permutation(n)
                    ob.inv_permutation = ob._generate_inv_permutation(ob.permutation)
                processed = ob.deobfuscate_frame(frame)

            proc.stdin.write(processed.tobytes())
            frame_count += 1

            if frame_count % 100 == 0 and total_frames > 0:
                pct = 6 + (frame_count / total_frames) * 88
                report(pct, f"处理视频帧: {frame_count}/{total_frames}")

        cap.release()
        proc.stdin.close()
        proc.wait()
        report(100, f"处理完成！输出: {output_path}")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    return output_path


# ============================================================
# 向后兼容 —— 包装旧接口
# ============================================================

def process_video_obfuscation(input_path, output_path, obfuscate=True, fps=None):
    """旧接口，内部委托给 process_video"""
    mode = 'obfuscate' if obfuscate else 'deobfuscate'
    return process_video(input_path, output_path, mode=mode, fps=fps)


# ============================================================
# 命令行入口
# ============================================================

if __name__ == '__main__':
    print("=" * 60)
    print("VideoObfuscation — 视频混淆工具")
    print("=" * 60)

    test_video = r"d:\video-obfuscation\0422.mp4"
    if os.path.exists(test_video):
        obf_path = test_video.replace('.mp4', '_obfuscated.mp4')
        process_video(test_video, obf_path, mode='obfuscate')

        rest_path = test_video.replace('.mp4', '_restored.mp4')
        process_video(obf_path, rest_path, mode='deobfuscate')

        print("\n" + "=" * 60)
        print("测试完成")
        print(f"原始:    {test_video}")
        print(f"混淆:    {obf_path}")
        print(f"复原:    {rest_path}")
        print("=" * 60)
    else:
        print(f"测试视频不存在: {test_video}")

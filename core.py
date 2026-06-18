"""
视频加密 / 解密模块

v2.0: 文件级 AES-256-CTR 加密，PBKDF2 密钥派生。
旧版帧级混淆类（VideoObfuscator, AudioObfuscator）已弃用。
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
import sys as _sys
import warnings

from crypto_layer import encrypt_file, decrypt_file

# Windows 上隐藏 ffmpeg 控制台窗口
if _sys.platform == 'win32':
    _SUB_FLAGS = {'creationflags': subprocess.CREATE_NO_WINDOW}
else:
    _SUB_FLAGS = {}


# ============================================================
# 视频混淆
# ============================================================

class VideoObfuscator:
    """视频混淆器 —— 块置换 + 通道交换（种子驱动多参数派生）

    已弃用: 请使用 process_video() 的 AES 文件级加密。
    """

    def __init__(self, block_size=16, seed=42):
        warnings.warn(
            "VideoObfuscator is deprecated, use process_video() with password instead.",
            DeprecationWarning, stacklevel=2)
        self.block_size = block_size
        self.seed = seed
        self.width = None
        self.height = None
        self.num_blocks_x = None
        self.num_blocks_y = None
        self.permutation = None
        self.inv_permutation = None
        # 从主种子派生所有加密参数
        self._channel_map = None
        self._channel_inv = None
        self._perm_seed = None
        self._init_derived_params()
        self._rng = random.Random(self._perm_seed)

    def _init_derived_params(self):
        """从主种子派生：块置换种子 + 颜色通道置换方案（6种之一）"""
        rng = random.Random(self.seed)
        self._perm_seed = rng.randint(0, 2**31 - 1)
        # 6 种可能的 BGR 通道置换
        perms = [
            [0, 1, 2],  # BGR -> BGR (恒等)
            [0, 2, 1],  # BGR -> BRG
            [1, 0, 2],  # BGR -> GBR
            [1, 2, 0],  # BGR -> GRB
            [2, 0, 1],  # BGR -> RBG
            [2, 1, 0],  # BGR -> RGB
        ]
        self._channel_map = perms[rng.randint(0, 5)]
        # 计算逆映射（用于解混淆）
        self._channel_inv = [0, 0, 0]
        for i, p in enumerate(self._channel_map):
            self._channel_inv[p] = i

    def _apply_channel_map(self, frame, mapping):
        """对帧应用任意通道置换"""
        result = np.zeros_like(frame)
        for dst, src in enumerate(mapping):
            result[:, :, dst] = frame[:, :, src]
        return result

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

    def _auto_adjust_block_size(self, h, w):
        """将 block_size 调整为能同时整除宽高的最大值（保证无损置换）。"""
        bs = min(self.block_size, w, h)
        while bs > 1 and (w % bs != 0 or h % bs != 0):
            bs -= 1
        if bs != self.block_size:
            self.block_size = bs
            self._rng = random.Random(self._perm_seed)

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
        result = self._apply_channel_map(result, self._channel_map)
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

        result = self._apply_channel_map(frame, self._channel_inv)
        blocks = self._split_into_blocks(result)
        restored = [blocks[i] for i in self.inv_permutation]
        result = self._merge_blocks(restored)
        return result


# ============================================================
# 音频混淆
# ============================================================

class AudioObfuscator:
    """音频混淆器 —— 时间段置换（可逆，种子驱动多参数派生）

    已弃用: 请使用 process_video() 的 AES 文件级加密。
    """

    def __init__(self, seed=42):
        warnings.warn(
            "AudioObfuscator is deprecated, use process_video() with password instead.",
            DeprecationWarning, stacklevel=2)
        self.seed = seed
        # 从主种子派生：置换种子 + 时间段长度 (30-80ms 随机)
        rng = random.Random(seed)
        self._perm_seed = rng.randint(0, 2**31 - 1)
        self.segment_duration_ms = rng.randint(30, 80)
        self.permutation = None
        self.inv_permutation = None
        self._rng = random.Random(self._perm_seed)

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
        """按 segment_size 将 PCM 分段，最后一段不足则补零（保证所有段长度一致）。"""
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
        return result

    def deobfuscate(self, pcm_data, sample_rate, original_length=None):
        """
        解混淆 PCM 音频数据。

        Args:
            pcm_data: np.int16 一维数组
            sample_rate: 采样率 (Hz)
            original_length: 原始音频采样数（用于裁剪因段补齐导致的额外零值）

        Returns:
            还原后的 np.int16 一维数组
        """
        seg_size = int(sample_rate * self.segment_duration_ms / 1000)

        # AAC 编码会将音频补齐到 1024 帧边界，裁剪多余部分使段边界对齐
        effective_len = len(pcm_data)
        if original_length is not None:
            expected_padded = ((original_length + seg_size - 1) // seg_size) * seg_size
            if effective_len > expected_padded:
                pcm_data = pcm_data[:expected_padded]
                effective_len = expected_padded

        if self.inv_permutation is None:
            self._init_for_length(effective_len, sample_rate)

        segments = self._split_segments(pcm_data, seg_size)
        restored = [segments[i] for i in self.inv_permutation]
        result = np.concatenate(restored)
        if original_length is not None:
            result = result[:original_length]
        return result


# ============================================================
# ffmpeg 辅助
# ============================================================

FFMPEG_AVAILABLE = None
FFMPEG_PATH = None


def set_ffmpeg_path(path):
    """设置 ffmpeg 可执行文件路径（用于打包后的应用）"""
    global FFMPEG_PATH, FFMPEG_AVAILABLE
    if path and os.path.isfile(path):
        FFMPEG_PATH = path
        d = os.path.dirname(path)
        if d not in os.environ.get('PATH', ''):
            os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')
    FFMPEG_AVAILABLE = None  # 强制重新检测


def _check_ffmpeg():
    global FFMPEG_AVAILABLE
    if FFMPEG_AVAILABLE is not None:
        return FFMPEG_AVAILABLE

    # 优先使用显式设置的路径
    if FFMPEG_PATH and os.path.isfile(FFMPEG_PATH):
        FFMPEG_AVAILABLE = True
        return True

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
                       capture_output=True, timeout=10, **_SUB_FLAGS)
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
            capture_output=True, text=True, timeout=30, **_SUB_FLAGS
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
    ], check=True, capture_output=True, timeout=300, **_SUB_FLAGS)


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
# 统一处理入口 (v2.0 — AES 文件级加密)
# ============================================================

def _mode_compat(mode):
    """将旧模式名映射到新模式名。"""
    if mode in ('obfuscate', 'encrypt', 'obfuscate_no_audio'):
        return 'encrypt'
    if mode in ('deobfuscate', 'decrypt', 'deobfuscate_no_audio'):
        return 'decrypt'
    return mode


def _ffmpeg_encode(input_path, output_path, progress_callback=None):
    """用 ffmpeg 将输入视频转码为 H.264/AAC 的 MP4。

    进度回调: 0%–100% 对应编码进度。
    """
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video: {input_path}")

    original_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    def report(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    report(0, f"Input: {width}x{height}, {original_fps:.2f}fps, {total_frames} frames")

    temp_dir = tempfile.mkdtemp(prefix='ve_')
    try:
        # Extract audio if present
        has_audio = False
        temp_audio = os.path.join(temp_dir, 'audio.wav')

        if _check_ffmpeg() and has_audio_stream(input_path):
            report(2, "Extracting audio...")
            extract_audio(input_path, temp_audio)
            has_audio = True
        else:
            report(2, "No audio track or ffmpeg not available")

        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-s', f'{width}x{height}',
            '-pix_fmt', 'bgr24',
            '-r', f'{original_fps:.6f}',
            '-i', '-',
        ]
        if has_audio:
            ffmpeg_cmd += ['-i', temp_audio]
        ffmpeg_cmd += [
            '-c:v', 'libx264', '-crf', '23', '-preset', 'medium',
            '-pix_fmt', 'yuv420p',
        ]
        if has_audio:
            ffmpeg_cmd += ['-c:a', 'aac', '-b:a', '128k',
                           '-map', '0:v:0', '-map', '1:a:0']
        ffmpeg_cmd.append(output_path)

        proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE, **_SUB_FLAGS)

        frame_count = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            proc.stdin.write(frame.tobytes())
            frame_count += 1
            if frame_count % 100 == 0 and total_frames > 0:
                pct = 5 + (frame_count / total_frames) * 70
                report(pct, f"Encoding: {frame_count}/{total_frames}")

        cap.release()
        proc.stdin.close()
        proc.wait()

        if proc.returncode != 0:
            raise subprocess.CalledProcessError(proc.returncode, ffmpeg_cmd)

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def process_video(input_path, output_path, mode='encrypt',
                  password=None, progress_callback=None,
                  **kwargs):
    """统一视频处理管线 (v2.0)。

    Args:
        input_path:  输入视频路径
        output_path: 输出路径
        mode:        'encrypt' 或 'decrypt'
        password:    加密 / 解密密码
        progress_callback: 可选回调 fn(percent: float, message: str)
        **kwargs:    忽略旧参数 (seed, fps, keep_audio, block_size, original_audio_len)

    Returns:
        dict: { 'output_path': str, 'mode': str }
    """
    mode = _mode_compat(mode)

    def report(pct, msg):
        if progress_callback:
            progress_callback(pct, msg)

    if not password:
        raise ValueError("Password is required")

    temp_dir = tempfile.mkdtemp(prefix='vec_')
    try:
        if mode == 'encrypt':
            # 1. ffmpeg 编码 (0%–80%)
            temp_video = os.path.join(temp_dir, 'normalized.mp4')
            def encode_cb(pct, msg):
                report(pct * 0.80, msg)
            _ffmpeg_encode(input_path, temp_video, progress_callback=encode_cb)

            # 2. AES 加密 (80%–100%)
            report(80, "Encrypting file...")
            def encrypt_cb(pct):
                report(80 + pct * 0.20, f"Encrypting: {pct:.0f}%")
            encrypt_file(temp_video, output_path, password,
                        progress_callback=encrypt_cb)

        else:  # decrypt
            # 1. AES 解密 (0%–80%)
            temp_decrypted = os.path.join(temp_dir, 'decrypted.mp4')
            report(0, "Decrypting file...")
            def decrypt_cb(pct):
                report(pct * 0.80, f"Decrypting: {pct:.0f}%")
            decrypt_file(input_path, temp_decrypted, password,
                        progress_callback=decrypt_cb)

            # 2. 复制到输出 (80%–100%)
            report(80, "Writing output...")
            import shutil as _shutil
            _shutil.copy2(temp_decrypted, output_path)
            report(100, "Done!")

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)

    report(100, f"Complete! Output: {output_path}")
    return {
        'output_path': output_path,
        'mode': mode,
    }


# ============================================================
# 向后兼容
# ============================================================

def process_video_obfuscation(input_path, output_path, obfuscate=True, fps=None):
    """旧接口，已弃用。请使用 process_video() 并传入 password。"""
    warnings.warn(
        "process_video_obfuscation is deprecated, use process_video() with password instead.",
        DeprecationWarning, stacklevel=2)
    mode = 'encrypt' if obfuscate else 'decrypt'
    return process_video(input_path, output_path, mode=mode,
                         password='deprecated')


# ============================================================
# 命令行入口
# ============================================================

if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Video Encryption Tool v2.0')
    parser.add_argument('input', help='Input video file')
    parser.add_argument('output', help='Output file')
    parser.add_argument('--password', '-p', required=True, help='Encryption password')
    parser.add_argument('--decrypt', '-d', action='store_true',
                        help='Decrypt mode (default: encrypt)')
    args = parser.parse_args()

    mode = 'decrypt' if args.decrypt else 'encrypt'
    result = process_video(args.input, args.output, mode=mode,
                          password=args.password,
                          progress_callback=lambda p, m: print(f"[{p:.0f}%] {m}"))
    print(f"\nDone. Output: {result['output_path']}")

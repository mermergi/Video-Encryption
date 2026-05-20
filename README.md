# VideoObfuscation

一款可逆的视频混淆工具，通过对视频画面和音频进行像素级置换，使机器内容识别系统难以分析，同时保留人类可观看性。使用同一随机种子即可完全还原原始内容。

## 原理

### 视频

1. **块置换**：将每帧分割为 N×N 像素块，用确定性随机种子打乱顺序
2. **颜色通道交换**：BGR → BRG，进一步扰乱画面
3. **尺寸自适应**：自动选择能整除宽高的最大 block_size（如 1080p 用 15×15），保证置换无损
4. **解混淆**：逆置换 + 通道还原，完全恢复原始帧

### 音频

1. **时间段置换**：将 PCM 音频切分为 50ms 时间段，用同一种子打乱
2. **解混淆**：逆置换恢复原始时间序

## 特性

- **完全可逆**：同一种子即可无损还原视频画面及音频
- **音频保留**：音频轨道经过可逆混淆后重新合成到输出视频
- **流式处理**：逐帧读取 → 内存混淆 → pipe 编码，零中间文件
- **H.264 编码**：通过 ffmpeg pipe 以 libx264 编码输出，相比 OpenCV 软编码缩小 10-20 倍体积
- **尺寸自适应**：自动选择最优 block_size，避免边缘像素丢失

## 依赖

- Python 3.8+
- ffmpeg（用于视频编码和音频处理）
- opencv-python、numpy、flask、pillow

安装：

```
pip install opencv-python numpy flask pillow
```

ffmpeg 下载：[https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)

## 使用

### 命令行

修改 `Config/config.ini`：

```ini
[config]
VIDEO_PATH=D:/input.mp4
IMG_VIDEO_PATH=D:/output/
```

运行：

```
py cli.py
```

### Web 界面

```
py web/app.py
```

浏览器打开 `http://localhost:5000`，上传视频后选择混淆或解混淆。

### API

```python
from core import process_video

# 混淆
process_video("input.mp4", "output_obfuscated.mp4", mode="obfuscate")

# 还原
process_video("obfuscated.mp4", "restored.mp4", mode="deobfuscate")
```

## 项目结构

```
VideoObfuscation/
├── core.py                      # 核心：VideoObfuscator + AudioObfuscator + 统一管线
├── cli.py                       # 命令行入口
├── _split_deprecated.py         # （已弃用）
├── Config/
│   ├── config.ini               # 配置文件
│   └── config.py                # 配置解析器
├── web/
│   └── app.py                   # Flask Web 应用
├── templates/
│   └── index.html               # Web 前端
├── uploads/                     # 上传目录
└── output/                      # 输出目录
```

## 兼容性

| 分辨率 | block_size | 无损 |
|--------|-----------|------|
| 640×480 | 16 | ✓ |
| 1280×720 | 16 | ✓ |
| 1920×1080 | 15 | ✓ |
| 1920×1088 | 16 | ✓ |
| 3840×2160 | 16 | ✓ |

## License

GPL-3.0

# VideoObfuscation

A reversible video obfuscation tool that scrambles video frames and audio through pixel/segment permutation, making machine analysis ineffective while keeping the content human-viewable. The original content can be fully restored using the same random seed.

## How It Works

### Video

1. **Block permutation**: Split each frame into N×N pixel blocks, shuffle them with a deterministic random seed
2. **Color channel swap**: BGR → BRG, further disrupts the image
3. **Adaptive block size**: Automatically picks the largest block size that evenly divides both dimensions (e.g., 15×15 for 1080p), ensuring lossless roundtrip
4. **Deobfuscation**: Inverse permutation + channel restore recovers the original frame exactly

### Audio

1. **Segment permutation**: Split PCM audio into 50ms time segments, shuffle with the same seed
2. **Deobfuscation**: Inverse permutation restores the original timing

## Features

- **Fully reversible**: Same seed restores both video and audio losslessly
- **Audio preservation**: Audio track is obfuscated and remuxed into the output
- **Streaming pipeline**: Read → obfuscate → encode in memory, zero intermediate files
- **H.264 encoding**: ffmpeg pipe with libx264, 10-20x smaller than OpenCV software encoding
- **Adaptive block size**: Auto-selects optimal block size, no edge artifacts

## Dependencies

- Python 3.8+
- ffmpeg (video encoding + audio processing)
- opencv-python, numpy, flask, pillow

```
pip install opencv-python numpy flask pillow
```

Download ffmpeg: [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)

## Usage

### CLI

Edit `Config/config.ini`:

```ini
[config]
VIDEO_PATH=D:/input.mp4
IMG_VIDEO_PATH=D:/output/
```

Run:

```
py cli.py
```

### Web UI

```
py web/app.py
```

Open `http://localhost:5000` in your browser.

### API

```python
from core import process_video

# Obfuscate
process_video("input.mp4", "output_obfuscated.mp4", mode="obfuscate")

# Restore
process_video("obfuscated.mp4", "restored.mp4", mode="deobfuscate")
```

## Project Structure

```
VideoObfuscation/
├── core.py                      # Core: VideoObfuscator + AudioObfuscator + pipeline
├── cli.py                       # CLI entry point
├── _split_deprecated.py         # (deprecated)
├── Config/
│   ├── config.ini               # Config file
│   └── config.py                # Config parser
├── web/
│   └── app.py                   # Flask web app
├── templates/
│   └── index.html               # Web frontend
├── uploads/                     # Upload directory
└── output/                      # Output directory
```

## Compatibility

| Resolution | Block size | Lossless |
|------------|-----------|----------|
| 640×480 | 16 | ✓ |
| 1280×720 | 16 | ✓ |
| 1920×1080 | 15 | ✓ |
| 1920×1088 | 16 | ✓ |
| 3840×2160 | 16 | ✓ |

## License

GPL-3.0

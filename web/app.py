import os
import sys
import threading
from flask import Flask, render_template, request, jsonify, send_file
from werkzeug.utils import secure_filename

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(project_root)

app = Flask(__name__,
    template_folder=os.path.join(project_root, 'templates'),
    static_folder=os.path.join(project_root, 'static')
)

# 配置
UPLOAD_FOLDER = os.path.join(project_root, 'uploads')
OUTPUT_FOLDER = os.path.join(project_root, 'output')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB

# 全局进度存储
progress_data = {
    'status': 'idle',
    'current_step': '',
    'progress': 0,
    'message': 'Ready...',
    'output_file': None,
}


def update_progress(status, step, progress, message, output_file=None):
    progress_data['status'] = status
    progress_data['current_step'] = step
    progress_data['progress'] = progress
    progress_data['message'] = message
    if output_file is not None:
        progress_data['output_file'] = output_file


def _progress_callback(percent, message):
    if percent < 80:
        step = 'processing'
    else:
        step = 'encrypt'
    update_progress('processing', step, percent, message)


def process_video_task(file_path, mode='encrypt', password=None):
    """在后台线程中处理视频"""
    try:
        import warnings
        warnings.filterwarnings('ignore', category=DeprecationWarning)
        from core import process_video

        file_dir = os.path.dirname(file_path)
        basename = os.path.splitext(os.path.basename(file_path))[0]

        if mode == 'encrypt':
            output_name = f"{basename}_encrypted.ve2"
        else:
            output_name = f"{basename}_decrypted.mp4"

        output_path = os.path.join(OUTPUT_FOLDER, output_name)

        update_progress('processing', 'start', 0,
                        f"Starting {mode}...")

        result = process_video(
            input_path=file_path,
            output_path=output_path,
            mode=mode,
            password=password,
            progress_callback=_progress_callback,
        )

        update_progress('completed', 'done', 100,
                        "Done!",
                        output_file=output_path)

    except Exception as e:
        import traceback
        traceback.print_exc()
        update_progress('error', 'error', 0, f'Error: {str(e)}')


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload():
    if 'file' not in request.files:
        return jsonify({'success': False, 'message': 'No file selected'})

    file = request.files['file']
    if file.filename == '':
        return jsonify({'success': False, 'message': 'Empty filename'})

    if file:
        filename = secure_filename(file.filename)
        import time
        timestamp = str(int(time.time()))
        save_name = f"{timestamp}_{filename}"
        save_path = os.path.join(UPLOAD_FOLDER, save_name)
        file.save(save_path)

        return jsonify({
            'success': True,
            'message': 'Upload successful',
            'file_path': save_path,
            'file_name': filename
        })


@app.route('/api/process', methods=['POST'])
def process():
    data = request.get_json()
    file_path = data.get('file_path')
    password = data.get('password')
    mode = data.get('mode', 'encrypt')

    if not file_path or not os.path.exists(file_path):
        return jsonify({'success': False, 'message': 'File not found'})
    if not password:
        return jsonify({'success': False, 'message': 'Password required'})

    update_progress('processing', 'start', 0, f'Starting {mode}...')
    thread = threading.Thread(target=process_video_task,
                              args=(file_path, mode, password))
    thread.daemon = True
    thread.start()

    return jsonify({'success': True, 'message': f'Started {mode}'})


@app.route('/api/progress', methods=['GET'])
def progress():
    return jsonify(progress_data)


@app.route('/api/download', methods=['GET'])
def download():
    output_file = progress_data.get('output_file')
    if output_file and os.path.exists(output_file):
        filename = os.path.basename(output_file)
        return send_file(output_file, as_attachment=True,
                         download_name=filename)

    # fallback: 扫描 output 目录
    for root, dirs, files in os.walk(OUTPUT_FOLDER):
        for f in files:
            if f.endswith(('.mp4', '.avi', '.ve2')):
                return send_file(os.path.join(root, f),
                                 as_attachment=True, download_name=f)

    return jsonify({'success': False, 'message': 'File not found'})


if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    app.run(host='0.0.0.0', port=5000, debug=True)

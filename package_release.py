"""一键发布脚本 — 构建 exe、打包 zip、创建 GitHub Release"""
import os
import sys
import json
import zipfile
import hashlib
import subprocess
import shutil
import urllib.request
import urllib.error

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DIST_DIR = os.path.join(PROJECT_DIR, 'dist')
EXE_NAME = 'VideoEncryptTool.exe'
README_NAME = 'README.txt'
VERSION_FILE = os.path.join(PROJECT_DIR, 'version.txt')
SPEC_FILE = os.path.join(PROJECT_DIR, 'VideoEncryptTool.spec')
REPO = 'mermergi/Video-Encryption'


def get_version():
    if os.path.isfile(VERSION_FILE):
        with open(VERSION_FILE, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if content:
                return content
    return '0.0.0'


def save_version(ver):
    with open(VERSION_FILE, 'w', encoding='utf-8') as f:
        f.write(ver)


def bump_version(ver, level):
    parts = ver.split('.')
    if len(parts) != 3:
        parts = ['0', '0', '0']
    major, minor, patch = int(parts[0]), int(parts[1]), int(parts[2])
    if level == 'major':
        major += 1; minor = 0; patch = 0
    elif level == 'minor':
        minor += 1; patch = 0
    else:  # patch
        patch += 1
    return f'{major}.{minor}.{patch}'


def get_token():
    token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
    if token:
        return token
    try:
        r = subprocess.run(
            ['git', 'credential-manager', 'get'],
            input='protocol=https\nhost=github.com\n',
            capture_output=True, text=True, timeout=10
        )
        for line in r.stdout.splitlines():
            if line.startswith('password='):
                return line.split('=', 1)[1]
    except Exception:
        pass
    print('未找到 GitHub token，请设置 GITHUB_TOKEN 环境变量')
    sys.exit(1)


def api_request(method, url, token, data=None, json_data=None):
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json',
    }
    if json_data:
        data = json.dumps(json_data).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(f'API 错误 ({e.code}): {body}')
        return None


def upload_asset(upload_url, filepath, filename, token):
    """自定义上传以支持大文件流式上传"""
    url = upload_url.replace('{?name,label}', f'?name={filename}')
    headers = {
        'Authorization': f'token {token}',
        'Content-Type': 'application/zip',
    }
    with open(filepath, 'rb') as f:
        data = f.read()
    req = urllib.request.Request(url, data=data, headers=headers, method='POST')
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')
        print(f'上传失败 ({e.code}): {body}')
        return None


def build_exe():
    print('🔨 构建 exe...')
    r = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', '--clean', SPEC_FILE],
        cwd=PROJECT_DIR
    )
    if r.returncode != 0:
        print('PyInstaller 构建失败')
        sys.exit(1)
    print('构建完成\n')


def sha256_file(filepath):
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            h.update(chunk)
    return h.hexdigest()


def create_zip(version):
    exe = os.path.join(DIST_DIR, EXE_NAME)
    readme = os.path.join(DIST_DIR, README_NAME)
    zip_name = f'VideoEncryptTool_v{version}.zip'
    zip_path = os.path.join(PROJECT_DIR, zip_name)

    if not os.path.isfile(exe):
        print(f'错误: 未找到 {exe}')
        sys.exit(1)

    print(f'📦 打包 {zip_name} ...')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(exe, EXE_NAME)
        if os.path.isfile(readme):
            zf.write(readme, README_NAME)

    sha = sha256_file(zip_path)
    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f'完成: {zip_name} ({size_mb:.1f} MB)')
    print(f'SHA256: {sha}\n')
    return zip_path, sha


def git_commit_and_tag(version):
    print('📋 Git 操作...')
    subprocess.run(['git', 'add', 'version.txt', VERSION_FILE], cwd=PROJECT_DIR)
    subprocess.run(['git', 'commit', '-m', f'v{version}'], cwd=PROJECT_DIR)
    subprocess.run(['git', 'push'], cwd=PROJECT_DIR)

    tag = f'v{version}'
    r = subprocess.run(['git', 'tag', '-l', tag], cwd=PROJECT_DIR, capture_output=True, text=True)
    if r.stdout.strip():
        print(f'Tag {tag} 已存在，跳过创建')
    else:
        subprocess.run(['git', 'tag', '-a', tag, '-m', f'v{version}'], cwd=PROJECT_DIR)
        subprocess.run(['git', 'push', 'origin', tag], cwd=PROJECT_DIR)
        print(f'Tag {tag} 已推送')
    print()


def create_github_release(version, sha, zip_path, token):
    zip_name = os.path.basename(zip_path)

    body = (
        f"## v{version}\n\n"
        "Video Encryption Tool — seed-based video obfuscation.\n\n"
        "### Features\n"
        "- Frame + Audio dual encryption with unique per-seed parameters\n"
        "- Embedded VLC player for encrypted video preview\n"
        "- Chinese / English UI\n"
        "- Bundled ffmpeg (zero dependencies)\n"
        "- MP4 / AVI / MKV / MOV output formats\n\n"
        "### SHA256\n```\n" + sha + "\n```"
    )

    release_data = {
        'tag_name': f'v{version}',
        'name': f'v{version} - Video Encryption Tool',
        'body': body,
        'draft': False,
        'prerelease': False,
    }

    print('🚀 创建 GitHub Release...')
    result = api_request(
        'POST',
        f'https://api.github.com/repos/{REPO}/releases',
        token,
        json_data=release_data
    )
    if not result:
        print('Release 创建失败')
        return

    upload_url = result.get('upload_url')
    if not upload_url:
        print('未获取到 upload_url')
        return

    print(f'📤 上传 {zip_name} ({os.path.getsize(zip_path) / 1024 / 1024:.0f}MB)...')
    asset = upload_asset(upload_url, zip_path, zip_name, token)
    if asset:
        print(f'上传成功: {asset["browser_download_url"]}')
    print()


def main():
    version = get_version()
    print(f'当前版本: {version}')

    bump = None
    if len(sys.argv) > 1:
        bump = sys.argv[1]
        if bump not in ('major', 'minor', 'patch'):
            print('用法: python package_release.py [major|minor|patch]')
            print('  major — x.0.0')
            print('  minor — 0.x.0')
            print('  patch — 0.0.x (默认)')
            sys.exit(1)
    else:
        bump = 'patch'

    new_version = bump_version(version, bump)
    print(f'新版本: {new_version}')

    token = get_token()

    save_version(new_version)
    build_exe()
    zip_path, sha = create_zip(new_version)
    git_commit_and_tag(new_version)
    create_github_release(new_version, sha, zip_path, token)

    print('✅ 全部完成！')
    print(f'Release: https://github.com/{REPO}/releases/tag/v{new_version}')


if __name__ == '__main__':
    main()

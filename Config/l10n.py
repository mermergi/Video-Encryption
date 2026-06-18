"""多语言支持模块"""
import json
import os
import sys


class LanguageManager:
    """管理翻译字符串的加载、查找和语言切换"""

    def __init__(self, default_lang='zh_CN'):
        self.default_lang = default_lang
        self.current_lang = default_lang
        self.strings = {}
        self.available = {}

        self._scan_available()
        self._load_pref()
        self.load_language(self.current_lang)

    def _get_locales_dir(self):
        """获取语言文件目录，兼容开发和 PyInstaller 环境"""
        if getattr(sys, 'frozen', False):
            return os.path.join(sys._MEIPASS, 'Config', 'locales')
        return os.path.join(os.path.dirname(os.path.abspath(__file__)), 'locales')

    def _get_prefs_path(self):
        """获取偏好文件路径"""
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        prefs_dir = os.path.join(appdata, 'VideoEncryptTool')
        os.makedirs(prefs_dir, exist_ok=True)
        return os.path.join(prefs_dir, 'prefs.json')

    def _scan_available(self):
        """扫描 locales 目录，发现所有可用语言"""
        try:
            d = self._get_locales_dir()
            if not os.path.isdir(d):
                return
            for fn in os.listdir(d):
                if fn.endswith('.json'):
                    code = fn[:-5]  # 去掉 .json
                    try:
                        with open(os.path.join(d, fn), 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            name = data.get('_language_name', code)
                            self.available[code] = name
                    except (json.JSONDecodeError, IOError):
                        pass
        except Exception:
            pass

    def load_language(self, lang_code):
        """加载指定语言文件；失败则回退到默认语言"""
        path = os.path.join(self._get_locales_dir(), f'{lang_code}.json')
        try:
            with open(path, 'r', encoding='utf-8') as f:
                self.strings = json.load(f)
                self.current_lang = lang_code
        except (json.JSONDecodeError, IOError):
            # 回退到默认语言
            if lang_code != self.default_lang:
                self.load_language(self.default_lang)

    def tr(self, key, **kwargs):
        """翻译查找；缺失键返回 !KEY! 标记；支持 str.format(**kwargs)"""
        value = self.strings.get(key)
        if value is None:
            return f'!{key}!'
        if kwargs:
            try:
                return value.format(**kwargs)
            except (KeyError, ValueError):
                return value
        return value

    def get_available(self):
        """返回 {code: display_name}"""
        return dict(self.available)

    def get_current_code(self):
        return self.current_lang

    def save_pref(self):
        """将当前语言偏好保存到 %APPDATA%/VideoEncryptTool/prefs.json"""
        try:
            path = self._get_prefs_path()
            with open(path, 'w', encoding='utf-8') as f:
                json.dump({'language': self.current_lang}, f)
        except Exception:
            pass

    def _load_pref(self):
        """从偏好文件加载语言偏好"""
        try:
            path = self._get_prefs_path()
            if os.path.isfile(path):
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    lang = data.get('language')
                    if lang and lang in self.available:
                        self.current_lang = lang
        except (json.JSONDecodeError, IOError):
            pass

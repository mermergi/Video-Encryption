"""
Video Encryption Tool — 桌面版图形界面
"""
import os
import sys
import subprocess
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from core import process_video, set_ffmpeg_path, _check_ffmpeg
from Config.l10n import LanguageManager


class VideoEncryptApp:
    def __init__(self, root):
        self.root = root
        self.lang = LanguageManager()

        self.root.title(self.lang.tr("app.title"))
        self.root.geometry("720x620+300+300")
        self.root.minsize(600, 520)
        self.root.resizable(True, True)

        self.mode = tk.StringVar(value='encrypt')
        self.input_path = tk.StringVar()
        self.output_path = tk.StringVar()
        self.password_var = tk.StringVar()
        self.password_visible = False
        self.keep_audio = tk.BooleanVar(value=True)
        self.output_format = tk.StringVar(value='mp4')
        self.ffmpeg_path_var = tk.StringVar()
        self.vlc_path_var = tk.StringVar()

        self.is_running = False
        self._player_initialized = False

        self._detect_ffmpeg()
        self._build_ui()
        self._center_window()
        self._apply_language()

        self.root.protocol('WM_DELETE_WINDOW', self._on_close)

    def _detect_ffmpeg(self):
        if getattr(sys, 'frozen', False):
            candidates = [
                os.path.join(sys._MEIPASS, 'ffmpeg', 'ffmpeg.exe'),
            ]
        else:
            candidates = [
                os.path.join(_project_root, 'ffmpeg', 'ffmpeg.exe'),
                os.path.join(_project_root, 'ffmpeg.exe'),
            ]

        for c in candidates:
            if os.path.isfile(c):
                self.ffmpeg_path_var.set(c)
                set_ffmpeg_path(c)
                return

        import shutil
        if shutil.which('ffmpeg'):
            self.ffmpeg_path_var.set('ffmpeg')
            return

        self.ffmpeg_path_var.set('')

    # ── UI Construction ───────────────────────────────────────

    def _build_ui(self):
        main = ttk.Frame(self.root, padding=15)
        main.pack(fill=tk.BOTH, expand=True)

        self._title_label = ttk.Label(main, font=('Segoe UI', 16, 'bold'))
        self._title_label.pack(anchor='w')
        ttk.Separator(main, orient='horizontal').pack(fill=tk.X, pady=(5, 10))

        self._notebook = ttk.Notebook(main)
        self._notebook.pack(fill=tk.BOTH, expand=True)

        self._build_main_tab(self._notebook)
        self._build_player_tab(self._notebook)
        self._build_settings_tab(self._notebook)

    # ── Main tab (Encrypt/Decrypt) ────────────────────────────

    def _build_main_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text="")

        # Mode selection
        self._mode_frame = ttk.LabelFrame(tab, padding=10)
        self._mode_frame.pack(fill=tk.X)
        mode_row = ttk.Frame(self._mode_frame)
        mode_row.pack()
        self._radio_encrypt = ttk.Radiobutton(mode_row,
            variable=self.mode, value='encrypt', command=self._on_mode_change)
        self._radio_encrypt.pack(side=tk.LEFT, padx=10)
        self._radio_decrypt = ttk.Radiobutton(mode_row,
            variable=self.mode, value='decrypt', command=self._on_mode_change)
        self._radio_decrypt.pack(side=tk.LEFT, padx=10)

        # File selection
        self._file_frame = ttk.LabelFrame(tab, padding=10)
        self._file_frame.pack(fill=tk.X, pady=(10, 0))
        self._lbl_input, _, self._btn_browse_in = self._add_file_row(
            self._file_frame, self.input_path, self._browse_input, 0)
        self._lbl_output, _, self._btn_browse_out = self._add_file_row(
            self._file_frame, self.output_path, self._browse_output, 1)

        # Password
        self._password_frame = ttk.LabelFrame(tab, padding=10)
        self._password_frame.pack(fill=tk.X, pady=(10, 0))
        self._password_info_label = ttk.Label(self._password_frame, foreground='#666')
        self._password_info_label.pack(anchor='w')
        pw_row = ttk.Frame(self._password_frame)
        pw_row.pack(fill=tk.X, pady=(5, 0))
        self.password_entry = ttk.Entry(pw_row, textvariable=self.password_var,
                                        font=('Consolas', 11), show='*')
        self.password_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.toggle_pw_btn = ttk.Button(pw_row, command=self._toggle_password_show)
        self.toggle_pw_btn.pack(side=tk.LEFT, padx=(5, 0))

        # Progress
        self._progress_frame = ttk.LabelFrame(tab, padding=10)
        self._progress_frame.pack(fill=tk.X, pady=(10, 0))
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(self._progress_frame, maximum=100,
                                            variable=self.progress_var)
        self.progress_bar.pack(fill=tk.X)
        self.status_var = tk.StringVar(value="")
        self.status_label = ttk.Label(self._progress_frame,
                                       textvariable=self.status_var,
                                       foreground='#666')
        self.status_label.pack(anchor='w', pady=(5, 0))

        # Button
        btn_row = ttk.Frame(tab)
        btn_row.pack(fill=tk.X, pady=(15, 0))
        self.process_btn = ttk.Button(btn_row, command=self._on_process)
        self.process_btn.pack(side=tk.RIGHT)

    # ── Settings tab ──────────────────────────────────────────

    def _build_settings_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=10)
        notebook.add(tab, text="")

        # Language switcher (at top so it's always visible)
        self._lang_frame = ttk.LabelFrame(tab, padding=10)
        self._lang_frame.pack(fill=tk.X)
        lang_row = ttk.Frame(self._lang_frame)
        lang_row.pack(fill=tk.X)
        available = self.lang.get_available()
        self._lang_codes = list(available.keys())
        self._lang_names = list(available.values())
        self._lang_combo = ttk.Combobox(lang_row, values=self._lang_names,
                                         state='readonly', width=14)
        current_code = self.lang.get_current_code()
        if current_code in available:
            self._lang_combo.set(available[current_code])
        self._lang_combo.pack(side=tk.LEFT)
        self._lang_combo.bind('<<ComboboxSelected>>', self._on_language_change)

        # ffmpeg path
        self._ff_frame = ttk.LabelFrame(tab, padding=10)
        self._ff_frame.pack(fill=tk.X, pady=(10, 0))
        ff_row = ttk.Frame(self._ff_frame)
        ff_row.pack(fill=tk.X)
        self.ffmpeg_entry = ttk.Entry(ff_row, textvariable=self.ffmpeg_path_var)
        self.ffmpeg_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self._btn_browse_ff = ttk.Button(ff_row, command=self._browse_ffmpeg)
        self._btn_browse_ff.pack(side=tk.RIGHT)
        self._ff_hint = ttk.Label(self._ff_frame, foreground='#666')
        self._ff_hint.pack(anchor='w', pady=(5, 0))
        self._btn_ff_apply = ttk.Button(self._ff_frame, command=self._apply_ffmpeg_path)
        self._btn_ff_apply.pack(anchor='w', pady=(5, 0))

        # VLC path
        self._vlc_frame = ttk.LabelFrame(tab, padding=10)
        self._vlc_frame.pack(fill=tk.X, pady=(10, 0))
        vlc_row = ttk.Frame(self._vlc_frame)
        vlc_row.pack(fill=tk.X)
        self.vlc_entry = ttk.Entry(vlc_row, textvariable=self.vlc_path_var)
        self.vlc_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        self._btn_browse_vlc = ttk.Button(vlc_row, command=self._browse_vlc)
        self._btn_browse_vlc.pack(side=tk.RIGHT)
        self._vlc_hint = ttk.Label(self._vlc_frame, foreground='#666')
        self._vlc_hint.pack(anchor='w', pady=(5, 0))
        self._btn_vlc_apply = ttk.Button(self._vlc_frame, command=self._apply_vlc_path)
        self._btn_vlc_apply.pack(anchor='w', pady=(5, 0))
        self._vlc_status_label = ttk.Label(self._vlc_frame)
        self._vlc_status_label.pack(anchor='w', pady=(2, 0))

        # Audio options
        self._audio_frame = ttk.LabelFrame(tab, padding=10)
        self._audio_frame.pack(fill=tk.X, pady=(10, 0))
        self._audio_check = ttk.Checkbutton(self._audio_frame,
                                             variable=self.keep_audio)
        self._audio_check.pack(anchor='w')
        self._audio_hint = ttk.Label(self._audio_frame, foreground='#666')
        self._audio_hint.pack(anchor='w', pady=(2, 0))

        # Output format
        self._fmt_frame = ttk.LabelFrame(tab, padding=10)
        self._fmt_frame.pack(fill=tk.X, pady=(10, 0))
        fmt_row = ttk.Frame(self._fmt_frame)
        fmt_row.pack(fill=tk.X)
        self._fmt_label = ttk.Label(fmt_row)
        self._fmt_label.pack(side=tk.LEFT)
        self._format_combo = ttk.Combobox(fmt_row, textvariable=self.output_format,
                                           values=['mp4', 'avi', 'mkv', 'mov'],
                                           state='readonly', width=8)
        self._format_combo.pack(side=tk.LEFT, padx=(5, 0))
        self._fmt_hint = ttk.Label(self._fmt_frame, foreground='#666')
        self._fmt_hint.pack(anchor='w', pady=(5, 0))
        self.output_format.trace_add('write', self._on_format_change)


    # ── Player tab ────────────────────────────────────────────

    @staticmethod
    def _search_vlc():
        common = [
            r'C:\Program Files\VideoLAN\VLC\vlc.exe',
            r'C:\Program Files (x86)\VideoLAN\VLC\vlc.exe',
            os.path.expanduser(r'~\AppData\Local\Programs\VideoLAN\VLC\vlc.exe'),
        ]
        for f in common:
            if os.path.isfile(f):
                return f
        import shutil
        return shutil.which('vlc')

    def _build_player_tab(self, notebook):
        tab = ttk.Frame(notebook, padding=5)
        notebook.add(tab, text="")

        self._player_file_lbl = ttk.Label(tab, font=('Segoe UI', 9))
        self._player_file_lbl.pack(anchor='w')

        self._player_display = tk.Frame(tab, bg='black')
        self._player_display.pack(fill=tk.BOTH, expand=True, pady=(3, 0))

        self._player_placeholder = tk.Label(self._player_display,
            fg='#555', bg='black', font=('Segoe UI', 14))
        self._player_placeholder.pack(expand=True)

        self._vlc_player = None
        self._vlc_instance = None

        self._player_initialized = self._init_vlc_player()
        if not self._player_initialized:
            from tkinter import ttk as _ttk
            self._player_placeholder.config(font=('Segoe UI', 12))
            self._player_download_link = tk.Label(self._player_display,
                fg='#4af', bg='black', cursor='hand2',
                font=('Segoe UI', 11, 'underline'))
            self._player_download_link.pack()
            self._player_download_link.bind('<Button-1>', lambda e: self._open_vlc_url())
            self._player_install_note = tk.Label(self._player_display,
                fg='#666', bg='black', font=('Segoe UI', 9))
            self._player_install_note.pack()
            return

        self._player_placeholder.destroy()
        self._player_placeholder = None

        ctrl = ttk.Frame(tab)
        ctrl.pack(fill=tk.X, pady=(5, 0))

        btn_f = ttk.Frame(ctrl)
        btn_f.pack(side=tk.LEFT)

        self._btn_player_browse = ttk.Button(btn_f, command=self._player_browse)
        self._btn_player_browse.pack(side=tk.LEFT, padx=1)
        self._player_play_btn = ttk.Button(btn_f, text="▶",
            command=self._player_toggle, width=3)
        self._player_play_btn.pack(side=tk.LEFT, padx=1)
        self._btn_player_stop = ttk.Button(btn_f, text="⏹",
            command=self._player_stop, width=3)
        self._btn_player_stop.pack(side=tk.LEFT, padx=1)
        self._btn_player_mute = ttk.Button(btn_f, text="🔇",
            command=self._player_toggle_mute, width=3)
        self._btn_player_mute.pack(side=tk.LEFT, padx=1)

        self._player_time_var = tk.StringVar(value="00:00 / 00:00")
        self._player_seek_var = tk.DoubleVar(value=0)
        seek = ttk.Scale(ctrl, variable=self._player_seek_var,
            from_=0, to=1000, command=self._player_seek, orient=tk.HORIZONTAL)
        seek.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self._player_time_label = ttk.Label(ctrl,
            textvariable=self._player_time_var, width=16)
        self._player_time_label.pack(side=tk.LEFT)

        self._volume_label = ttk.Label(ctrl)
        self._volume_label.pack(side=tk.LEFT, padx=(5, 0))
        self._player_vol_var = tk.DoubleVar(value=80)
        ttk.Scale(ctrl, variable=self._player_vol_var, from_=0, to=100,
            command=self._player_volume,
            orient=tk.HORIZONTAL, length=80).pack(side=tk.LEFT, padx=2)

    def _init_vlc_player(self):
        for d in [
            r'C:\Program Files\VideoLAN\VLC',
            r'C:\Program Files (x86)\VideoLAN\VLC',
            os.path.expanduser(r'~\AppData\Local\Programs\VideoLAN\VLC'),
            self.vlc_path_var.get().strip() if self.vlc_path_var.get().strip() else '',
        ]:
            if d and os.path.isfile(os.path.join(d, 'libvlc.dll')):
                if d not in os.environ.get('PATH', ''):
                    os.environ['PATH'] = d + os.pathsep + os.environ.get('PATH', '')
                if hasattr(os, 'add_dll_directory'):
                    try:
                        os.add_dll_directory(d)
                    except Exception:
                        pass
                break

        try:
            import vlc as _v
            self._vlc_instance = _v.Instance('--no-xlib --quiet')
            self._vlc_player = self._vlc_instance.media_player_new()
            for aout in ('mmdevice', 'waveout', 'directsound'):
                try:
                    self._vlc_player.audio_output_set(aout)
                    break
                except Exception:
                    continue
            return True
        except Exception:
            self._vlc_instance = None
            self._vlc_player = None
            return False

    # ── Player controls ───────────────────────────────────────

    def _player_browse(self):
        path = filedialog.askopenfilename(
            title=self.lang.tr("dialog.title.open_video"),
            filetypes=[
                (self.lang.tr("dialog.filetype.video"),
                 "*.mp4 *.avi *.mov *.mkv"),
                (self.lang.tr("dialog.filetype.all"), "*.*")])
        if path:
            self._player_open(path)

    def _player_open(self, path):
        if not self._vlc_player:
            return
        self._player_file_lbl.config(text=os.path.basename(path))
        self._player_file_lbl.update_idletasks()
        self._vlc_player.set_hwnd(self._player_display.winfo_id())
        media = self._vlc_instance.media_new(path)
        self._vlc_player.set_media(media)
        vol = int(self._player_vol_var.get())
        self._vlc_player.audio_set_mute(False)
        self._vlc_player.audio_set_volume(vol)
        self._vlc_player.play()
        self.root.after(200, lambda: self._vlc_player.audio_set_volume(vol))
        self._player_play_btn.config(text="⏸")
        self._player_poll()

    def _player_toggle(self):
        if not self._vlc_player:
            return
        state = self._vlc_player.get_state()
        if state in (6, 7):
            self._vlc_player.stop()
            self._vlc_player.play()
            self._player_play_btn.config(text="⏸")
            self._player_poll()
        elif self._vlc_player.is_playing():
            self._vlc_player.pause()
            self._player_play_btn.config(text="▶")
        else:
            self._vlc_player.play()
            self._player_play_btn.config(text="⏸")

    def _player_stop(self):
        if not self._vlc_player:
            return
        self._vlc_player.stop()
        self._player_play_btn.config(text="▶")
        self._player_seek_var.set(0)
        self._player_time_var.set("00:00 / 00:00")

    def _player_seek(self, val):
        if not self._vlc_player:
            return
        pos = float(val) / 1000.0
        if self._vlc_player.get_state() in (6, 7):
            self._vlc_player.play()
        self._vlc_player.set_position(pos)

    def _player_volume(self, val):
        if not self._vlc_player:
            return
        vol = max(0, min(100, int(float(val))))
        self._vlc_player.audio_set_mute(False)
        self._vlc_player.audio_set_volume(vol)

    def _player_toggle_mute(self):
        if not self._vlc_player:
            return
        self._vlc_player.audio_toggle_mute()

    def _player_poll(self):
        if not self._vlc_player:
            self.root.after(500, self._player_poll)
            return
        total = self._vlc_player.get_length()
        pos = self._vlc_player.get_position()
        state = self._vlc_player.get_state()
        if state == 6:
            self._player_play_btn.config(text="▶")
        self._vlc_player.audio_set_mute(False)
        vol = int(self._player_vol_var.get())
        self._vlc_player.audio_set_volume(vol)
        if total > 0:
            cur = int(pos * total) if pos > 0 else 0
            self._player_seek_var.set(pos * 1000 if pos > 0 else 0)
            self._player_time_var.set(
                f"{cur // 60000:02d}:{(cur % 60000) // 1000:02d} / "
                f"{total // 60000:02d}:{(total % 60000) // 1000:02d}")
        self.root.after(500, self._player_poll)

    def _player_close(self):
        if self._vlc_player:
            self._vlc_player.stop()
            self._vlc_player.release()
            self._vlc_player = None

    # ── UI helpers ────────────────────────────────────────────

    def _add_file_row(self, parent, var, cmd, row):
        f = ttk.Frame(parent)
        f.pack(fill=tk.X, pady=3)
        lbl = ttk.Label(f, width=10)
        lbl.pack(side=tk.LEFT)
        e = ttk.Entry(f, textvariable=var)
        e.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
        btn = ttk.Button(f, command=cmd)
        btn.pack(side=tk.RIGHT)
        return lbl, e, btn

    def _center_window(self):
        self.root.update_idletasks()
        w = self.root.winfo_width()
        h = self.root.winfo_height()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f'{w}x{h}+{x}+{y}')

    # ── Language ──────────────────────────────────────────────

    def _on_language_change(self, event=None):
        idx = self._lang_combo.current()
        if 0 <= idx < len(self._lang_codes):
            code = self._lang_codes[idx]
            self.lang.load_language(code)
            self.lang.save_pref()
            self._apply_language()

    def _apply_language(self):
        lang = self.lang

        # Window & notebook
        self.root.title(lang.tr("app.title"))
        self._title_label.config(text=lang.tr("app.title"))
        self._notebook.tab(0, text=lang.tr("tab.encrypt"))
        self._notebook.tab(1, text=lang.tr("tab.player"))
        self._notebook.tab(2, text=lang.tr("tab.settings"))

        # Main tab
        self._mode_frame.config(text=lang.tr("label.mode"))
        self._radio_encrypt.config(text=lang.tr("radio.encrypt"))
        self._radio_decrypt.config(text=lang.tr("radio.decrypt"))
        self._file_frame.config(text=lang.tr("label.file"))
        self._lbl_input.config(text=lang.tr("label.input_video"))
        self._lbl_output.config(text=lang.tr("label.output_path"))
        self._btn_browse_in.config(text=lang.tr("button.browse"))
        self._btn_browse_out.config(text=lang.tr("button.browse"))

        self._password_frame.config(text=lang.tr("label.password"))
        self._refresh_password_info()
        key = "password.hide" if self.password_visible else "password.show"
        self.toggle_pw_btn.config(text=lang.tr(key))

        self._progress_frame.config(text=lang.tr("label.progress"))
        self._refresh_process_button()

        # Settings tab
        self._ff_frame.config(text=lang.tr("settings.ffmpeg_frame"))
        self._ff_hint.config(text=lang.tr("settings.ffmpeg_hint"))
        self._btn_ff_apply.config(text=lang.tr("settings.ffmpeg_apply"))
        self._btn_browse_ff.config(text=lang.tr("button.browse"))

        self._vlc_frame.config(text=lang.tr("settings.vlc_frame"))
        self._vlc_hint.config(text=lang.tr("settings.vlc_hint"))
        self._btn_vlc_apply.config(text=lang.tr("settings.vlc_apply"))
        self._btn_browse_vlc.config(text=lang.tr("button.browse"))
        self._refresh_vlc_status()

        self._audio_frame.config(text=lang.tr("settings.audio_frame"))
        self._audio_check.config(text=lang.tr("settings.audio_keep"))
        self._audio_hint.config(text=lang.tr("settings.audio_hint"))

        self._fmt_frame.config(text=lang.tr("settings.format_frame"))
        self._fmt_label.config(text=lang.tr("settings.format_container"))
        self._fmt_hint.config(text=lang.tr("settings.format_hint"))

        self._lang_frame.config(text=lang.tr("settings.language"))

        # Player tab
        if self._player_initialized:
            self._player_file_lbl.config(text=lang.tr("player.no_file"))
            self._btn_player_browse.config(text=lang.tr("player.select_video"))
            self._volume_label.config(text=lang.tr("player.volume"))
        else:
            self._player_file_lbl.config(text=lang.tr("player.no_file"))
            if hasattr(self, '_player_placeholder') and self._player_placeholder:
                self._player_placeholder.config(text=lang.tr("player.not_found"))
            if hasattr(self, '_player_download_link'):
                self._player_download_link.config(text=lang.tr("player.download_link"))
            if hasattr(self, '_player_install_note'):
                self._player_install_note.config(text=lang.tr("player.install_hint"))

    def _refresh_vlc_status(self):
        if not hasattr(self, '_vlc_status_label'):
            return
        vlc = self._search_vlc()
        if vlc:
            self._vlc_status_label.config(
                text=self.lang.tr("settings.vlc_detected", path=vlc),
                foreground='green')
        else:
            self._vlc_status_label.config(
                text=self.lang.tr("settings.vlc_not_found"),
                foreground='#999')

    def _refresh_password_info(self):
        is_enc = self.mode.get() == 'encrypt'
        if is_enc:
            self._password_info_label.config(
                text=self.lang.tr("password.info_encrypt"), foreground='#666')
        else:
            self._password_info_label.config(
                text=self.lang.tr("password.info_decrypt"), foreground='#666')

    def _refresh_process_button(self):
        if self.is_running:
            self.process_btn.config(text=self.lang.tr("button.processing"))
        else:
            self.process_btn.config(text=self.lang.tr("button.start"))

    # ── Mode switch ───────────────────────────────────────────

    def _on_mode_change(self):
        self.input_path.set('')
        self.output_path.set('')
        self.password_var.set('')
        self._refresh_password_info()
        self.progress_var.set(0)
        self.status_var.set(self.lang.tr("status.ready"))

    # ── File dialogs ──────────────────────────────────────────

    def _browse_input(self):
        fmts = ['mp4', 'avi', 'mov', 'mkv']
        path = filedialog.askopenfilename(
            title=self.lang.tr("dialog.title.open_input"),
            filetypes=[
                (self.lang.tr("dialog.filetype.video"),
                 ' '.join(f'*.{f}' for f in fmts)),
                (self.lang.tr("dialog.filetype.all"), "*.*")])
        if path:
            self.input_path.set(path)
            self._auto_set_output_path()

    def _browse_output(self):
        ext = self.output_format.get() or 'mp4'
        path = filedialog.asksaveasfilename(
            title=self.lang.tr("dialog.title.save_output"),
            defaultextension=f'.{ext}',
            filetypes=[(f'{ext.upper()} Video', f'*.{ext}')])
        if path:
            self.output_path.set(path)

    def _auto_set_output_path(self):
        inp = self.input_path.get()
        if not inp or not os.path.isfile(inp):
            return
        if self.output_path.get():
            return
        d = os.path.dirname(inp)
        name = os.path.splitext(os.path.basename(inp))[0]
        if self.mode.get() == 'encrypt':
            self.output_path.set(os.path.join(d, f'{name}_encrypted.ve2'))
        else:
            ext = self.output_format.get() or 'mp4'
            self.output_path.set(os.path.join(d, f'{name}_decrypted.{ext}'))

    def _on_format_change(self, *_):
        if self.mode.get() == 'encrypt':
            return
        inp = self.input_path.get()
        out = self.output_path.get()
        if not inp or not out:
            return
        d = os.path.dirname(out)
        name = os.path.splitext(os.path.basename(out))[0]
        ext = self.output_format.get() or 'mp4'
        new_out = os.path.join(d, f'{name}.{ext}')
        if new_out != out:
            self.output_path.set(new_out)

    # ── Settings actions ──────────────────────────────────────

    def _browse_ffmpeg(self):
        path = filedialog.askopenfilename(
            title=self.lang.tr("dialog.title.open_ffmpeg"),
            filetypes=[
                (self.lang.tr("dialog.filetype.ffmpeg"), "ffmpeg.exe"),
                (self.lang.tr("dialog.filetype.all"), "*.*")])
        if path:
            self.ffmpeg_path_var.set(path)
            self._apply_ffmpeg_path()

    def _apply_ffmpeg_path(self):
        p = self.ffmpeg_path_var.get().strip()
        if p:
            set_ffmpeg_path(p)

    def _browse_vlc(self):
        path = filedialog.askdirectory(
            title=self.lang.tr("dialog.title.open_vlc"))
        if path:
            self.vlc_path_var.set(path)

    def _apply_vlc_path(self):
        p = self.vlc_path_var.get().strip()
        exe = os.path.join(p, 'vlc.exe') if p else ''
        if exe and os.path.isfile(exe):
            messagebox.showinfo(
                self.lang.tr("msgbox.vlc_set.title"),
                self.lang.tr("msgbox.vlc_set.message"))
        elif p:
            messagebox.showerror(
                self.lang.tr("msgbox.error.title"),
                self.lang.tr("msgbox.vlc_error.message", path=exe))

    # ── Password ───────────────────────────────────────────────

    def _toggle_password_show(self):
        self.password_visible = not self.password_visible
        self.password_entry.config(show='' if self.password_visible else '*')
        key = "password.hide" if self.password_visible else "password.show"
        self.toggle_pw_btn.config(text=self.lang.tr(key))

    # ── Progress callback ─────────────────────────────────────

    def _progress_callback(self, percent, message):
        self.progress_var.set(percent)
        self.status_var.set(message)
        self.root.update_idletasks()

    # ── Process flow ──────────────────────────────────────────

    def _on_process(self):
        if self.is_running:
            return

        inp = self.input_path.get()
        out = self.output_path.get()
        mode = self.mode.get()

        if not inp:
            return messagebox.showerror(
                self.lang.tr("msgbox.error.title"),
                self.lang.tr("msgbox.error.no_input"))
        if not os.path.isfile(inp):
            return messagebox.showerror(
                self.lang.tr("msgbox.error.title"),
                self.lang.tr("msgbox.error.file_not_found"))
        if not out:
            return messagebox.showerror(
                self.lang.tr("msgbox.error.title"),
                self.lang.tr("msgbox.error.no_output"))

        password = self.password_var.get()
        if not password:
            return messagebox.showerror(
                self.lang.tr("msgbox.error.title"),
                self.lang.tr("msgbox.error.no_password"))
        if len(password) < 8:
            return messagebox.showerror(
                self.lang.tr("msgbox.error.title"),
                self.lang.tr("msgbox.error.password_short"))

        if mode == 'encrypt':
            from tkinter import simpledialog
            confirm = simpledialog.askstring(
                self.lang.tr("msgbox.confirm_password.title"),
                self.lang.tr("msgbox.confirm_password.message"),
                show='*', parent=self.root)
            if confirm != password:
                return messagebox.showerror(
                    self.lang.tr("msgbox.error.title"),
                    self.lang.tr("msgbox.error.password_mismatch"))

        self.is_running = True
        self.process_btn.config(state='disabled',
                                 text=self.lang.tr("button.processing"))
        self.progress_var.set(0)
        self.status_var.set(self.lang.tr("status.initializing"))

        t = threading.Thread(target=self._run_process,
                             args=(inp, out, mode, password), daemon=True)
        t.start()

    def _run_process(self, inp, out, mode, password):
        try:
            result = process_video(
                input_path=inp,
                output_path=out,
                mode=mode,
                password=password,
                progress_callback=self._progress_callback,
            )
            self.root.after(0, lambda: self._on_done(result))
        except Exception as e:
            self.root.after(0, lambda: self._on_error(str(e)))

    def _on_done(self, result):
        self.progress_var.set(100)
        self.status_var.set(self.lang.tr("status.done"))
        self.is_running = False
        self.process_btn.config(state='normal',
                                 text=self.lang.tr("button.start"))
        messagebox.showinfo(
            self.lang.tr("msgbox.done.title"),
            self.lang.tr("msgbox.done.message", path=result['output_path']))

    def _on_error(self, msg):
        self.status_var.set(self.lang.tr("status.error", msg=msg))
        self.is_running = False
        self.process_btn.config(state='normal',
                                 text=self.lang.tr("button.start"))
        messagebox.showerror(
            self.lang.tr("msgbox.error.title"), msg)

    def _on_close(self):
        self._player_close()
        self.root.destroy()

    @staticmethod
    def _open_vlc_url():
        import webbrowser
        webbrowser.open('https://www.videolan.org/vlc/')


def main():
    if getattr(sys, 'frozen', False):
        p = os.path.join(sys._MEIPASS, 'ffmpeg', 'ffmpeg.exe')
        if os.path.isfile(p):
            set_ffmpeg_path(p)
    else:
        local = os.path.join(_project_root, 'ffmpeg', 'ffmpeg.exe')
        if os.path.isfile(local):
            set_ffmpeg_path(local)

    root = tk.Tk()
    app = VideoEncryptApp(root)
    root.mainloop()


if __name__ == '__main__':
    main()

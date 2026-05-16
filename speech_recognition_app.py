import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

import tkinter as tk
from tkinter import ttk, messagebox
import speech_recognition as sr
import threading
import queue
import time
import json
import sys
import ctypes
import winsound
import pyautogui
import pyperclip
from PIL import Image, ImageDraw
import pystray

# PyInstaller one-file: use exe dir for writable files, _MEIPASS for bundled data
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
    BUNDLE_DIR = sys._MEIPASS
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    BUNDLE_DIR = APP_DIR

CONFIG_FILE = os.path.join(APP_DIR, "config.json")
HISTORY_FILE = os.path.join(APP_DIR, "recognition_history.txt")

# Copy default config from bundle if not present in writable location
if getattr(sys, 'frozen', False) and not os.path.exists(CONFIG_FILE):
    bundled_config = os.path.join(BUNDLE_DIR, "config.json")
    if os.path.exists(bundled_config):
        import shutil
        shutil.copy(bundled_config, CONFIG_FILE)

# Windows SendInput — match the real INPUT struct with union (40 bytes on 64-bit)
INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 4
KEYEVENTF_KEYUP = 2


class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long),
                ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_void_p)]


class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort),
                ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_void_p)]


class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong),
                ("wParamL", ctypes.c_ushort),
                ("wParamH", ctypes.c_ushort)]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT),
                ("ki", _KEYBDINPUT),
                ("hi", _HARDWAREINPUT)]


class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong),
                ("u", _INPUT_UNION)]


def send_unicode_text(text):
    inputs = []
    for ch in text:
        code = ord(ch)
        inp_d = _INPUT()
        inp_d.type = INPUT_KEYBOARD
        inp_d.u.ki.wVk = 0
        inp_d.u.ki.wScan = code
        inp_d.u.ki.dwFlags = KEYEVENTF_UNICODE
        inp_d.u.ki.time = 0
        inp_d.u.ki.dwExtraInfo = None
        inputs.append(inp_d)

        inp_u = _INPUT()
        inp_u.type = INPUT_KEYBOARD
        inp_u.u.ki.wVk = 0
        inp_u.u.ki.wScan = code
        inp_u.u.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP
        inp_u.u.ki.time = 0
        inp_u.u.ki.dwExtraInfo = None
        inputs.append(inp_u)

    n = len(inputs)
    if n > 0:
        ArrayType = _INPUT * n
        ctypes.windll.user32.SendInput(n, ArrayType(*inputs), ctypes.sizeof(_INPUT))

DEFAULT_CONFIG = {
    "stop_word": "结束输入",
    "phrase_time_limit": 10,
    "ambient_duration": 1,
    "language": "zh",
    "model": "tiny",
    "minimize_to_tray": True,
}


def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return {**DEFAULT_CONFIG, **json.load(f)}
    return DEFAULT_CONFIG


def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def create_tray_icon():
    img = Image.new("RGB", (64, 64), color="#1f77d2")
    draw = ImageDraw.Draw(img)
    draw.ellipse([16, 8, 48, 40], fill="white")
    draw.rectangle([28, 38, 36, 52], fill="white")
    draw.rectangle([20, 28, 44, 38], fill="white")
    return img


class WakeWordApp:
    def __init__(self, root):
        self.root = root
        self.root.title("语音识别输入")
        self.root.geometry("420x500")
        self.root.resizable(False, False)
        self.root.configure(bg="#f0f2f5")
        self.root.option_add("*Font", "{Microsoft YaHei UI} 10")

        self.config = load_config()
        self.recognizer = sr.Recognizer()
        self.recognizer.pause_threshold = 1.5
        self.recognizer.non_speaking_duration = 1.0
        self.recognizer.dynamic_energy_threshold = False
        pyautogui.FAILSAFE = False
        self.whisper_model = None
        self._init_whisper()
        self.running = False
        self.message_queue = queue.Queue()
        self.tray_icon = None
        self.tray_thread = None

        self.setup_ui()
        self.check_queue()

        if self.config["minimize_to_tray"]:
            self.root.after(500, self.minimize_to_tray)
        self.root.after(300, self.start_engine)

        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        title_frame = tk.Frame(self.root, bg="#1f77d2", height=60)
        title_frame.pack(fill=tk.X)
        tk.Label(
            title_frame, text="🎤 语音识别输入",
            font=("{Microsoft YaHei UI}", 16, "bold"),
            bg="#1f77d2", fg="white", pady=15
        ).pack()

        # Settings card
        card = tk.Frame(self.root, bg="white", padx=15, pady=10)
        card.pack(fill=tk.X, padx=12, pady=10)
        card.config(relief=tk.FLAT, borderwidth=0,
                    highlightbackground="#e0e0e0", highlightthickness=1)

        tk.Label(card, text="停止词", bg="white", fg="#202124",
                 font=("{Microsoft YaHei UI}", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self.stop_entry = tk.Entry(card, font=("{Microsoft YaHei UI}", 14),
                                   justify=tk.CENTER, relief=tk.SOLID,
                                   borderwidth=1)
        self.stop_entry.insert(0, self.config["stop_word"])
        self.stop_entry.pack(fill=tk.X, pady=(0, 8))

        tk.Label(card, text="启动后自动持续识别，说出停止词结束识别",
                 bg="white", fg="#5f6368", font=("{Microsoft YaHei UI}", 8)).pack()

        # Status bar
        self.status_frame = tk.Frame(self.root, bg="white", padx=15, pady=10)
        self.status_frame.pack(fill=tk.X, padx=12, pady=6)
        self.status_frame.config(
            relief=tk.FLAT, borderwidth=0,
            highlightbackground="#e0e0e0", highlightthickness=1
        )

        status_left = tk.Frame(self.status_frame, bg="white")
        status_left.pack(fill=tk.X)

        self.status_dot = tk.Canvas(status_left, width=12, height=12,
                                    bg="white", highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 8))
        self.dot = self.status_dot.create_oval(1, 1, 11, 11, fill="#ea4335", outline="")

        self.status_label = tk.Label(
            status_left, text="引擎未启动", bg="white", fg="#ea4335",
            font=("{Microsoft YaHei UI}", 10, "bold")
        )
        self.status_label.pack(side=tk.LEFT)

        self.detail_label = tk.Label(
            status_left, text="", bg="white", fg="#5f6368",
            font=("{Microsoft YaHei UI}", 8)
        )
        self.detail_label.pack(side=tk.LEFT, padx=10)

        # Buttons
        btn_frame = tk.Frame(self.root, bg="#f0f2f5", pady=10)
        btn_frame.pack(fill=tk.X, padx=12)

        self.toggle_btn = tk.Button(
            btn_frame, text="▶ 启动引擎", command=self.toggle_engine,
            font=("{Microsoft YaHei UI}", 11, "bold"),
            bg="#34a853", fg="white", padx=18, pady=8,
            relief=tk.FLAT, cursor="hand2", activebackground="#2d9047"
        )
        self.toggle_btn.pack(side=tk.LEFT, padx=4)

        tk.Button(
            btn_frame, text="⚙ 保存设置", command=self.save_settings,
            font=("{Microsoft YaHei UI}", 10),
            bg="#fbbc04", fg="#202124", padx=14, pady=8,
            relief=tk.FLAT, cursor="hand2", activebackground="#f8b500"
        ).pack(side=tk.LEFT, padx=4)

        # Log area
        log_frame = tk.Frame(self.root, bg="white", padx=10, pady=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 12))
        log_frame.config(
            relief=tk.FLAT, borderwidth=0,
            highlightbackground="#e0e0e0", highlightthickness=1
        )

        tk.Label(log_frame, text="记录", bg="white", fg="#202124",
                 font=("{Microsoft YaHei UI}", 9, "bold")).pack(anchor=tk.W)

        self.log_area = tk.Text(log_frame, font=("{Microsoft YaHei UI}", 9),
                                bg="white", fg="#202124", relief=tk.FLAT,
                                borderwidth=0, wrap=tk.WORD, height=8)
        self.log_area.pack(fill=tk.BOTH, expand=True)

    def log(self, msg):
        t = time.strftime("%H:%M:%S")
        self.log_area.insert(tk.END, f"[{t}] {msg}\n")
        self.log_area.see(tk.END)

    def toggle_engine(self):
        if self.running:
            self.stop_engine()
        else:
            self.start_engine()

    def start_engine(self):
        if self.running:
            return
        self.running = True
        self.config["stop_word"] = self.stop_entry.get().strip() or "结束输入"
        self.update_status("listening", f"持续识别中，停止词: 「{self.config['stop_word']}」")
        self.toggle_btn.config(text="⏹ 停止引擎", bg="#ea4335",
                               activebackground="#d33c2d")
        self.log(f"引擎启动，停止词: 「{self.config['stop_word']}」")

        t = threading.Thread(target=self.listen_loop, daemon=True)
        t.start()

    def _init_whisper(self):
        try:
            from faster_whisper import WhisperModel
            model_name = self.config.get("model", "tiny")
            # When running as bundled exe, use bundled model from _MEIPASS
            if getattr(sys, 'frozen', False):
                bundled = os.path.join(BUNDLE_DIR, "whisper_model")
                if os.path.isdir(bundled):
                    model_name = bundled
            self.message_queue.put(("status", "listening",
                                    f"加载本地模型...", ""))
            self.whisper_model = WhisperModel(model_name, device="cpu",
                                              compute_type="int8")
            self.message_queue.put(("status", "listening",
                                    f"本地模型就绪", ""))
        except Exception:
            self.whisper_model = None

    def transcribe(self, audio):
        if self.whisper_model is not None:
            return self._transcribe_local(audio)
        return self._transcribe_google(audio)

    def _transcribe_local(self, audio):
        import numpy as np
        raw = audio.get_raw_data()
        samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
        segments, _ = self.whisper_model.transcribe(
            samples, language=self.config["language"])
        return "".join(seg.text for seg in segments).strip()

    def _transcribe_google(self, audio):
        return self.recognizer.recognize_google(
            audio, language=self.config["language"])

    def stop_engine(self):
        self.running = False
        self.update_status("stopped", "引擎已停止")
        self.toggle_btn.config(text="▶ 启动引擎", bg="#34a853",
                               activebackground="#2d9047")
        self.log("引擎已停止")

    def update_status(self, state, text, detail=""):
        colors = {
            "listening": "#34a853",
            "dictating": "#fbbc04",
            "recognizing": "#1f77d2",
            "stopped": "#ea4335",
            "error": "#ea4335",
        }
        color = colors.get(state, "#5f6368")
        self.status_dot.itemconfig(self.dot, fill=color)
        self.status_label.config(text=text, fg=color)
        self.detail_label.config(text=detail)

    def listen_loop(self):
        try:
            mic = sr.Microphone()
        except Exception as e:
            self.message_queue.put(("error", f"麦克风错误: {e}"))
            self.running = False
            return

        try:
            with mic as source:
                self.message_queue.put(("status", "listening",
                                        "校准环境噪音...", ""))
                self.recognizer.adjust_for_ambient_noise(
                    source, duration=self.config["ambient_duration"]
                )
                stop_word = self.config["stop_word"]
                self.message_queue.put(("status", "listening",
                                        f"持续识别中，停止词: 「{stop_word}」", ""))

                while self.running:
                    try:
                        audio = self.recognizer.listen(
                            source,
                            timeout=1,
                            phrase_time_limit=self.config["phrase_time_limit"]
                        )
                    except sr.WaitTimeoutError:
                        continue

                    if not self.running:
                        break

                    self.message_queue.put(("status", "recognizing",
                                            "识别中...", ""))

                    try:
                        text = self.transcribe(audio)
                    except sr.UnknownValueError:
                        continue
                    except sr.RequestError as e:
                        self.message_queue.put(("error", f"识别错误: {e}", ""))
                        time.sleep(1)
                        continue
                    except Exception as e:
                        self.message_queue.put(("error", f"识别错误: {e}", ""))
                        time.sleep(1)
                        continue

                    if not text.strip():
                        continue

                    # Check for stop word
                    stop_word = self.config["stop_word"]
                    if stop_word in text:
                        remaining = text.replace(stop_word, "").strip()
                        if remaining:
                            self.message_queue.put(("dictation_result", remaining))
                            self.type_text(remaining)
                            self.save_to_file(remaining)
                            winsound.Beep(800, 100)
                        self.message_queue.put(("stop_detected", text))
                        winsound.Beep(600, 300)
                        self.running = False
                        break

                    self.message_queue.put(("dictation_result", text))
                    self.type_text(text)
                    self.save_to_file(text)
                    winsound.Beep(800, 100)
                    self.message_queue.put(("status", "listening",
                                            f"持续识别中，停止词: 「{stop_word}」", ""))
        except Exception as e:
            self.message_queue.put(("error", f"引擎异常: {e}"))
        finally:
            if self.running:
                self.running = False
            self.message_queue.put(("engine_stopped",))

    def type_text(self, text):
        try:
            pyperclip.copy(text)
            time.sleep(0.05)
            send_unicode_text(text)
            self.message_queue.put(("typed", text))
            print(f"\n⌨ 已输入: {text}", flush=True)
        except Exception as e:
            self.message_queue.put(("error", f"输入失败: {e}"))
            print(f"\n⚠ 输入失败 (已复制到剪贴板): {e}", flush=True)

    def save_to_file(self, text):
        try:
            t = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{t}] {text}\n")
        except Exception:
            pass

    def save_settings(self):
        stop = self.stop_entry.get().strip()
        if not stop:
            messagebox.showwarning("提示", "停止词不能为空")
            return
        self.config["stop_word"] = stop
        save_config(self.config)
        self.log(f"设置已保存，停止词: 「{stop}」")
        messagebox.showinfo("成功", f"设置已保存！\n停止词: {stop}")

        if self.running:
            self.stop_engine()
            self.root.after(300, self.start_engine)

    def check_queue(self):
        try:
            while True:
                msg = self.message_queue.get_nowait()
                msg_type = msg[0]

                if msg_type == "status":
                    state, text, detail = msg[1], msg[2], msg[3] if len(msg) > 3 else ""
                    self.update_status(state, text, detail)

                elif msg_type == "dictation_result":
                    self.log(f"📝 识别结果: {msg[1]}")
                    print(f"📝 {msg[1]}", flush=True)

                elif msg_type == "typed":
                    self.log(f"⌨ 已输入: {msg[1]}")

                elif msg_type == "stop_detected":
                    self.log(f"🛑 检测到停止词: 「{msg[1]}」，引擎已停止")
                    print(f"🛑 检测到停止词，引擎已停止", flush=True)

                elif msg_type == "error":
                    self.update_status("error", msg[1])
                    self.log(f"⚠ {msg[1]}")

                elif msg_type == "engine_stopped":
                    self.update_status("stopped", "引擎已停止")

        except queue.Empty:
            pass
        self.root.after(100, self.check_queue)

    def minimize_to_tray(self):
        if self.tray_icon is not None:
            self.root.withdraw()
            return
        self.root.withdraw()
        self.tray_thread = threading.Thread(target=self.run_tray, daemon=True)
        self.tray_thread.start()

    def run_tray(self):
        def on_show(icon, item):
            self.root.after(0, self.root.deiconify)

        def on_quit(icon, item):
            self.tray_icon.stop()
            self.running = False
            self.root.after(0, self.root.destroy)

        menu = pystray.Menu(
            pystray.MenuItem("显示窗口", on_show, default=True),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("退出", on_quit),
        )
        self.tray_icon = pystray.Icon(
            "voice_input", create_tray_icon(), "语音识别输入", menu
        )
        self.tray_icon.run()

    def on_close(self):
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = WakeWordApp(root)
    root.mainloop()

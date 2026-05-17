import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
import threading
import queue
import time
import json
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

if getattr(sys, 'frozen', False) and not os.path.exists(CONFIG_FILE):
    bundled_config = os.path.join(BUNDLE_DIR, "config.json")
    if os.path.exists(bundled_config):
        import shutil
        shutil.copy(bundled_config, CONFIG_FILE)

# ── Windows SendInput ──────────────────────────────────────────────

INPUT_KEYBOARD = 1
KEYEVENTF_UNICODE = 4
KEYEVENTF_KEYUP = 2

class _MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", ctypes.c_long), ("dy", ctypes.c_long),
                ("mouseData", ctypes.c_ulong), ("dwFlags", ctypes.c_ulong),
                ("time", ctypes.c_ulong), ("dwExtraInfo", ctypes.c_void_p)]

class _KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", ctypes.c_ushort), ("wScan", ctypes.c_ushort),
                ("dwFlags", ctypes.c_ulong), ("time", ctypes.c_ulong),
                ("dwExtraInfo", ctypes.c_void_p)]

class _HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", ctypes.c_ulong), ("wParamL", ctypes.c_ushort),
                ("wParamH", ctypes.c_ushort)]

class _INPUT_UNION(ctypes.Union):
    _fields_ = [("mi", _MOUSEINPUT), ("ki", _KEYBDINPUT), ("hi", _HARDWAREINPUT)]

class _INPUT(ctypes.Structure):
    _fields_ = [("type", ctypes.c_ulong), ("u", _INPUT_UNION)]

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

# ── Config ─────────────────────────────────────────────────────────

DEFAULT_CONFIG = {
    "stop_word": "结束输入",
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

# ── Tray icon ──────────────────────────────────────────────────────

def create_tray_icon():
    img = Image.new("RGB", (64, 64), color="#1f77d2")
    draw = ImageDraw.Draw(img)
    draw.ellipse([16, 8, 48, 40], fill="white")
    draw.rectangle([28, 38, 36, 52], fill="white")
    draw.rectangle([20, 28, 44, 38], fill="white")
    return img

# ── Streaming speech engine ────────────────────────────────────────

def build_model_path():
    if getattr(sys, 'frozen', False):
        bundled = os.path.join(BUNDLE_DIR, "vosk_model")
        if os.path.isdir(bundled):
            return bundled
    project = os.path.join(APP_DIR, "vosk_model")
    if os.path.isdir(project):
        return project
    return None

class VoskStreamEngine:
    """Continuous streaming recognition with Vosk.

    Designed to run on a background thread; posts events to a queue."""

    def __init__(self, msg_queue, stop_word):
        self.mq = msg_queue
        self.stop_word = stop_word
        self.running = False

    def start(self):
        self.running = True
        t = threading.Thread(target=self._run, daemon=True)
        t.start()

    def stop(self):
        self.running = False

    def _run(self):
        import pyaudio
        import vosk

        self.mq.put(("status", "loading", "查找语音模型...", ""))

        model_path = build_model_path()
        if not model_path:
            self.mq.put(("error", "未找到语音模型，请将 vosk_model 放到程序目录"))
            self.running = False
            self.mq.put(("engine_stopped",))
            return

        self.mq.put(("status", "loading", f"加载模型 {model_path} ...", ""))
        try:
            model = vosk.Model(model_path)
        except Exception as e:
            self.mq.put(("error", f"模型加载失败: {e}"))
            self.running = False
            self.mq.put(("engine_stopped",))
            return

        self.mq.put(("status", "loading", "模型就绪，打开麦克风...", ""))
        rec = vosk.KaldiRecognizer(model, 16000)
        rec.SetWords(True)
        rec.SetPartialWords(True)

        try:
            pa = pyaudio.PyAudio()
        except Exception as e:
            self.mq.put(("error", f"音频初始化失败: {e}"))
            self.running = False
            self.mq.put(("engine_stopped",))
            return

        try:
            stream = pa.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=4000,
            )
            stream.start_stream()
        except Exception as e:
            pa.terminate()
            self.mq.put(("error", f"麦克风打开失败: {e}"))
            self.running = False
            self.mq.put(("engine_stopped",))
            return

        self.mq.put(("status", "listening",
                     f"流式识别中，停止词: 「{self.stop_word}」", ""))
        self.mq.put(("engine_ready",))

        accumulated = ""

        try:
            while self.running:
                try:
                    data = stream.read(4000, exception_on_overflow=False)
                except Exception:
                    continue

                chunk_len = len(data)
                if chunk_len == 0:
                    continue

                has_final = rec.AcceptWaveform(data) if chunk_len > 0 else False

                if has_final:
                    result = json.loads(rec.Result())
                    text = result.get("text", "").strip()
                    if text:
                        sw = self.stop_word
                        if sw and sw in text:
                            remaining = text.replace(sw, "").strip()
                            if remaining:
                                accumulated += remaining
                            if accumulated.strip():
                                self.mq.put(("final", accumulated.strip()))
                            self.mq.put(("stop_detected", text))
                            winsound.Beep(600, 300)
                            self.running = False
                            break
                        else:
                            accumulated += text
                            self.mq.put(("final", accumulated.strip()))
                            winsound.Beep(800, 100)
                            accumulated = ""
                else:
                    partial = json.loads(rec.PartialResult())
                    partial_text = partial.get("partial", "").strip()
                    if partial_text:
                        self.mq.put(("partial", accumulated + partial_text))

        except Exception as e:
            self.mq.put(("error", f"引擎异常: {e}"))
        finally:
            try:
                stream.stop_stream()
                stream.close()
                pa.terminate()
            except Exception:
                pass
            self.mq.put(("engine_stopped",))

# ── GUI Application ────────────────────────────────────────────────

class VoiceInputApp:
    def __init__(self, root):
        self.root = root
        self.root.title("语音识别输入")
        self.root.geometry("420x500")
        self.root.resizable(False, False)
        self.root.configure(bg="#f0f2f5")
        self.root.option_add("*Font", "{Microsoft YaHei UI} 10")

        self.config = load_config()
        pyautogui.FAILSAFE = False
        self.engine = None
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

    # ── UI ──────────────────────────────────────────────────────

    def setup_ui(self):
        title_frame = tk.Frame(self.root, bg="#1f77d2", height=60)
        title_frame.pack(fill=tk.X)
        tk.Label(
            title_frame, text="🎤 语音识别输入",
            font=("{Microsoft YaHei UI}", 16, "bold"),
            bg="#1f77d2", fg="white", pady=15
        ).pack()

        card = tk.Frame(self.root, bg="white", padx=15, pady=10)
        card.pack(fill=tk.X, padx=12, pady=10)
        card.config(relief=tk.FLAT, borderwidth=0,
                    highlightbackground="#e0e0e0", highlightthickness=1)

        tk.Label(card, text="停止词", bg="white", fg="#202124",
                 font=("{Microsoft YaHei UI}", 10, "bold")).pack(anchor=tk.W, pady=(0, 4))
        self.stop_entry = tk.Entry(card, font=("{Microsoft YaHei UI}", 14),
                                   justify=tk.CENTER, relief=tk.SOLID, borderwidth=1)
        self.stop_entry.insert(0, self.config["stop_word"])
        self.stop_entry.pack(fill=tk.X, pady=(0, 8))
        tk.Label(card, text="启动后自动识别，说出停止词结束",
                 bg="white", fg="#5f6368", font=("{Microsoft YaHei UI}", 8)).pack()

        # Status
        self.status_frame = tk.Frame(self.root, bg="white", padx=15, pady=10)
        self.status_frame.pack(fill=tk.X, padx=12, pady=6)
        self.status_frame.config(relief=tk.FLAT, borderwidth=0,
                                 highlightbackground="#e0e0e0", highlightthickness=1)
        status_left = tk.Frame(self.status_frame, bg="white")
        status_left.pack(fill=tk.X)
        self.status_dot = tk.Canvas(status_left, width=12, height=12,
                                    bg="white", highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 8))
        self.dot = self.status_dot.create_oval(1, 1, 11, 11, fill="#ea4335", outline="")
        self.status_label = tk.Label(
            status_left, text="引擎未启动", bg="white", fg="#ea4335",
            font=("{Microsoft YaHei UI}", 10, "bold"))
        self.status_label.pack(side=tk.LEFT)
        self.detail_label = tk.Label(
            status_left, text="", bg="white", fg="#5f6368",
            font=("{Microsoft YaHei UI}", 8))
        self.detail_label.pack(side=tk.LEFT, padx=10)

        # Buttons
        btn_frame = tk.Frame(self.root, bg="#f0f2f5", pady=10)
        btn_frame.pack(fill=tk.X, padx=12)
        self.toggle_btn = tk.Button(
            btn_frame, text="▶ 启动引擎", command=self.toggle_engine,
            font=("{Microsoft YaHei UI}", 11, "bold"),
            bg="#34a853", fg="white", padx=18, pady=8,
            relief=tk.FLAT, cursor="hand2", activebackground="#2d9047")
        self.toggle_btn.pack(side=tk.LEFT, padx=4)
        tk.Button(
            btn_frame, text="⚙ 保存设置", command=self.save_settings,
            font=("{Microsoft YaHei UI}", 10),
            bg="#fbbc04", fg="#202124", padx=14, pady=8,
            relief=tk.FLAT, cursor="hand2", activebackground="#f8b500"
        ).pack(side=tk.LEFT, padx=4)

        # Log
        log_frame = tk.Frame(self.root, bg="white", padx=10, pady=6)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=12, pady=(6, 12))
        log_frame.config(relief=tk.FLAT, borderwidth=0,
                         highlightbackground="#e0e0e0", highlightthickness=1)
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

    # ── Engine controls ────────────────────────────────────────

    def toggle_engine(self):
        if self.running:
            self.stop_engine()
        else:
            self.start_engine()

    def start_engine(self):
        if self.running:
            return
        self.running = True
        stop_word = self.stop_entry.get().strip() or "结束输入"
        self.config["stop_word"] = stop_word
        self.update_status("loading", "加载模型中...", "")
        self.toggle_btn.config(text="⏹ 停止引擎", bg="#ea4335",
                               activebackground="#d33c2d")
        self.log(f"引擎启动，停止词: 「{stop_word}」")
        self.engine = VoskStreamEngine(self.message_queue, stop_word)
        self.engine.start()

    def stop_engine(self):
        self.running = False
        if self.engine:
            self.engine.stop()
            self.engine = None
        self.update_status("stopped", "引擎已停止")
        self.toggle_btn.config(text="▶ 启动引擎", bg="#34a853",
                               activebackground="#2d9047")
        self.log("引擎已停止")

    # ── Status ─────────────────────────────────────────────────

    def update_status(self, state, text, detail=""):
        colors = {
            "loading": "#fbbc04",
            "listening": "#34a853",
            "stopped": "#ea4335",
            "error": "#ea4335",
        }
        color = colors.get(state, "#5f6368")
        self.status_dot.itemconfig(self.dot, fill=color)
        self.status_label.config(text=text, fg=color)
        self.detail_label.config(text=detail)

    # ── Output ─────────────────────────────────────────────────

    def type_text(self, text):
        try:
            pyperclip.copy(text)
            time.sleep(0.05)
            send_unicode_text(text)
            self.log(f"⌨ 已输入: {text}")
        except Exception as e:
            self.log(f"⚠ 输入失败: {e} (已复制到剪贴板)")

    def save_to_file(self, text):
        try:
            t = time.strftime("%Y-%m-%d %H:%M:%S")
            with open(HISTORY_FILE, "a", encoding="utf-8") as f:
                f.write(f"[{t}] {text}\n")
        except Exception:
            pass

    # ── Settings ───────────────────────────────────────────────

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

    # ── Message queue ──────────────────────────────────────────

    def check_queue(self):
        try:
            while True:
                msg = self.message_queue.get_nowait()
                msg_type = msg[0]

                if msg_type == "status":
                    self.update_status(msg[1], msg[2], msg[3] if len(msg) > 3 else "")

                elif msg_type == "engine_ready":
                    self.update_status("listening",
                        f"流式识别中，停止词: 「{self.config['stop_word']}」", "")

                elif msg_type == "partial":
                    self.detail_label.config(text=f"⋯ {msg[1]}")

                elif msg_type == "final":
                    text = msg[1]
                    self.log(f"📝 {text}")
                    self.type_text(text)
                    self.save_to_file(text)
                    self.detail_label.config(text="")

                elif msg_type == "stop_detected":
                    self.log(f"🛑 检测到停止词: 「{msg[1]}」")
                    self.running = False
                    if self.engine:
                        self.engine.stop()
                        self.engine = None

                elif msg_type == "error":
                    self.update_status("error", msg[1])
                    self.log(f"⚠ {msg[1]}")

                elif msg_type == "engine_stopped":
                    self.update_status("stopped", "引擎已停止")
                    self.running = False
        except queue.Empty:
            pass
        self.root.after(80, self.check_queue)

    # ── Tray ───────────────────────────────────────────────────

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
        self.tray_icon = pystray.Icon("voice_input", create_tray_icon(), "语音识别输入", menu)
        self.tray_icon.run()

    def on_close(self):
        self.running = False
        if self.tray_icon:
            self.tray_icon.stop()
        self.root.destroy()

# ── Entry point ────────────────────────────────────────────────────

if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceInputApp(root)
    root.mainloop()

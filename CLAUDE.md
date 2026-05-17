# Windows 离线流式语音识别应用

## 项目概述

基于 Vosk 的 Windows 本地语音识别 GUI 应用。流式识别，边说边出字，实时输入到光标位置。完全离线。

## 技术架构

- **GUI**: tkinter
- **语音识别**: Vosk (Kaldi 引擎)
- **流式处理**: PyAudio 实时读取 → Vosk AcceptWaveform → PartialResult 即时出字
- **文字输入**: Windows SendInput API (Unicode)
- **系统托盘**: pystray + PIL

## 关键文件

| 文件 | 说明 |
|------|------|
| `speech_recognition_app.py` | 主程序，GUI + VoskStreamEngine + 托盘 |
| `speech_recognition_app.spec` | PyInstaller 打包配置 |
| `config.json` | 用户配置（停止词） |
| `build.bat` | 一键打包脚本 |

## 模型加载优先级

```
1. <exe目录>/vosk_model/     → 外挂模型（优先，可换大模型）
2. <_MEIPASS>/vosk_model/    → 内嵌 small-cn 模型（备用）
```

## 打包注意事项

1. **干净 venv** — 避免 conda 污染，exe ~79MB
2. **Vosk 原生 DLL** — 必须放到 `vosk/` 子目录，否则 libvosk.dll 找不到依赖 (error 0x7e)
3. **binaries 目标路径 = vosk** — 4 个 DLL (libvosk, libstdc++-6, libgcc, libwinpthread) 必须同目录
4. **console=False** — GUI 应用
5. **模型 datas** — `('vosk_model', 'vosk_model')` 把模型目录打包进 _MEIPASS

## 文件路径逻辑

```
frozen (exe):
  - 配置文件: <exe目录>/config.json              → 可读写
  - 外挂模型: <exe目录>/vosk_model/              → 优先使用
  - 内嵌模型: <_MEIPASS>/vosk_model/             → 只读，备用
  - 历史记录: <exe目录>/recognition_history.txt  → 可读写
  - 调试日志: <exe目录>/debug.log                → 引擎诊断

开发模式:
  - 所有文件: <脚本目录>/                         → 可读写
```

## 关键依赖

```
vosk>=0.3.45          # 离线流式识别
pyaudio>=0.2.14       # 音频采集
pystray>=0.19.5       # 系统托盘
Pillow>=10.0.0        # 托盘图标
pyautogui>=0.9.54     # 备选输入
pyperclip>=1.11.0     # 剪贴板
```

## 已知问题

- Vosk small-cn 模型准确度有限，输出带空格已通过 `.replace(" ", "")` 去除
- 外挂完整模型 (vosk-model-cn-0.22) 可显著提升效果，解压后 ~2GB

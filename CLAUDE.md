# Windows 离线流式语音识别应用

## 项目概述

基于 Vosk 的 Windows 本地语音识别 GUI 应用。流式识别，边说边出字，实时输入到光标位置。完全离线运行，无需联网。

## 技术架构

- **GUI**: tkinter (Python 内置)
- **语音识别**: Vosk (Kaldi 引擎，vosk-model-small-cn-0.22)
- **流式处理**: PyAudio 实时读取音频块 → Vosk AcceptWaveform → PartialResult 秒出字
- **文字输入**: Windows SendInput API (支持 Unicode)
- **系统托盘**: pystray + PIL

## 关键文件

| 文件 | 说明 |
|------|------|
| `speech_recognition_app.py` | 主程序，GUI + VoskStreamEngine + 托盘 |
| `speech_recognition_app.spec` | PyInstaller 打包配置 |
| `config.json` | 用户配置（停止词） |
| `build.bat` | 一键打包脚本 |

## 打包注意事项

1. **使用干净 venv** — 避免 conda 环境的多余依赖污染，exe 大小 ~66MB
2. **模型内嵌** — Vosk CN 模型通过 `datas` 打包进 exe
3. **console=False** — GUI 应用，不显示控制台
4. **无需环境变量** — Vosk 没有 OpenMP DLL 冲突问题，不需要 `KMP_DUPLICATE_LIB_OK`

## 文件路径逻辑

```
frozen (exe):
  - 配置文件: <exe目录>/config.json       → 可读可写
  - 模型文件: <_MEIPASS>/vosk_model/      → 只读
  - 历史记录: <exe目录>/recognition_history.txt → 可读可写

开发模式 (python):
  - 所有文件: <脚本目录>/                  → 可读可写
```

## 关键依赖

```
vosk>=0.3.45               # 离线流式语音识别
pyaudio>=0.2.14            # 音频采集
pystray>=0.19.5            # 系统托盘
Pillow>=10.0.0             # 托盘图标
pyautogui>=0.9.54          # 备选输入方式
pyperclip>=1.11.0          # 剪贴板操作
```

# Windows 离线语音识别应用

## 项目概述

基于 faster-whisper 的 Windows 本地语音识别 GUI 应用。持续监听麦克风，实时将语音转为文字并自动输入到光标位置。完全离线运行，无需联网。

## 技术架构

- **GUI**: tkinter (Python 内置)
- **语音识别**: faster-whisper (CTranslate2 CPU 推理, tiny 模型)
- **音频输入**: PyAudio + speech_recognition
- **文字输入**: Windows SendInput API (支持 Unicode)
- **系统托盘**: pystray + PIL

## 关键文件

| 文件 | 说明 |
|------|------|
| `speech_recognition_app.py` | 主程序，包含 GUI、引擎、托盘逻辑 |
| `speech_recognition_app.spec` | PyInstaller 打包配置 |
| `config.json` | 用户配置文件（停止词、语言等） |
| `build.bat` | 一键打包脚本 |

## 打包注意事项

1. **KMP_DUPLICATE_LIB_OK=TRUE** — 必须设置此环境变量，否则 faster_whisper 和 torch 的 OpenMP DLL 冲突会导致启动崩溃（exit code 3）
2. **console=False** — GUI 应用，不显示控制台窗口
3. **排除 torch 子模块** — 打包时排除 CUDA/distributed/ONNX 等不需要的 torch 子包，将 exe 从数 GB 缩减到 ~350MB
4. **模型内嵌** — tiny 模型文件（~75MB）通过 `datas` 参数打包进 exe，确保其离线可用
5. **文件路径** — 通过 `sys.frozen` 判断是否为打包后的 exe，配置文件读写使用 exe 同级目录，模型读取使用 `_MEIPASS`

## 运行时的文件路径逻辑

```
frozen (exe):
  - 配置文件: <exe目录>/config.json       → 可读可写
  - 模型文件: <_MEIPASS>/whisper_model/   → 只读
  - 历史记录: <exe目录>/recognition_history.txt → 可读可写

开发模式 (python):
  - 所有文件: <脚本目录>/                  → 可读可写
```

## 关键依赖

```
faster-whisper>=1.0.0    # 离线语音识别
SpeechRecognition==3.10.0 # 麦克风管理和音频处理
pyaudio==0.2.14           # 音频输入
pystray==0.19.5           # 系统托盘
Pillow>=10.0.0            # 托盘图标绘制
pyautogui==0.9.54         # 键盘输入(备选)
pyperclip==1.11.0         # 剪贴板(备选)
```

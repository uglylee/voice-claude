# 离线语音识别输入工具

Windows 本地语音识别应用，完全离线运行，无需联网。说出的话实时转为文字，自动输入到任意光标位置。

## 特性

- 完全离线 — 基于 faster-whisper 本地推理，无需联网
- 持续识别 — 启动后持续监听，说出停止词自动结束
- 自动输入 — 识别结果直接输入到当前光标位置（支持中文/英文/多语言）
- 系统托盘 — 可最小化到托盘后台运行
- 自定义停止词 — 自由设置触发停止的词汇

## 系统要求

- Windows 10 或更高
- 麦克风

## 快速开始

### 下载即用（推荐）

从 [Releases](../../releases) 下载 `语音识别.exe`，双击运行。

### 从源码运行

```bash
pip install -r requirements.txt
python speech_recognition_app.py
```

### 打包为 exe

```bash
# 需先安装依赖
pip install -r requirements.txt
pip install pyinstaller

# 设置环境变量并打包
set KMP_DUPLICATE_LIB_OK=TRUE
pyinstaller speech_recognition_app.spec --clean --noconfirm
```

打包输出在 `dist/语音识别.exe`。

## 使用说明

1. 启动应用
2. 点击 **启动引擎**，等待模型加载（首次约 5-10 秒）
3. 对着麦克风说话，识别的文字会自动输入到光标位置
4. 说出停止词（默认 `结束输入`）停止识别
5. 可在设置中自定义停止词

## 技术栈

| 组件 | 用途 |
|------|------|
| faster-whisper (tiny) | 本地语音识别引擎 |
| CTranslate2 | CPU 推理加速 |
| tkinter | GUI 界面 |
| PyAudio | 麦克风采集 |
| pystray | 系统托盘 |

## 项目结构

```
voice-claude/
├── speech_recognition_app.py   # 主程序
├── speech_recognition_app.spec # PyInstaller 打包配置
├── config.json                 # 用户配置
├── requirements.txt            # Python 依赖
└── build.bat                   # 打包批处理脚本
```

## 许可证

MIT

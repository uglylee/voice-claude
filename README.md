# 离线流式语音识别输入工具

Windows 本地语音识别应用，流式识别，边说边出字，完全离线运行。

## 特性

- 流式识别 — 边说边出字，不是说完再识别
- 完全离线 — 基于 Vosk 本地推理，无需联网
- 自动输入 — 识别结果直接输入到光标位置
- 系统托盘 — 最小化到托盘后台运行
- 自定义停止词 — 配置触发停止的词汇
- 轻量 — 仅 66MB

## 系统要求

- Windows 10 或更高
- 麦克风

## 快速开始

### 下载即用

从 [Releases](../../releases) 下载 `语音识别.exe`，双击运行。

### 从源码运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 下载中文模型
# 从 https://alphacephei.com/vosk/models 下载 vosk-model-small-cn-0.22.zip
# 解压到项目目录，重命名为 vosk_model

# 3. 运行
python speech_recognition_app.py
```

### 打包为 exe

```bash
pip install -r requirements.txt pyinstaller
pyinstaller speech_recognition_app.spec --clean --noconfirm
```

输出：`dist/语音识别.exe`

## 使用说明

1. 启动应用，点击 **启动引擎**
2. 对着麦克风说话，文字实时出现在状态栏
3. 每句结束自动输入到光标位置，开始下一句
4. 说出停止词（默认 `结束输入`）停止识别

## 技术栈

| 组件 | 用途 |
|------|------|
| Vosk | 本地流式语音识别引擎 |
| PyAudio | 麦克风采集 |
| tkinter | GUI 界面 |
| pystray | 系统托盘 |
| SendInput | Windows Unicode 输入 |

## 项目结构

```
voice-claude/
├── speech_recognition_app.py   # 主程序
├── speech_recognition_app.spec # PyInstaller 打包配置
├── config.json                 # 用户配置
├── requirements.txt            # Python 依赖
└── build.bat                   # 打包脚本
```

## 许可证

MIT

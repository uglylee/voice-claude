# 离线流式语音识别输入

Windows 本地语音识别，边说边出字，完全离线。

## 特性

- 流式识别 — 边说边出字
- 完全离线 — Vosk 本地推理，无需联网
- 自动输入 — 识别结果直接输入到光标位置
- 系统托盘 — 最小化后台运行
- 自定义停止词

## 下载

从 [Releases](../../releases) 下载最新版 `语音识别.exe`（79MB），双击运行。

## 提升识别效果

内置 small-cn 模型（42MB），如需更高准确度：

1. 下载 [vosk-model-cn-0.22](https://alphacephei.com/vosk/models/vosk-model-cn-0.22.zip)（1.4GB）
2. 解压重命名为 `vosk_model`
3. 放到 `语音识别.exe` 同级目录
4. 重启应用自动使用新模型

## 从源码运行

```bash
pip install -r requirements.txt
# 下载中文模型解压为 vosk_model
python speech_recognition_app.py
```

## 打包

```bash
pip install -r requirements.txt pyinstaller
# 确保 vosk_model 目录在项目根目录
pyinstaller speech_recognition_app.spec --clean --noconfirm
# 输出: dist/语音识别.exe
```

## 使用

1. 启动 → 点击「启动引擎」
2. 说话，实时出字，每句结束自动输入
3. 说出「结束输入」停止

## 技术栈

| 组件 | 用途 |
|------|------|
| Vosk | 本地流式语音识别 |
| PyAudio | 麦克风采集 |
| tkinter | GUI 界面 |
| pystray | 系统托盘 |
| SendInput | Unicode 输入 |

## 许可证

MIT

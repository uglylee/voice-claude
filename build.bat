@echo off
REM 语音识别应用 - 打包脚本
REM 这个脚本会将 Python 应用转换为可执行的 Windows exe 文件

echo.
echo ================================
echo  开始构建 Windows exe 应用...
echo ================================
echo.

REM 检查 PyInstaller 是否已安装
python -m pip show pyinstaller > nul 2>&1
if errorlevel 1 (
    echo 正在安装 PyInstaller...
    pip install PyInstaller
)

REM 构建 exe
echo 正在构建应用...
PyInstaller --onefile ^
    --windowed ^
    --icon=NONE ^
    --name="语音识别" ^
    --add-data="speech_recognition_app.py:." ^
    speech_recognition_app.py

echo.
echo ================================
echo  构建完成！
echo ================================
echo.
echo exe 文件位置: dist\语音识别.exe
echo.
pause

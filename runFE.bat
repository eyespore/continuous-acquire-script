@echo off
REM 前端执行脚本
echo Activating project python virtual environment
call .venv\Script\activate
call cd pycomm
call python app_fe.py

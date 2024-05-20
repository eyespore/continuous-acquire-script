@echo off
REM 项目初始化脚本
for /f "tokens=2 delims= " %%i in ('python --version') do set PYTHON_VERSION=%%i
echo Current Python version: %PYTHON_VERSION%

echo Start constructing python virtual environment...
call python -m venv .venv
echo Done

echo Downloading project requirement...
call python install -r requirement
echo Done

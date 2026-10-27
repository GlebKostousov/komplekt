@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
py -3.13 --version >nul 2>&1
if errorlevel 1 goto try_python
py -3.13 scripts\run.py
goto finished
:try_python
python --version >nul 2>&1
if errorlevel 1 goto missing_python
python scripts\run.py
goto finished
:missing_python
echo Для запуска нужен Python 3.13. Инструкция есть в README.md.
echo Скачать: https://www.python.org/downloads/windows/
:finished
pause

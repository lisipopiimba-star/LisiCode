@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
where py >nul 2>nul
if not errorlevel 1 goto use_py
where python >nul 2>nul
if not errorlevel 1 goto use_python
echo [ERROR] Python 3 не найден. Установи Python 3 и включи Add Python to PATH.
pause
exit /b 1
:use_py
py -3 --version
if errorlevel 1 goto python_error
py -3 -m pip install -r requirements.txt
if errorlevel 1 goto pip_error
py -3 lisicode.py
goto finish
:use_python
python --version
if errorlevel 1 goto python_error
python -m pip install -r requirements.txt
if errorlevel 1 goto pip_error
python lisicode.py
goto finish
:python_error
echo [ERROR] Не удалось запустить Python 3.
goto finish
:pip_error
echo [ERROR] Не удалось установить зависимости. Проверь интернет и pip.
:finish
echo.
echo LisiCode завершил работу. Код выхода: %errorlevel%
pause
endlocal

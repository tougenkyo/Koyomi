@echo off
rem ------------------------------------------------------------------
rem  こよみアラーム を使えるようにする。
rem
rem    install.bat                そのまま用意する
rem    install.bat /noshortcut    ショートカットは作らない
rem
rem  このファイルは Shift-JIS(cp932) で書いてあります。
rem ------------------------------------------------------------------
chcp 932 >nul
setlocal
cd /d "%~dp0"
title こよみアラーム セットアップ

echo.
echo   こよみアラーム セットアップ
echo   ==========================================
echo.

rem ---- 使う Python を探す ------------------------------------------
set "PY=python"
%PY% -c "import sys" >nul 2>&1
if not errorlevel 1 goto FOUND

set "PY=py -3"
%PY% -c "import sys" >nul 2>&1
if not errorlevel 1 goto FOUND

echo   Python が見つかりませんでした。
echo.
echo   https://www.python.org/ から 3.10 以降を入れてください。
echo   途中に出てくる「Add python.exe to PATH」に印を付けるのを忘れずに。
echo.
pause
exit /b 1

:FOUND
for /f "delims=" %%P in ('%PY% -c "import sys;print(sys.executable)"') do set "WHICH=%%P"
for /f "delims=" %%V in ('%PY% -V') do set "VER=%%V"
echo   使う Python : %WHICH%
echo   その版      : %VER%
echo.
echo   ここに部品を入れます。別の Python に入れたいときは、
echo   いったん閉じて、その Python から実行し直してください。
echo.

rem ---- pip を新しくする（うまくいかなくても先へ進む）----------------
echo   [1/4] pip を新しくします
echo   ------------------------------------------
%PY% -m pip install --upgrade pip
echo.

rem ---- 必要なものを入れる ------------------------------------------
echo   [2/4] 必要なものを入れます
echo   ------------------------------------------
%PY% -m pip install -r requirements.txt
if errorlevel 1 goto FAILED
echo.

rem ---- ちゃんと入ったか確かめる ------------------------------------
echo   [3/4] 入ったかどうか確かめます
echo   ------------------------------------------
%PY% -c "import PySide6, jpholiday, pygame" >nul 2>&1
if errorlevel 1 goto FAILED
echo   そろいました。
echo.

rem ---- 起動用のショートカット --------------------------------------
rem  ここは尋ねない。パイプやファイルから流し込まれると、
rem  尋ねたつもりが勝手に決まってしまうため。要らない人は /noshortcut。
if /i "%~1"=="/noshortcut" goto DONE
echo   [4/4] ショートカットを作ります
echo   ------------------------------------------
%PY% tools/make_shortcut.py
echo   要らないときは、そのファイルを消すか、
echo   install.bat /noshortcut で実行し直してください。
echo.

:DONE
echo   ==========================================
echo   準備ができました。
echo.
echo   ショートカット、または次のどちらかで始められます。
echo     pythonw run.pyw   ふだんはこちら（黒い窓が出ません）
echo     python  run.pyw   コンソールを付けて始める（不具合を追うとき）
echo.
pause
exit /b 0

:FAILED
echo.
echo   ==========================================
echo   うまくいきませんでした。
echo.
echo   ネットにつながっているか、
echo   別の Python が混ざっていないかを確かめてください。
echo.
pause
exit /b 1

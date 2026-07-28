@echo off
chcp 65001 >nul
title Terminal Ringan
cd /d "%~dp0"

rem  Lingkungan Python sengaja diletakkan DI LUAR OneDrive.
rem  Isinya ribuan berkas kecil — kalau ditaruh di dalam folder OneDrive,
rem  sinkronisasi akan berjalan terus-menerus dan memberatkan komputer.
set "VENV=%LOCALAPPDATA%\terminal-ringan-venv"

echo.
echo   ==========================================
echo      TERMINAL RINGAN
echo   ==========================================
echo.

rem --- cari Python ---
set "PY="
where py >nul 2>nul && set "PY=py"
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo   [X] Python tidak ditemukan di komputer ini.
    echo.
    echo       Pasang dari https://www.python.org/downloads/
    echo       Saat memasang, centang "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

rem --- siapkan lingkungan ---
if not exist "%VENV%\Scripts\python.exe" (
    echo   [1/3] Menyiapkan lingkungan Python...
    echo         ^(sekali saja, sekitar 2-3 menit^)
    %PY% -m venv "%VENV%"
    if errorlevel 1 (
        echo   [X] Gagal membuat lingkungan Python.
        pause
        exit /b 1
    )
) else (
    echo   [1/3] Lingkungan Python sudah siap.
)

echo   [2/3] Memeriksa pustaka...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip --quiet --disable-pip-version-check
"%VENV%\Scripts\python.exe" -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo   [X] Gagal memasang pustaka. Periksa koneksi internet Anda.
    pause
    exit /b 1
)

echo   [3/3] Menjalankan terminal...
echo.
echo   Browser akan terbuka sendiri di http://localhost:8501
echo   Untuk berhenti: tutup jendela ini, atau tekan Ctrl+C.
echo.

"%VENV%\Scripts\python.exe" -m streamlit run terminal_ringan.py

echo.
echo   Terminal berhenti.
pause

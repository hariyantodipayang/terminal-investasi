#!/usr/bin/env bash
# Terminal Investasi — peluncur untuk macOS dan Linux
# Launcher for macOS and Linux
#
# Cara pakai / Usage:
#     chmod +x MULAI.sh     (sekali saja / once)
#     ./MULAI.sh

set -u
cd "$(dirname "$0")"

# Lingkungan Python sengaja diletakkan di luar folder aplikasi, supaya folder
# yang disinkronkan ke cloud tidak dipenuhi ribuan berkas kecil.
VENV="${HOME}/.terminal-investasi-venv"

echo
echo "  =========================================="
echo "     TERMINAL INVESTASI"
echo "  =========================================="
echo

# --- cari Python / find Python ---
PY=""
for kandidat in python3 python; do
    if command -v "$kandidat" >/dev/null 2>&1; then
        if "$kandidat" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
            PY="$kandidat"
            break
        fi
    fi
done

if [ -z "$PY" ]; then
    echo "  [X] Python 3.9 atau lebih baru tidak ditemukan."
    echo "      Python 3.9 or newer not found."
    echo
    echo "      macOS  : brew install python3"
    echo "      Ubuntu : sudo apt install python3 python3-venv python3-pip"
    echo "      Fedora : sudo dnf install python3 python3-pip"
    echo
    exit 1
fi

echo "  Python  : $($PY --version 2>&1)"

# --- siapkan lingkungan / prepare environment ---
if [ ! -x "${VENV}/bin/python" ]; then
    echo "  [1/3] Menyiapkan lingkungan Python (sekali saja, 2-3 menit)..."
    echo "        Setting up Python environment (one time, 2-3 minutes)..."
    if ! "$PY" -m venv "$VENV"; then
        echo
        echo "  [X] Gagal membuat lingkungan Python."
        echo "      Failed to create the Python environment."
        echo "      Ubuntu/Debian: sudo apt install python3-venv"
        exit 1
    fi
else
    echo "  [1/3] Lingkungan Python sudah siap."
fi

echo "  [2/3] Memeriksa pustaka / checking libraries..."
"${VENV}/bin/python" -m pip install --upgrade pip --quiet --disable-pip-version-check
if ! "${VENV}/bin/python" -m pip install -r requirements.txt --quiet --disable-pip-version-check; then
    echo
    echo "  [X] Gagal memasang pustaka. Periksa koneksi internet Anda."
    echo "      Failed to install libraries. Check your internet connection."
    exit 1
fi

echo "  [3/3] Menjalankan terminal / starting..."
echo
echo "  Browser akan terbuka di http://localhost:8501"
echo "  Untuk berhenti: tekan Ctrl+C"
echo

exec "${VENV}/bin/python" -m streamlit run terminal_ringan.py

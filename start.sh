#!/bin/bash
# Knowledge Lab · Quick Start

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║     Knowledge Lab · Learning Tool    ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

cd "$(dirname "$0")"

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 not found. Install: https://www.python.org/downloads/"
    exit 1
fi

# First run: configure
if [ ! -f .env ]; then
    echo "[SETUP] First run — configuring..."
    echo ""
    read -p "Enter your DeepSeek API Key: " API_KEY
    echo "LLM_API_KEY=$API_KEY" > .env
    echo "VAULT_PATH=./vault" >> .env
    echo ""
    echo "[OK] Configuration saved to .env"
fi

# Install dependencies if needed
python3 -c "import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "[SETUP] Installing dependencies..."
    python3 -m pip install -r requirements.txt -q
    echo "[OK] Dependencies installed"
fi

# Create vault structure
mkdir -p vault/00_学习笔记 vault/01_错题本 vault/06_产品层
cp -n templates/* vault/00_学习笔记/ 2>/dev/null
cp -n templates/* vault/01_错题本/ 2>/dev/null
cp -n standards/* vault/06_产品层/ 2>/dev/null

# Load .env
export $(grep -v '^#' .env | xargs)

echo ""
echo "  Starting server at http://localhost:5050"
echo ""

# Open browser
if command -v open &> /dev/null; then
    open http://localhost:5050
elif command -v xdg-open &> /dev/null; then
    xdg-open http://localhost:5050
fi

python3 server/quiz_server.py --port 5050

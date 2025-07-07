#!/bin/bash

# スクリプトのディレクトリに移動
cd "$(dirname "$0")"

# 仮想環境を有効化
source venv/bin/activate

# .envファイルを読み込み（必要に応じて）
export $(cat .env | grep -v '^#' | xargs)

# Pythonスクリプトを実行
python main.py

# 仮想環境を無効化（オプション）
deactivate

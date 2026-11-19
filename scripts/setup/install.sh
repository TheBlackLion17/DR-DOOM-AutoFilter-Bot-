#!/usr/bin/env bash
set -euo pipefail
apt-get update
apt-get install -y python3 python3-venv python3-dev build-essential mysql-server
systemctl enable --now mysql
python3 -m venv venv
./venv/bin/pip install --upgrade pip
./venv/bin/pip install -r requirements.txt
if [[ ! -f .env ]]; then cp .env.example .env; chmod 600 .env; fi
printf '\nInstalled. Configure .env and MySQL credentials before starting.\n'

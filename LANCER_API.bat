@echo off
title API - Site Web
cd /d "M:\Data_planes_project\backend"
python -m uvicorn api:app --host 127.0.0.1 --port 8000
pause
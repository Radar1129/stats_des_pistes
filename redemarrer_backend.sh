#!/bin/bash
pkill -9 -f uvicorn
pkill -9 -f api.py
rm -f /home/ubuntu/stats_des_pistes/backend/scraped_cache.json
cd /home/ubuntu/stats_des_pistes/backend || exit 1
nohup python3 -m uvicorn api:app --host 127.0.0.1 --port 8000 > uvicorn.log 2>&1 &
sleep 2

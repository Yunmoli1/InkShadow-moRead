#!/bin/bash
# Restart the MoRead backend server (kills old listener, starts fresh)
for pid in $(netstat -ano | grep ":8686" | grep "LISTENING" | sed 's/.*LISTENING *//;s/ .*//' | sort -u); do
  taskkill //F //PID "$pid" 2>/dev/null
done
powershell -Command "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Where-Object { \$_.CommandLine -like '*uvicorn*' -or \$_.CommandLine -like '*spawn_main*moread*' } | ForEach-Object { Stop-Process -Id \$_.ProcessId -Force -ErrorAction SilentlyContinue }" 2>/dev/null
sleep 1
cd "D:\ZCode-墨读\backend"
exec python -m uvicorn app.main:app --host 127.0.0.1 --port 8686

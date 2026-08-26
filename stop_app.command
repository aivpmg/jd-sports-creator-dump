#!/bin/bash
cd "$(dirname "$0")"
echo "Stopping JD Sports Creator Dump..."
pkill -f "streamlit run app.py"
echo "Stopped successfully! 💖"
sleep 1
osascript -e 'tell application "Terminal" to close first window' &

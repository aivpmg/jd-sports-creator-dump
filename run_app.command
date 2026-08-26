#!/bin/bash
cd "$(dirname "$0")"
# Run streamlit in the background and redirect output to a log file
nohup python3 -m streamlit run app.py --server.port 8502 > streamlit.log 2>&1 &
# Wait 2 seconds for the server to start
sleep 2
# Open the browser automatically
open http://localhost:8502
# Close the terminal window instantly
osascript -e 'tell application "Terminal" to close first window' &

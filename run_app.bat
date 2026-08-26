@echo off
echo ✨ Starting JD Sports Creator Dump... 💖
echo Installing/updating required packages...
python -m pip install streamlit pandas google-api-python-client google-auth-httplib2 google-auth-oauthlib
echo Starting Streamlit server...
python -m streamlit run app.py
pause

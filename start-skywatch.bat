@echo off
cd /d C:\Users\dell\skywatch-pilot
call venv\Scripts\activate.bat
echo.
echo SkyWatch Pilot starting...
echo Open in browser: http://localhost:8080/login
echo Keep this window OPEN while using the app.
echo.
python -m app
pause

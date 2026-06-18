@echo off
REM Cleo Tutor launcher (Windows)

if "%ANTHROPIC_API_KEY%"=="" (
  echo.
  echo   Set your API key first:
  echo   set ANTHROPIC_API_KEY=sk-ant-...
  echo.
  pause
  exit /b 1
)

pip install -r requirements.txt -q
python app.py

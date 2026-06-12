@echo off
chcp 65001 >nul
title Trading Picks - Intraday & Swing
color 0A

echo.
echo =============================================
echo   TRADING PICKS — Intraday & Swing
echo =============================================
echo.

echo Installing dependencies...
pip install streamlit requests pandas yfinance numpy pytz --quiet
echo Done.
echo.

echo Opening: http://localhost:8509
echo First load ~20 seconds
echo Press Refresh Picks button for latest data
echo.

cd /d "%~dp0"
python -m streamlit run trading_app.py --server.port=8509 --browser.gatherUsageStats=false

pause

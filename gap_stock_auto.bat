@echo off
chcp 65001 >nul
title KIS Auto Trading Bot
echo ===================================================
echo 🚀 한국투자증권(KIS) 갭메우기 스케줄러 봇 🚀
echo ===================================================
echo [안내] kis_secret.json 파일에 앱키/시크릿키/계좌번호가 
echo 올바르게 입력되어 있는지 확인해주세요.
echo 모의투자 URL(openapivts)이 기본 설정되어 있습니다.
echo.
python gap_stock_auto.py
pause

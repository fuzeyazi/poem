@echo off
title poetry-spring2 stop-all
setlocal enabledelayedexpansion

set "MYSQL_ADMIN=C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqladmin.exe"
set "MYSQL_PWD=%MYSQL_PASSWORD%"
set "REDIS_CLI=E:\redis\redis-cli.exe"

echo ============================================
echo   poetry-spring2 full stack stop
echo   order: gateway -^> potry-service -^> Nacos -^> Redis -^> MySQL
echo ============================================

call :kill_port 9080 poetry-gateway
call :kill_port 8081 potry-service
call :kill_port 8848 Nacos

rem Redis: graceful shutdown first, force kill as fallback
call :already 6379
if "!SKIP!"=="1" (
    echo [stop] Redis graceful shutdown
    "%REDIS_CLI%" shutdown >nul 2>&1 || call :kill_port 6379 Redis
    ping -n 2 127.0.0.1 >nul
) else (
    echo [skip] Redis 6379 not running
)

rem MySQL: mysqladmin graceful shutdown (avoid data risk of hard kill)
call :already 3306
if "!SKIP!"=="1" (
    echo [stop] MySQL mysqladmin shutdown
    "%MYSQL_ADMIN%" -uroot -p%MYSQL_PWD% shutdown >nul 2>&1
    if errorlevel 1 call :kill_port 3306 MySQL
) else (
    echo [skip] MySQL 3306 not running
)

echo done.
endlocal
exit /b 0

rem kill_port <port> <name>: find PID by listening port and taskkill
:kill_port
set "FOUND=0"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":%~1 " ^| findstr /C:"LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1 && set "FOUND=1"
)
if "%FOUND%"=="1" (echo [stop] %~2 :%~1 killed) else (echo [skip] %~2 :%~1 not running)
exit /b 0

rem already <port>: set SKIP=1 if port is listening, else SKIP=0
:already
set "SKIP=0"
netstat -ano | findstr /C:":%~1 " | findstr /C:"LISTENING" >nul 2>&1 && set "SKIP=1"
exit /b 0

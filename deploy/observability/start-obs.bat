@echo off
title poetry observability start/stop
setlocal enabledelayedexpansion

rem ============ 可观测性栈裸跑启停(本机 Docker 引擎不稳时的替代方案) ============
rem 二进制目录(首次需下载解压, 见 deploy/observability/README.md)
set "OBS_HOME=E:\javatexts\observability"
set "PROM_DIR=%OBS_HOME%\prometheus-2.54.1.windows-amd64"
set "GRAF_DIR=%OBS_HOME%\grafana-v11.3.0"

if "%~1"=="stop" goto stop

echo [start] Prometheus :9091
start "poetry-prometheus" /D "%PROM_DIR%" cmd /c "prometheus.exe --config.file=prometheus.yml --web.listen-address=127.0.0.1:9091 --storage.tsdb.path=data > ..\prom-run.log 2>&1"

echo [start] Grafana :3001 (admin/poetry)
rem provisioning 指向裸跑副本(datasource=127.0.0.1:9091, dashboards指向仓库目录),子进程继承
set "GF_PATHS_PROVISIONING=E:\javatexts\observability\gprovisioning"
set "GF_SECURITY_ADMIN_PASSWORD=poetry"
set "GF_SERVER_HTTP_PORT=3001"
start "poetry-grafana" /D "%GRAF_DIR%" cmd /c "bin\grafana-server.exe > ..\grafana-run.log 2>&1"

echo.
echo URLs: Grafana http://localhost:3001 (admin/poetry)   Prometheus http://localhost:9091
echo dashboards auto-provisioned from repo deploy/observability/grafana/dashboards
goto :eof

:stop
call :kill 9091 poetry-prometheus
call :kill 3001 poetry-grafana
goto :eof

:kill
set "FOUND=0"
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /C:":%~1 " ^| findstr /C:"LISTENING"') do (
    taskkill /F /PID %%p >nul 2>&1 && set "FOUND=1"
)
if "!FOUND!"=="1" (echo [stop] %~2 :%~1 killed) else (echo [skip] %~2 :%~1 not running)
exit /b 0

@echo off
title poetry-spring2 start-all
setlocal enabledelayedexpansion

rem ============ paths (see COORDINATION.md section 5) ============
set "MYSQLD=C:\Program Files\MySQL\MySQL Server 8.4\bin\mysqld.exe"
set "MYSQL_DATA=C:\Users\fuze\mysql-data"
set "REDIS_HOME=E:\redis"
set "NACOS_BIN=E:\javatexts\nacos-dl\nacos\bin"
set "JAVA17=E:\java\IntelliJ IDEA Ultimate\jbr"
set "REPO=E:\javatexts\poetry-spring2"
rem Nacos startup.cmd needs JAVA_HOME -> JDK17 (inherited by child process)
set "JAVA_HOME=%JAVA17%"

echo ============================================
echo   poetry-spring2 full stack start
echo   order: MySQL -^> Redis -^> Nacos -^> potry-service -^> gateway
echo   idempotent: skip if port already listening
echo ============================================

rem ---------- 1. MySQL 8.4 : 3306 ----------
call :already 3306
if "!SKIP!"=="1" goto redis
echo [start] MySQL 8.4
start "MySQL84" "%MYSQLD%" --datadir=%MYSQL_DATA% --port=3306
call :wait 3306 20 MySQL

:redis
rem ---------- 2. Redis : 6379 ----------
call :already 6379
if "!SKIP!"=="1" goto nacos
echo [start] Redis
start "Redis" /D "%REDIS_HOME%" "%REDIS_HOME%\redis-server.exe" "%REDIS_HOME%\redis.windows.conf"
call :wait 6379 10 Redis

:nacos
rem ---------- 3. Nacos : 8848 ----------
call :already 8848
if "!SKIP!"=="1" goto service
echo [start] Nacos standalone
start "Nacos" /D "%NACOS_BIN%" "%NACOS_BIN%\startup.cmd" -m standalone
call :wait 8848 30 Nacos

:service
rem ---------- 4. potry-service : 8081 ----------
call :already 8081
if "!SKIP!"=="1" goto gateway
if not exist "%REPO%\potry-service\target\potry-service-0.0.1-SNAPSHOT.jar" goto no_svc_jar
echo [start] potry-service 8081
start "potry-service" /D "%REPO%\potry-service\target" cmd /c "java -jar potry-service-0.0.1-SNAPSHOT.jar > ..\..\run-java.log 2>&1"
call :wait 8081 40 potry-service
goto gateway

:no_svc_jar
echo [ERROR] potry-service jar missing. Build first: mvn -pl potry-service -am package -DskipTests

:gateway
rem ---------- 5. poetry-gateway : 9080 ----------
call :already 9080
if "!SKIP!"=="1" goto summary
if not exist "%REPO%\poetry-gateway\target\poetry-gateway-0.0.1-SNAPSHOT.jar" goto no_gw_jar
echo [start] poetry-gateway 9080
start "poetry-gateway" /D "%REPO%\poetry-gateway\target" cmd /c "java -jar poetry-gateway-0.0.1-SNAPSHOT.jar > ..\..\run-gw.log 2>&1"
call :wait 9080 20 poetry-gateway
goto summary

:no_gw_jar
echo [ERROR] poetry-gateway jar missing. Build first: mvn -pl poetry-gateway -am package -DskipTests

:summary
echo.
echo ============ health summary ============
set "FAIL=0"
call :already 3306
if "!SKIP!"=="1" (echo   [ OK ] MySQL         :3306) else echo   [FAIL] MySQL         :3306
call :already 6379
if "!SKIP!"=="1" (echo   [ OK ] Redis         :6379) else echo   [FAIL] Redis         :6379
call :already 8848
if "!SKIP!"=="1" (echo   [ OK ] Nacos         :8848) else echo   [FAIL] Nacos         :8848
call :already 8081
if "!SKIP!"=="1" (echo   [ OK ] potry-service :8081) else echo   [FAIL] potry-service :8081
call :already 9080
if "!SKIP!"=="1" (echo   [ OK ] gateway       :9080) else echo   [FAIL] gateway       :9080
call :already 3306
if not "!SKIP!"=="1" set "FAIL=1"
call :already 6379
if not "!SKIP!"=="1" set "FAIL=1"
call :already 8848
if not "!SKIP!"=="1" set "FAIL=1"
call :already 8081
if not "!SKIP!"=="1" set "FAIL=1"
call :already 9080
if not "!SKIP!"=="1" set "FAIL=1"
echo.
if "!FAIL!"=="1" goto partly
echo all services ready.
goto footer
:partly
echo some services NOT ready. check %REPO%\run-java.log / run-gw.log
:footer
echo note: agent(8000) is owned by the agent session, not included. stop all: stop-all.bat
endlocal & exit /b !FAIL!

rem ============ subroutines ============
rem already <port>: set SKIP=1 if port is listening, else SKIP=0
:already
set "SKIP=0"
netstat -ano | findstr /C:":%~1 " | findstr /C:"LISTENING" >nul 2>&1 && set "SKIP=1"
exit /b 0

rem wait <port> <max_tries> <name>: poll every ~2s until port listening
:wait
set /a n=0
:w_loop
ping -n 3 127.0.0.1 >nul
netstat -ano | findstr /C:":%~1 " | findstr /C:"LISTENING" >nul 2>&1
if not errorlevel 1 echo   [ready] %~3 :%~1
if not errorlevel 1 exit /b 0
set /a n+=1
if !n! geq %~2 echo   [timeout] %~3 port %~1 not ready after %~2 tries, continue...
if !n! geq %~2 exit /b 1
goto :w_loop

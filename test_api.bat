@echo off
chcp 65001 >nul

echo === 注册测试用户 ===
curl -s -X POST http://localhost:8080/user/register -H "Content-Type: application/json" -d "{\"username\":\"perfuser\",\"password\":\"123456\"}"
echo.
echo.

echo === 用户登录 ===
curl -s -X POST http://localhost:8080/user/login -H "Content-Type: application/json" -d "{\"username\":\"perfuser\",\"password\":\"123456\"}" > token.txt
echo.
echo.

echo === 提取Token ===
for /f "tokens=2 delims=:" %%a in ('findstr "token" token.txt') do (
    set TOKEN=%%a
)
set TOKEN=%TOKEN:"=%
set TOKEN=%TOKEN: =%
echo Token: %TOKEN%
echo.

echo === 测试无认证接口 ===
echo --- GetCount ---
curl -s -o NUL -w "状态码: %%{http_code}  响应时间: %%{time_total}s\n" http://localhost:8080/user/poetry/GetCount
echo.

echo === 测试需要认证的接口 ===
echo --- GetAllDynasty ---
curl -s -o NUL -w "状态码: %%{http_code}  响应时间: %%{time_total}s\n" -H "token: %TOKEN%" http://localhost:8080/user/poetry/GetAllDynasty
echo.

echo --- GetPoemDateRondom ---
curl -s -o NUL -w "状态码: %%{http_code}  响应时间: %%{time_total}s\n" -H "token: %TOKEN%" http://localhost:8080/user/poetry/GetPoemDateRondom
echo.

echo --- GetPoemPage ---
curl -s -o NUL -w "状态码: %%{http_code}  响应时间: %%{time_total}s\n" -H "token: %TOKEN%" "http://localhost:8080/user/poetry/GetPoemPage?pageNum=1&pageSize=20"
echo.

echo --- GetContentById ---
curl -s -o NUL -w "状态码: %%{http_code}  响应时间: %%{time_total}s\n" -H "token: %TOKEN%" http://localhost:8080/user/poetry/GetContentById/1
echo.

echo --- GetDynastyandpoem ---
curl -s -o NUL -w "状态码: %%{http_code}  响应时间: %%{time_total}s\n" -H "token: %TOKEN%" http://localhost:8080/user/poetry/GetDynastyandpoem
echo.

echo --- GetAllPoemName ---
curl -s -o NUL -w "状态码: %%{http_code}  响应时间: %%{time_total}s\n" -H "token: %TOKEN%" http://localhost:8080/user/poetry/GetAllPoemName
echo.

echo --- GetPoemByDynasty ---
curl -s -o NUL -w "状态码: %%{http_code}  响应时间: %%{time_total}s\n" -H "token: %TOKEN%" "http://localhost:8080/user/poetry/GetPoemBydynasty?dynasty=唐代"
echo.

del token.txt
echo.
echo === 测试完成 ===

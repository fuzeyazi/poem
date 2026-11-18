# -*- coding: utf-8 -*-
"""查询优化前后基线:各接口 30 次延迟采样"""
import sys, time, statistics, requests

BASE = "http://127.0.0.1:8081"
ENDPOINTS = {
    "随机诗GetPoemDateRondom": "/user/poetry/GetPoemDateRondom",
    "推荐好诗GetVeryGoodPoem": "/user/poetry/GetVeryGoodPoem",
    "朝代列表GetAllDynasty":   "/user/poetry/GetAllDynasty",
    "总数GetCount":            "/user/poetry/GetCount",
    "朝代聚合GetDynastyandpoem": "/user/poetry/GetDynastyandpoem",
    "朝代分页(参照)":          "/user/poetry/GetPoemsByDynasty?dynasty=%E5%94%90%E4%BB%A3&pageNum=1&pageSize=20",
}

token = sys.argv[1]
s = requests.Session()
N = 30
for name, path in ENDPOINTS.items():
    lat = []
    for _ in range(3):  # 预热3次
        s.get(BASE + path, headers={"token": token}, timeout=15)
    for _ in range(N):
        t0 = time.time()
        r = s.get(BASE + path, headers={"token": token}, timeout=15)
        lat.append((time.time() - t0) * 1000)
        if r.status_code != 200:
            print(f"  !! {name} HTTP {r.status_code}")
    lat.sort()
    print(f"{name:<24} avg={statistics.mean(lat):>6.1f}ms  P50={lat[N//2]:>6.1f}  P95={lat[int(N*0.95)]:>6.1f}")

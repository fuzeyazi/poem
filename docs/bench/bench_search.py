# -*- coding: utf-8 -*-
"""
搜索接口前置模糊(LIKE %x%) → FULLTEXT ngram 改造专项压测。
用法:
  python bench_search.py latency <token>          # 多关键词单次延迟(30采样)
  python bench_search.py bench <token> <kw> <c1,c2,...>  # GetPoembyTitle 并发
"""
import sys, time, threading, statistics, argparse
import requests

BASE = "http://127.0.0.1:8081"

# (标签, 路径, params) —— 真实用户搜索词
CASES = [
    ("title_黄鹤楼", "/user/poetry/GetPoembyTitle", {"title": "黄鹤楼", "pageNum": 1, "pageSize": 20}),
    ("title_静夜思", "/user/poetry/GetPoembyTitle", {"title": "静夜思", "pageNum": 1, "pageSize": 20}),
    ("title_春",     "/user/poetry/GetPoembyTitle", {"title": "春", "pageNum": 1, "pageSize": 20}),
    ("title_杜甫",   "/user/poetry/GetPoembyTitle", {"title": "杜甫", "pageNum": 1, "pageSize": 20}),
    ("forum_月光",   "/user/luntan/search", {"content": "月光"}),
    ("forum_江南",   "/user/luntan/search", {"content": "江南"}),
]


def get_token():
    r = requests.post(BASE + "/user/login", json={"username": "hud_15605", "password": "123456"}).json()
    return r["data"]["token"]


def latency_all(token):
    for label, path, params in CASES:
        s = requests.Session()
        try:
            for _ in range(3):
                s.get(BASE + path, params=params, headers={"token": token}, timeout=30)
            lat, n_hit = [], None
            for _ in range(30):
                t0 = time.time()
                r = s.get(BASE + path, params=params, headers={"token": token}, timeout=30)
                lat.append((time.time() - t0) * 1000)
                if r.status_code != 200:
                    print(f"  !! {label} status={r.status_code} {r.text[:100]}")
                    break
                d = r.json().get("data")
                if isinstance(d, dict):
                    n_hit = d.get("total")
                elif isinstance(d, list):
                    n_hit = len(d)
            else:
                lat.sort()
                p95 = lat[int(len(lat) * 0.95)]
                print(f"{label:<14} n=30  median={statistics.median(lat):>7.2f}ms  p95={p95:>7.2f}ms  "
                      f"min={lat[0]:.2f}  max={lat[-1]:.2f}  hits={n_hit}  bytes={len(r.content)}")
                continue
            print(f"{label:<14} FAILED")
        except Exception as e:
            print(f"{label:<14} EXC {e}")


def run_level(token, kw, concurrency, duration=15):
    path = "/user/poetry/GetPoembyTitle"
    params = {"title": kw, "pageNum": 1, "pageSize": 20}
    lat, errors, count = [], 0, 0
    stop = time.time() + duration
    lock = threading.Lock()
    sess = threading.local()

    def worker():
        nonlocal errors, count
        try:
            s = sess.s
        except AttributeError:
            s = sess.s = requests.Session()
        while time.time() < stop:
            t0 = time.time()
            try:
                r = s.get(BASE + path, params=params, headers={"token": token}, timeout=30)
                dt = (time.time() - t0) * 1000
                with lock:
                    lat.append(dt); count += 1
                    if r.status_code != 200:
                        errors += 1
            except Exception:
                with lock:
                    errors += 1; count += 1

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(concurrency)]
    t_start = time.time()
    for t in threads: t.start()
    for t in threads: t.join()
    wall = time.time() - t_start

    lat.sort()
    def pct(p): return lat[min(len(lat)-1, int(len(lat)*p))] if lat else -1
    print(f"c={concurrency:>3}  QPS={count/wall:>7.1f}  avg={statistics.mean(lat) if lat else -1:>7.1f}ms  "
          f"P50={pct(0.5):>7.1f}  P95={pct(0.95):>7.1f}  P99={pct(0.99):>7.1f}  err={errors}/{count}", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["latency", "bench"])
    ap.add_argument("token", nargs="?")
    ap.add_argument("kw", nargs="?", default="黄鹤楼")
    ap.add_argument("levels", nargs="?", default="10,50")
    a = ap.parse_args()
    token = a.token or get_token()
    if a.mode == "latency":
        print(f"== 搜索接口单次延迟 (BASE={BASE}) ==")
        latency_all(token)
    else:
        print(f"== 并发压测 GetPoembyTitle kw={a.kw} ==")
        for c in [int(x) for x in a.levels.split(",")]:
            run_level(token, a.kw, c)

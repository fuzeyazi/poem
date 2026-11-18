# -*- coding: utf-8 -*-
"""
ORDER BY RAND() 治理专项压测：6 个随机接口，单次延迟(30采样) + 并发(QPS/P95/P99)。
用法:
  python bench_rand.py latency <token>          # 6 接口单次延迟
  python bench_rand.py bench <token> <path> <c1,c2,...>  # 单接口并发压测
"""
import sys, time, threading, statistics, argparse
import requests

BASE = "http://127.0.0.1:8081"

# (标签, 路径) —— 全部是 ORDER BY RAND() 热路径
ENDPOINTS = [
    ("rhesis_random10", "/user/rhesis/GetRhesisDateRondom"),
    ("rhesis_today1",   "/user/rhesis/GetVeryGoodRhesis"),
    ("poetry_writers",  "/user/poetry/Get?pageNum=1&pageSize=5"),
    ("writer_randpoems", "/user/writer/GetRandomPoems"),
    ("writer_rand5",    "/user/writer/GetRandomWriters"),
    ("luntan_rand5",    "/user/luntan/select/forum"),
]


def get_token():
    # register 接口存量 500(2026-10-24 发现,待修), 暂用固定账号
    r = requests.post(BASE + "/user/login", json={"username": "hud_15605", "password": "123456"}).json()
    return r["data"]["token"]


def latency_all(token):
    """每接口串行 30 次采样(先 3 次预热), 输出中位/P95"""
    for label, path in ENDPOINTS:
        url = BASE + path
        s = requests.Session()
        try:
            for _ in range(3):
                s.get(url, headers={"token": token}, timeout=30)
            lat = []
            for _ in range(30):
                t0 = time.time()
                r = s.get(url, headers={"token": token}, timeout=30)
                lat.append((time.time() - t0) * 1000)
                if r.status_code != 200:
                    print(f"  !! {label} status={r.status_code} body={r.text[:120]}")
                    break
            else:
                lat.sort()
                p95 = lat[int(len(lat) * 0.95)]
                print(f"{label:<18} n=30  median={statistics.median(lat):>7.2f}ms  p95={p95:>7.2f}ms  "
                      f"min={lat[0]:.2f}  max={lat[-1]:.2f}  bytes={len(r.content)}")
                continue
            print(f"{label:<18} FAILED")
        except Exception as e:
            print(f"{label:<18} EXC {e}")


def run_level(token, path, concurrency, duration=15):
    lat, errors, count = [], 0, 0
    stop = time.time() + duration
    lock = threading.Lock()
    sess = threading.local()

    def worker():
        nonlocal errors, count
        url = BASE + path
        try:
            s = sess.s
        except AttributeError:
            s = sess.s = requests.Session()
        while time.time() < stop:
            t0 = time.time()
            try:
                r = s.get(url, headers={"token": token}, timeout=30)
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
    ap.add_argument("path", nargs="?")
    ap.add_argument("levels", nargs="?", default="10,50")
    a = ap.parse_args()
    token = a.token or get_token()
    if a.mode == "latency":
        print(f"== 单次延迟基线 (BASE={BASE}) ==")
        latency_all(token)
    else:
        print(f"== 并发压测 {a.path} ==")
        for c in [int(x) for x in a.levels.split(",")]:
            run_level(token, a.path, c)

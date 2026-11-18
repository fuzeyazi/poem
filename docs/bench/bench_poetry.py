# -*- coding: utf-8 -*-
"""potry-service 诗词接口并发压测：梯度并发，输出 QPS / P50 / P95 / P99 / 错误率"""
import sys, time, threading, statistics, argparse
import requests

BASE = "http://127.0.0.1:8081"
PATH = "/user/poetry/GetPoemsByDynasty?dynasty=%E5%94%90%E4%BB%A3&pageNum=1&pageSize=20"
DURATION = 20  # 每档持续秒数
def run_level(token, concurrency):
    lat, errors, count = [], 0, 0
    stop = time.time() + DURATION
    lock = threading.Lock()
    sess = threading.local()

    def worker():
        nonlocal errors, count
        url = PATH if PATH.startswith("http") else BASE + PATH
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
    qps = count / wall
    print(f"c={concurrency:>3}  QPS={qps:>7.1f}  avg={statistics.mean(lat) if lat else -1:>7.1f}ms  "
          f"P50={pct(0.5):>7.1f}  P95={pct(0.95):>7.1f}  P99={pct(0.99):>7.1f}  "
          f"err={errors}/{count}", flush=True)

if __name__ == "__main__":
    levels = [int(x) for x in sys.argv[1].split(",")] if len(sys.argv) > 1 else [10, 50, 100, 200]
    token = sys.argv[2] if len(sys.argv) > 2 else None
    if len(sys.argv) > 3:
        PATH = sys.argv[3]
    if not token:
        import random
        u = f"bench_{random.randint(10**6, 10**7)}"
        requests.post(BASE + "/user/register", json={"username": u, "password": "123456"})
        r = requests.post(BASE + "/user/login", json={"username": u, "password": "123456"}).json()
        token = r["data"]["token"]
    print(f"token ok, 目标: {PATH[:40]}..., 每档 {DURATION}s", flush=True)
    for c in levels:
        run_level(token, c)

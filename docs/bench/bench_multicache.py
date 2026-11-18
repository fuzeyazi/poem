# -*- coding: utf-8 -*-
"""
多级缓存 (Multi-Level Cache: L1 Caffeine + L2 Redis + Redisson BloomFilter) 压测与对比实证脚本
输出指标：QPS / P50 / P95 / P99 / 错误率 / L1 本地缓存命中率 / 布隆防穿透耗时
"""
import sys
import time
import threading
import statistics
import random
import requests

BASE = "http://127.0.0.1:8081"
POEM_DETAIL_PATH = "/user/poetry/GetPoemById?id="
WRITER_DETAIL_PATH = "/user/poetry/GetPoemWriter?id="
ADMIN_CACHE_STATS = "/admin/cache/stats"
ADMIN_CACHE_WARMUP = "/admin/cache/warmup"
DURATION = 15  # 每档梯度持续压测秒数


def run_benchmark(name, url_generator, token, concurrency=50, duration=10):
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
            url = url_generator()
            t0 = time.time()
            try:
                r = s.get(url, headers={"token": token}, timeout=10)
                dt = (time.time() - t0) * 1000
                with lock:
                    lat.append(dt)
                    count += 1
                    if r.status_code != 200:
                        errors += 1
            except Exception:
                with lock:
                    errors += 1
                    count += 1

    threads = [threading.Thread(target=worker, daemon=True) for _ in range(concurrency)]
    t_start = time.time()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    wall = time.time() - t_start

    lat.sort()

    def pct(p):
        return lat[min(len(lat) - 1, int(len(lat) * p))] if lat else -1

    qps = count / wall if wall > 0 else 0
    avg_lat = statistics.mean(lat) if lat else -1
    print(f"[{name}] c={concurrency:>3}  QPS={qps:>8.1f}  avg={avg_lat:>6.2f}ms  "
          f"P50={pct(0.5):>6.2f}ms  P95={pct(0.95):>6.2f}ms  P99={pct(0.99):>6.2f}ms  "
          f"err={errors}/{count}", flush=True)
    return {"qps": qps, "avg": avg_lat, "p99": pct(0.99)}


def fetch_cache_stats(token):
    try:
        r = requests.get(BASE + ADMIN_CACHE_STATS, headers={"token": token}, timeout=5)
        if r.status_code == 200:
            data = r.json().get("data", {})
            print("\n========== [多级缓存运行指标快照] ==========")
            for k, v in data.items():
                print(f"  {k:<26}: {v}")
            print("==========================================\n")
    except Exception as e:
        print(f"[Warn] 获取多级缓存指标失败: {e}")


if __name__ == "__main__":
    print("====================================================")
    print("   poetry-spring2 多级缓存 (L1/L2/Bloom) 高并发压测   ")
    print("====================================================")

    # 1. 登录/注册获取用户 Token
    u = f"bench_multi_{random.randint(10**6, 10**7)}"
    try:
        requests.post(BASE + "/user/register", json={"username": u, "password": "123456"}, timeout=5)
        r = requests.post(BASE + "/user/login", json={"username": u, "password": "123456"}, timeout=5).json()
        token = r.get("data", {}).get("token", "")
        print(f"[*] 获取测试 Token 成功: {u}")
    except Exception as e:
        print(f"[!] 连接服务失败 ({BASE}): {e}")
        print("[!] 请确保后端 potry-service (8081) 已启动后再运行压测。")
        sys.exit(1)

    # 2. 预热核心 ID
    print("[*] 触发布隆过滤器与缓存异步预热...")
    try:
        requests.post(BASE + ADMIN_CACHE_WARMUP, headers={"token": token}, timeout=10)
    except Exception:
        pass

    # 3. 测试场景 A：热点诗词高频并发读取 (测试 L1 Caffeine 微秒级命中)
    hot_ids = [1, 2, 3, 5, 8, 10]
    print(f"\n>>> 场景 1: 热点诗词高并发读取 (聚焦 L1 本地 Caffeine 缓存吞吐)")
    run_benchmark(
        "Hot Poem (L1 Caffeine)",
        lambda: BASE + POEM_DETAIL_PATH + str(random.choice(hot_ids)),
        token,
        concurrency=100,
        duration=DURATION
    )

    # 4. 测试场景 B：布隆过滤器恶意非法 ID 穿透拦截 (测试 0.1ms 拒绝非法请求)
    print(f"\n>>> 场景 2: 随机非法大整数 ID 扫描 (聚焦 Redisson 布隆过滤器防穿透)")
    run_benchmark(
        "Invalid ID (Bloom Intercept)",
        lambda: BASE + POEM_DETAIL_PATH + str(random.randint(90000000, 99999999)),
        token,
        concurrency=100,
        duration=DURATION
    )

    # 5. 测试场景 C：诗人名片并发读取
    print(f"\n>>> 场景 3: 诗人名片并发读取 (多级缓存协同)")
    run_benchmark(
        "Writer Card (MultiCache)",
        lambda: BASE + WRITER_DETAIL_PATH + str(random.randint(1, 10)),
        token,
        concurrency=50,
        duration=DURATION
    )

    # 6. 打印最新监控快照
    fetch_cache_stats(token)

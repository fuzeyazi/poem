# -*- coding: utf-8 -*-
"""
点赞幂等改造专项：复现超发/丢判重 + 压测 toggle 写路径。
用法:
  python bench_like.py repro <token> <blogid>   # 场景复现: 丢判重重复点赞 + 并发首点超发
  python bench_like.py bench <token> <blogid> [c1,c2]  # toggle 写路径并发压测
"""
import sys, time, threading, statistics, subprocess, argparse
import requests

BASE = "http://127.0.0.1:8081"
REDIS_CLI = r"E:\redis\redis-cli.exe"
MYSQL = r"C:\Program Files\MySQL\MySQL Server 8.4\bin\mysql.exe"


def redis_del(key):
    subprocess.run([REDIS_CLI, "DEL", key], capture_output=True)


def get_liked(blogid):
    out = subprocess.run(
        [MYSQL, "-uroot", "-ppublication-placeholder-mysql_password", "poem", "-N", "-B", "-e",
         f"SELECT liked FROM poem.poem_blog WHERE id={blogid}"],
        capture_output=True, text=True).stdout.strip()
    return int(out)


def like_once(tok, blogid):
    r = requests.get(BASE + "/user/luntan/dianzan", params={"blogid": blogid},
                     headers={"token": tok}, timeout=15)
    return r.status_code, (r.json().get("data") or r.json().get("msg", ""))


def repro(tok, blogid):
    key = f"blog:like{blogid}"
    print(f"== 目标帖子 {blogid} ==")

    # 场景1: Redis 判重丢失后的重复点赞(模拟 Redis 重启/被逐出)
    redis_del(key)                       # 清干净初始态
    get_liked(blogid)
    like_once(tok, blogid)               # 第一次点赞
    before = get_liked(blogid)
    redis_del(key)                       # 模拟 Redis 丢数据(本机真实发生过)
    _, msg = like_once(tok, blogid)      # 同一用户再点一次
    after = get_liked(blogid)
    print(f"[S1 丢判重] 点赞后={before}, 删Redis再点后={after}, 响应={msg!r}  "
          f"=> {'超发! 同用户两赞' if after - before >= 1 else '幂等OK'}")

    # 场景2: 并发首点(模拟手快双击/网络重试并发)
    for rnd in range(1, 4):
        redis_del(key)
        # 先归零状态: 奇数轮先点掉上轮遗留(忽略输出)
        for _ in range(3):
            like_once(tok, blogid)
        redis_del(key)
        b = get_liked(blogid)
        barrier = threading.Barrier(10)
        results = []
        def worker():
            barrier.wait()
            results.append(like_once(tok, blogid)[1])
        ts = [threading.Thread(target=worker) for _ in range(10)]
        for t in ts: t.start()
        for t in ts: t.join()
        a = get_liked(blogid)
        ok_cnt = sum(1 for m in results if m == "点赞成功")
        print(f"[S2 并发首点 r{rnd}] 10线程barrier并发: before={b} after={a} 增量={a-b}, "
              f"点赞成功响应={ok_cnt}  => {'超发! (应≤1)' if a - b > 1 else '未超发'}")

    # 场景3: 退回净零(为后续压测留干净状态)
    for _ in range(4):
        like_once(tok, blogid)
    print(f"[cleanup] 最终 liked={get_liked(blogid)}")


def run_level(tok, blogid, concurrency, duration=15):
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
                r = s.get(BASE + "/user/luntan/dianzan", params={"blogid": blogid},
                          headers={"token": tok}, timeout=30)
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
    ap.add_argument("mode", choices=["repro", "bench"])
    ap.add_argument("token")
    ap.add_argument("blogid", type=int, default=46)
    ap.add_argument("levels", nargs="?", default="10,50")
    a = ap.parse_args()
    if a.mode == "repro":
        repro(a.token, a.blogid)
    else:
        print(f"== 点赞toggle写路径压测 blogid={a.blogid} ==")
        for c in [int(x) for x in a.levels.split(",")]:
            run_level(a.token, a.blogid, c)

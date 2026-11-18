# -*- coding: utf-8 -*-
"""MQ+WebSocket 事件驱动通知链路端到端验证"""
import asyncio, json, time, threading, requests
import websockets

B = 'http://127.0.0.1:8081'
WS = 'ws://127.0.0.1:8081/ws/websocket'   # SockJS 的原生 websocket 端点

received = []
ws_ready = threading.Event()

async def stomp_subscriber():
    async with websockets.connect(WS) as ws:
        # STOMP CONNECT
        await ws.send("CONNECT\naccept-version:1.2\nhost:localhost\n\n\x00")
        await ws.recv()
        # SUBSCRIBE /topic/newpost
        await ws.send("SUBSCRIBE\nid:sub-0\ndestination:/topic/newpost\n\n\x00")
        ws_ready.set()
        try:
            async for msg in ws:
                if msg.startswith("MESSAGE") and "newpost" in msg:
                    body = msg.split("\n\n")[1].rstrip("\x00")
                    received.append((time.time(), body))
                    if len(received) >= 1:
                        return
        except websockets.ConnectionClosed:
            pass

def run_ws():
    asyncio.run(stomp_subscriber())

t = threading.Thread(target=run_ws, daemon=True)
t.start()
ws_ready.wait(timeout=10)
print("1. STOMP 订阅者已就绪 (/topic/newpost)")

# 登录两个用户: srs_bench_1 发帖, bench 账号关注他
def login(u, p='123456'):
    return requests.post(B+'/user/login', json={'username':u,'password':p}, timeout=15).json()['data']['token']

poster = login('srs_bench_1')
fan = login('probe_new@demo.com', '') if False else None
# 关注: 用 bench 用户关注 srs_bench_1(其userid=76)
s = requests.Session()
import random
fu = f'mqfan_{random.randint(10**6,10**7)}'
requests.post(B+'/user/register', json={'username':fu,'password':'123456'}, timeout=15)
fan = login(fu)
# guanzhu 接口: followUserid=76, isFollow=true
r = s.get(B+'/user/luntan/guanzhu', headers={'token':fan}, params={'followUserid':76,'isFollow':'true'}, timeout=15)
print("2. 建立关注:", r.text[:60])

# 发帖
t0 = time.time()
r = s.post(B+'/user/luntan/fabutiezi', headers={'token':poster},
           json={'title':'MQ事件驱动测试帖','content':'RabbitMQ+WebSocket端到端验证','type':'测试'}, timeout=15)
rt = (time.time()-t0)*1000
print(f"3. 发帖: {r.text[:40]} 接口RT={rt:.0f}ms")

t.join(timeout=10)
if received:
    ts, body = received[0]
    print(f"4. STOMP 实时推送已收到! 端到端延迟={((ts-t0)*1000):.0f}ms")
    print("   推送内容:", body[:120])
else:
    print("4. ✗ 未收到推送")

# 收件箱与缓存验证
import pymysql, subprocess
c = pymysql.connect(host='127.0.0.1', user='root', password='publication-placeholder-mysql_password', database='poem', autocommit=True)
cur = c.cursor()
cur.execute("SELECT id FROM poem_blog ORDER BY id DESC LIMIT 1"); blogid = cur.fetchone()[0]
out = subprocess.run([r'E:\redis\redis-cli.exe','ZRANGE',f'fan:{2}','0','-1','WITHSCORES'], capture_output=True, text=True).stdout
cur.execute("SELECT id FROM user WHERE username=%s", (fu,)); fanid = cur.fetchone()[0]
out = subprocess.run([r'E:\redis\redis-cli.exe','ZSCORE',f'fan:{fanid}',str(blogid)], capture_output=True, text=True).stdout.strip()
print(f"5. 粉丝收件箱 fan:{fanid} 含新帖{blogid}: {out != ''} (score={out[:13]})")
ttl = subprocess.run([r'E:\redis\redis-cli.exe','TTL',f'blog:{blogid}'], capture_output=True, text=True).stdout.strip()
print(f"6. 帖子内容缓存 blog:{blogid} TTL={ttl}s (应≈3600)")

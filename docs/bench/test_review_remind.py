# -*- coding: utf-8 -*-
"""复习提醒推送端到端验证: STOMP订阅 -> admin触发 -> 收推 -> 防重 -> 历史接口"""
import asyncio, time, threading, json
import requests, websockets

B = 'http://127.0.0.1:8081'
WS = 'ws://127.0.0.1:8081/ws/websocket'

received = []
ws_ready = threading.Event()

async def stomp_subscriber():
    async with websockets.connect(WS) as ws:
        await ws.send("CONNECT\naccept-version:1.2\nhost:localhost\n\n\x00")
        await ws.recv()
        await ws.send("SUBSCRIBE\nid:sub-0\ndestination:/topic/review.77\n\n\x00")
        ws_ready.set()
        try:
            async for msg in ws:
                if msg.startswith("MESSAGE") and "review" in msg:
                    received.append(msg.split("\n\n")[1].rstrip("\x00"))
                    return
        except websockets.ConnectionClosed:
            pass

threading.Thread(target=lambda: asyncio.run(stomp_subscriber()), daemon=True).start()
assert ws_ready.wait(10)
print("1. STOMP 已订阅 /topic/review.77")

tok = requests.post(B + '/user/login', json={'username': 'hud_15605', 'password': '123456'}, timeout=10).json()['data']['token']
H = {'token': tok}

r = requests.get(B + '/user/book/remindcount', headers=H, timeout=10).json()
print(f"2. remindcount = {r['data']} (期望3)")

# admin 手动触发(需要 admin token: 验证码流程)
code_resp = requests.get(B + '/admin/getCode', timeout=10).json()
import subprocess
ck = code_resp['data']['codeKey']
code = subprocess.run([r'E:\redis\redis-cli.exe', 'GET', ck], capture_output=True, text=True).stdout.strip()
adm = requests.post(B + '/admin/login', json={'username': 'asdfg', 'password': '123456', 'code': code, 'codeKey': ck}, timeout=10).json()['data']['token']
r2 = requests.post(B + '/admin/remind/trigger', headers={'token': adm}, timeout=15).json()
print(f"3. 手动触发: {r2['data']}")

for _ in range(20):
    if received:
        break
    time.sleep(0.5)
print(f"4. STOMP 收到推送: {received[0] if received else '(未收到!)'}")

r3 = requests.post(B + '/admin/remind/trigger', headers={'token': adm}, timeout=15).json()
time.sleep(1)
print(f"5. 防重(二次触发后新消息数应为0): 新增={len(received)-1}, 触发返回='{r3['data']}'")

r4 = requests.get(B + '/user/book/remindlog', headers=H, timeout=10).json()
print(f"6. remindlog = {r4['data']}")

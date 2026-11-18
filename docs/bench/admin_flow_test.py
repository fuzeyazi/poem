# -*- coding: utf-8 -*-
"""管理端正向流程验证:验证码(JDK序列化key) -> admin登录 -> 管理操作 -> 角色隔离"""
import requests, re

B = 'http://127.0.0.1:8081'

def redis_get_jdk(key):
    """用原始socket RESP协议读取JDK序列化key的值"""
    s = socket.create_connection(('127.0.0.1', 6379), timeout=8)
    raw_key = b'\xac\xed\x00\x05t\x00' + bytes([len(key)]) + key.encode()
    s.sendall(b'*2\r\n$3\r\nGET\r\n$%d\r\n' % len(raw_key) + raw_key + b'\r\nQUIT\r\n*1\r\n$4\r\nQUIT\r\n')
    buf = b''
    try:
        while True:
            chunk = s.recv(65536)
            if not chunk:
                break
            buf += chunk
    except Exception:
        pass
    s.close()
    return buf

import socket
r = requests.get(B+'/admin/getCode', timeout=15).json()['data']
key = r['codeKey']
buf = redis_get_jdk(key)
# JDK序列化字符串: AC ED 00 05 74 00 [2字节长度] <code>
m = re.search(rb't\x00\x04(\w{4})', buf)
code = m.group(1).decode() if m else None
print('1. 验证码:', code)

r2 = requests.post(B+'/admin/login', json={'username':'asdfg','password':'123456','code':code,'codeKey':key}, timeout=15)
d = r2.json()
print('2. admin登录:', d.get('code'), str(d.get('data'))[:60])
at = d['data']['token']

sc = requests.get(B+'/admin/getAll', headers={'token': at}, timeout=15).status_code
print('3. getAll(admin token,直连):', sc)
sc2 = requests.post(B+'/admin/disable/1?id=76', headers={'token': at}, timeout=15).status_code
print('4. disable(admin token):', sc2)
sc3 = requests.get('http://127.0.0.1:9080/admin/getAll', headers={'token': at}, timeout=15).status_code
print('5. getAll(经网关,admin token):', sc3)
ut = requests.post(B+'/user/login', json={'username':'srs_bench_1','password':'123456'}, timeout=15).json()['data']['token']
sc4 = requests.get('http://127.0.0.1:9080/admin/getAll', headers={'token': ut}, timeout=15).status_code
print('6. 用户token冒充admin(经网关):', sc4, '<-隔离生效' if sc4 == 401 else '<-FAIL')
sc5 = requests.get('http://127.0.0.1:9080/admin/getAll', timeout=15).status_code
print('7. 无token(经网关):', sc5)

# 验证「key 锚定 + varint 长度前缀」能否精确取出 access_token（C# 端要用同一算法）
import os, glob, base64, json, time

LS = os.path.expandvars(r"%APPDATA%\kimi-desktop\Local Storage\leveldb")


def varint(b, i):
    val = 0; shift = 0
    while i < len(b):
        c = b[i]; i += 1
        val |= (c & 0x7F) << shift
        if not (c & 0x80):
            return val, i
        shift += 7
        if shift > 35:
            break
    return -1, i


def decode_ls(v):
    if not v:
        return ""
    if len(v) >= 4 and v[1] == 0 and v[0] != 0:
        return v.decode("utf-16-le", "ignore")
    if v[0] == 0:
        n = len(v) - 1
        if n % 2:
            n -= 1
        return v[1:1 + n].decode("utf-16-le", "ignore")
    if v[0] == 1:
        return v[1:].decode("utf-8", "ignore")
    return v.decode("utf-8", "ignore")


now = int(time.time())
files = sorted(glob.glob(os.path.join(LS, "*")), key=os.path.getmtime, reverse=True)
print("leveldb 文件（按修改时间）:", [os.path.basename(f) for f in files][:6])
found = []
for f in files:
    if not os.path.isfile(f) or os.path.getsize(f) == 0:
        continue
    with open(f, "rb") as fh:          # 只读打开，不动 Kimi 数据
        b = fh.read()
    for key in (b"access_token", b"refresh_token"):
        pos = 0
        while True:
            pos = b.find(key, pos)
            if pos < 0:
                break
            nxt = pos + len(key)
            ln, after = varint(b, nxt)
            if 0 < ln < 4000 and after + ln <= len(b):
                raw = b[after:after + ln]
                s = decode_ls(raw)
                if s.startswith("eyJ") and s.count(".") == 2:
                    try:
                        p = s.split(".")[1]
                        p += "=" * (-len(p) % 4)
                        claims = json.loads(base64.urlsafe_b64decode(p))
                        found.append((key.decode(), os.path.basename(f), len(s), claims.get("exp"), claims.get("iat")))
                    except Exception as e:
                        found.append((key.decode(), os.path.basename(f), len(s), "decode-fail", str(e)[:30]))
            pos = nxt
print("\n精确取到的键值（key 锚定 + 长度前缀）:")
for k, fn, ln, exp, iat in found:
    tag = ""
    if isinstance(exp, int):
        tag = "  exp=%s (%+ds) iat=%s 剩余TTL=%ds" % (time.strftime('%H:%M:%S', time.localtime(exp)), exp - now, iat, exp - now)
    print("   %-14s %-14s len=%-4d %s" % (k, fn, ln, tag))
best = [x for x in found if isinstance(x[3], int) and x[3] > now]
print("\n可用（未过期）token 数：%d；最长 exp：%s" % (
    len(best), time.strftime('%H:%M:%S', time.localtime(max(x[3] for x in best))) if best else "无"))

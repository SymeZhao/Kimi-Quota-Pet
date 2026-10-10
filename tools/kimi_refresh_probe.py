# 只验证不落盘：用本地 refresh_token 调 Kimi 官方 RefreshToken 接口
#   关键问题：1) 能不能换到新 access_token  2) 服务端会不会轮换 refresh_token（旧的是否立即失效）
#   本脚本不写任何文件、不改 leveldb，只在内存里用令牌，输出全部脱敏。
import os, glob, re, json, base64, time, urllib.request, urllib.error

LS = os.path.expandvars(r"%APPDATA%\kimi-desktop\Local Storage\leveldb")
URL = "https://auth.kimi.com/api/account.gateway.v1.AuthService/RefreshToken"


def varint(b, i):
    v = 0; s = 0
    while i < len(b):
        c = b[i]; i += 1
        v |= (c & 0x7F) << s
        if not (c & 0x80): return v, i
        s += 7
        if s > 35: break
    return -1, i


def decode_ls(v):
    if not v: return ""
    if len(v) >= 4 and v[1] == 0 and v[0] != 0: return v.decode("utf-16-le", "ignore")
    if v[0] == 0:
        n = len(v) - 1
        if n % 2: n -= 1
        return v[1:1 + n].decode("utf-16-le", "ignore")
    if v[0] == 1: return v[1:].decode("utf-8", "ignore")
    return v.decode("utf-8", "ignore")


def find_all(b, key):
    out = []
    k = key.encode()
    pos = 0
    while True:
        pos = b.find(k, pos)
        if pos < 0: break
        i = pos + len(k)
        ln, after = varint(b, i)
        if 0 < ln < 8192 and after + ln <= len(b):
            s = decode_ls(b[after:after + ln])
            if s.startswith("eyJ"): out.append(s)
        pos = i
    return out


def claims(t):
    try:
        p = t.split(".")[1]; p += "=" * (-len(p) % 4)
        return json.loads(base64.urlsafe_b64decode(p))
    except Exception:
        return {}


now = int(time.time())
refresh = None
for f in sorted(glob.glob(os.path.join(LS, "*")), key=os.path.getmtime, reverse=True):
    if not os.path.isfile(f) or os.path.getsize(f) == 0: continue
    cands = find_all(open(f, "rb").read(), "refresh_token")
    good = [c for c in cands if claims(c).get("exp", 0) > now]
    if good:
        refresh = max(good, key=lambda c: claims(c).get("exp", 0))
        print("refresh_token 来源: %s  len=%d  exp=%s（%.0f 天后）" % (
            os.path.basename(f), len(refresh),
            time.strftime("%Y-%m-%d %H:%M", time.localtime(claims(refresh)["exp"])),
            (claims(refresh)["exp"] - now) / 86400.0))
        break
if not refresh:
    raise SystemExit("本地没有未过期的 refresh_token")


def call(body, tag):
    data = json.dumps(body).encode()
    req = urllib.request.Request(URL, data=data, method="POST")
    for k, v in (("Content-Type", "application/json"), ("Connect-Protocol-Version", "1"),
                 ("Accept", "application/json"), ("User-Agent", "kimi-quota-pet/0.1")):
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=25) as r:
            raw = r.read().decode("utf-8", "replace")
            return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, e)


def summarize(raw, stored):
    try:
        j = json.loads(raw)
    except Exception:
        return "非 JSON: " + raw[:200]
    def walk(o, path=""):
        out = []
        if isinstance(o, dict):
            for k, v in o.items(): out += walk(v, path + "/" + k)
        elif isinstance(o, list):
            for i, v in enumerate(o[:2]): out += walk(v, path + "[%d]" % i)
        else:
            out.append((path, o))
        return out
    lines = []
    for path, val in walk(j):
        s = str(val)
        if s.startswith("eyJ") and s.count(".") == 2:
            c = claims(s)
            same = "【与本地相同】" if s == stored else "【与本地不同 -> 服务端轮换了 refresh_token】"
            mark = same if "refresh" in path.lower() else ""
            lines.append("   %-28s <JWT len=%d exp=%s> %s" % (
                path, len(s), time.strftime("%m-%d %H:%M", time.localtime(c["exp"])) if c.get("exp") else "?", mark))
        elif len(s) > 60:
            lines.append("   %-28s <len=%d>" % (path, len(s)))
        else:
            lines.append("   %-28s %s" % (path, s))
    return "\n".join(lines)


print("\n=== 第 1 次调用（用本地存的 refresh_token）===")
st, raw = call({"refreshToken": refresh}, "first")
print("HTTP", st)
print(summarize(raw, refresh))
first_ok = st == 200
new_refresh = None
try:
    j = json.loads(raw)
    for k in ("refreshToken", "refresh_token"):
        if isinstance(j.get(k), str): new_refresh = j[k]
    if j.get("data") and isinstance(j["data"], dict):
        for k in ("refreshToken", "refresh_token"):
            if isinstance(j["data"].get(k), str): new_refresh = j["data"][k]
except Exception:
    pass

print("\n=== 第 2 次调用（仍用【旧的】本地 refresh_token，检验是否已失效）===")
time.sleep(1.5)
st2, raw2 = call({"refreshToken": refresh}, "second")
print("HTTP", st2)
print("结论：" + ("旧 refresh_token 仍然可用 —— 服务端没有作废旧令牌，桌面版不会被踢下线"
                 if st2 == 200 else
                 "旧 refresh_token 已被拒（HTTP %s）—— 桌面版可能被要求重新登录，需谨慎" % st2))
if new_refresh is not None:
    print("服务端%s在响应里返回了 refresh_token" % ("有" if new_refresh else "没有"))
else:
    print("响应里没有 refresh_token 字段（说明它沿用旧的，风险更低）")

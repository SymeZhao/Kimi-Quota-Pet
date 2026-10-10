# 把 DSH 余额桌宠 v3 移植成 Kimi 额度桌宠
#   * 数据层：内嵌 C# 每次轮询重读 Kimi 桌面版 leveldb 里的 access_token，调官方额度接口
#   * 显示：主显「套餐剩余 %」，为 0 时切「额外额度 ¥」
#   * 额度上升（充值/周期重置）：静默跳值；白饭那套（米饭盆/铁盆/雷达）素材不放、菜单无入口
#   * 托盘图标换成立绘图标；菜单删掉充值动画/雷达/设置 API Key 三个入口
import os

SRC = r"C:\Users\Administrator\Documents\DSH-Balance-Pet\dsh_pet.ps1"
DST_DIR = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet"
DST = os.path.join(DST_DIR, "kimi_pet.ps1")

with open(SRC, "r", encoding="ascii", newline="") as fh:
    s = fh.read()
assert "\r" not in s, "unexpected CRLF"

EDITS = []


def rep(old, new, tag):
    EDITS.append(("replace", old, new, tag))


def repall(old, new, tag):
    EDITS.append(("replace_all", old, new, tag))


def splice(start, end, new, tag, keep_end=True):
    EDITS.append(("splice", start, end, new, tag, keep_end))


# ------------------------------------------------------------- 1. 启动块 ------
splice(
    "# Credentials: local override, then environment, then DSH's own credential store.",
    "if (-not $env:DSHPET_SPRITE) { $env:DSHPET_SPRITE = Join-Path $here 'sprite.png' }",
    "# Nothing to configure. The embedded C# re-reads the Kimi desktop app's own login\n"
    "# state (leveldb access_token, ~15 min lifetime) on every poll and calls the same\n"
    "# quota endpoint the app itself uses. Read-only: no API key, no token on disk.\n"
    "if (-not $env:DSHPET_SPRITE) { $env:DSHPET_SPRITE = Join-Path $here 'sprite.png' }\n"
    "if (-not $env:DSHPET_POLL_MS)   { $env:DSHPET_POLL_MS   = '10000' }\n",
    "startup block",
    keep_end=False,
)

# --------------------------------------------------------------- 2. 字段 ------
rep(
    "    bool _isAccount;\n    string _token;\n    bool _noSave;",
    "    bool _isAccount;\n    string _token;\n"
    "    // ---- Kimi membership quota -------------------------------------------\n"
    "    // The stats call returns how much of the plan quota is used (a ratio for the\n"
    "    // billing period) and how much CNY is left in the Extra Usage wallet. The\n"
    "    // widget prints whichever is meaningful:\n"
    "    //   plan has room  -> remaining percentage, one cue = 1 %\n"
    "    //   plan exhausted -> Extra Usage balance, one cue = 0.01 CNY\n"
    "    double _step = 1.0;                              // charge step, current mode\n"
    "    string _panelLabel = \"\\u5269\\u4F59\\u989D\\u5EA6\";   // panel caption\n"
    "    string _panelSym = \"\";                           // drawn before the number\n"
    "    string _panelSuffix = \"%\";                        // drawn after the number\n"
    "    bool _noSave;",
    "kimi fields",
)

# ----------------------------------------------------------- 3. 平板四边形 ----
rep(
    "        double[] qx = new double[] { 549.6, 949.7, 984.7, 584.6 };\n"
    "        double[] qy = new double[] { 706.2, 642.0, 860.2, 924.3 };\n",
    "        // Kimi artwork: the tablet is DRAWN into sprite.png by\n"
    "        // tools/kimi_make_assets.py, so these are that rectangle's corners.\n"
    "        // Order 0..3 = TL, TR, BR, BL. To move the panel, edit PX/PY in the asset\n"
    "        // script, re-run it, and paste the new numbers from panel_quad.txt here.\n"
    "        double[] qx = new double[] { 958, 1398, 1398, 958 };\n"
    "        double[] qy = new double[] { 1096, 1096, 1306, 1306 };\n",
    "panel quad",
)

# ------------------------------------------------------------- 4. 头部坐标 ----
rep(
    "        _headX = (int)(sw * 0.50 + sh * 0.17);\n        _headY = (int)(sh * 0.36);\n",
    "        _headX = (int)(sw * 0.494);\n        _headY = (int)(sh * 0.175);\n",
    "head coords",
)

# ------------------------------------------------------------- 5. 托盘图标 ----
rep(
    "        _tray.Icon = SystemIcons.Application;\n",
    "        try { _tray.Icon = new Icon(Path.Combine(baseDir, \"pet.ico\")); }\n"
    "        catch { _tray.Icon = SystemIcons.Application; }\n",
    "tray icon",
)

# ------------------------------------------------ 6. 首次运行要 Key 的弹窗 ----
splice(
    "        // Shared copy, first run: nothing configured a key, so ask once instead",
    "        _tray = new NotifyIcon();",
    "        // No key prompt: the Kimi pet reads the desktop app's own login state.\n",
    "no key dialog",
    keep_end=True,
)

# --------------------------------------------------- 7. 菜单：充值动画入口 ----
rep(
    "        ToolStripMenuItem testTop = NewItem(IC_BOWL, S_TESTTOP);\n"
    "        _testTopItem = testTop;\n"
    "        ToolStripMenuItem testTopGo = NewItem(IC_NONE, S_TESTTOPG);\n"
    "        testTopGo.Click += delegate { TestTopUp(TestTopUpYuan); };\n"
    "        testTop.DropDownItems.Add(testTopGo);\n"
    "        // Fires the nameplate up by hand so the readouts can be checked without\n"
    "        // waiting out the 10 s deadline. Display only - it does not feed the bowl.\n"
    "        ToolStripMenuItem radarOn = NewItem(IC_NONE, S_RADARON);\n"
    "        radarOn.Click += delegate { OpenRadarManually(); };\n"
    "        testTop.DropDownItems.Add(radarOn);\n"
    "        testTop.DropDownItems.Add(new ToolStripSeparator());\n"
    "        ToolStripMenuItem testTopCustom = NewItem(IC_NONE, S_CUSTOM);\n"
    "        testTopCustom.Click += delegate { AskTopUp(); };\n"
    "        testTop.DropDownItems.Add(testTopCustom);\n"
    "        _menu.Items.Add(testTop);\n\n",
    "",
    "menu topup block",
)
rep(
    "        test.Click += delegate { DemoCharge(StepYuan); };\n",
    "        test.Click += delegate { DemoCharge(_step); };\n",
    "test charge step",
)
rep(
    "        double[] demos = new double[] { 0.05, 0.1, 0.2, 0.5, 1.0 };\n",
    "        // One cue = 1 % in plan mode, 0.01 CNY in Extra Usage mode.\n"
    "        double[] demos = new double[] { 1, 2, 3, 5, 10 };\n",
    "demo amounts",
)
rep(
    "    void DemoCharge(double amount) {\n"
    "        if (amount < StepYuan) amount = StepYuan;\n"
    "        int cues = (int)Math.Round(amount / StepYuan);\n"
    "        if (cues < 1) cues = 1;\n"
    "        if (cues > 500) cues = 500;\n"
    "        _demoLeft = cues;\n"
    "        _demoAmount = StepYuan;\n"
    "        Log(\"demo charge: \" + Yuan(amount) + \" -> \" + cues + \" cue(s), \" +\n"
    "            CueGapSec.ToString(\"0.#\") + \"s apart\");\n"
    "        _dirty = true;\n"
    "    }\n",
    "    void DemoCharge(double amount) {\n"
    "        if (amount < _step) amount = _step;\n"
    "        int cues = (int)Math.Round(amount / _step);\n"
    "        if (cues < 1) cues = 1;\n"
    "        if (cues > MaxCuesPerPoll) cues = MaxCuesPerPoll;\n"
    "        _demoLeft = cues;\n"
    "        _demoAmount = _step;\n"
    "        Log(\"demo charge: \" + amount.ToString(\"0.##\", CultureInfo.InvariantCulture) +\n"
    "            _panelSuffix + \" -> \" + cues + \" cue(s), \" +\n"
    "            CueGapSec.ToString(\"0.#\") + \"s apart\");\n"
    "        _dirty = true;\n"
    "    }\n",
    "DemoCharge body",
)

# ------------------------------------------------- 8. 菜单：设置 API Key ----
rep(
    "        // ---- system ----\n"
    "        ToolStripMenuItem key = NewItem(IC_KEY, S_SETKEY);\n"
    "        key.Click += delegate { AskKey(); };\n"
    "        _menu.Items.Add(key);\n\n",
    "        // ---- system ----\n\n",
    "menu api key",
)

# --------------------------------------------------------------- 9. 状态 ------
rep(
    '    const string S_NOKEY   = "\\u7F3A\\u5C11 API Key";\n',
    '    const string S_NOKEY   = "\\u6253\\u5F00 Kimi \\u684C\\u9762\\u7248";   // open the desktop app\n',
    "no-token status",
)

# ----------------------------------------------------------- 10. 日志名 ------
rep('Path.Combine(_baseDir, "pet.log")', 'Path.Combine(_baseDir, "kimi_pet.log")', "log name 1")
# hit pool and feed pool both build the log path from baseDir
repall('Path.Combine(baseDir, "pet.log")', 'Path.Combine(baseDir, "kimi_pet.log")', "log name 2")

# ----------------------------------------------------------- 11. PollNow -----
rep(
    "    void PollNow(bool snap) {\n"
    "        if (!HasSecret) {\n"
    "            _connected = false;\n"
    "            _status = S_NOKEY;\n"
    "            _lastPollResult = \"no credentials\";\n"
    "            _dirty = true;\n"
    "            Log(\"poll skipped: no credentials (menu: \" + S_SETKEY + \")\");\n"
    "            return;\n"
    "        }\n"
    "        if (Interlocked.CompareExchange(ref _pollInFlight, 1, 0) != 0) return;\n"
    "        bool wantSnap = snap;\n"
    "        ThreadPool.QueueUserWorkItem(delegate {\n"
    "            try {\n"
    "                string body = FetchBalance();\n"
    "                double bal = ParseAnyCny(body);\n"
    "                if (double.IsNaN(bal)) { Fail(\"cannot parse response: \" + Trunc(body)); return; }\n"
    "                lock (_hits) { _bankedBal = bal; _bankedSnap = wantSnap; _bankedValid = true; }\n"
    "            } catch (Exception ex) {\n"
    "                Fail(ex.Message);\n"
    "            } finally {\n"
    "                Interlocked.Exchange(ref _pollInFlight, 0);\n"
    "            }\n"
    "        });\n"
    "    }\n",
    "    void PollNow(bool snap) {\n"
    "        // The access token is re-read from the Desktop app's leveldb on EVERY poll:\n"
    "        // it lives ~15 minutes and the app keeps minting new ones, so a cached copy\n"
    "        // would go stale within minutes. Only one request is ever in flight.\n"
    "        if (Interlocked.CompareExchange(ref _pollInFlight, 1, 0) != 0) return;\n"
    "        bool wantSnap = snap;\n"
    "        ThreadPool.QueueUserWorkItem(delegate {\n"
    "            try {\n"
    "                string token = ReadKimiToken();\n"
    "                if (string.IsNullOrEmpty(token)) { FailNoToken(); return; }\n"
    "                string body = FetchKimi(token);\n"
    "                double val; string err;\n"
    "                if (!ParseKimiValue(body, out val, out err)) { Fail(err); return; }\n"
    "                // A rise (Extra Usage top-up, or the plan rolling into a new period)\n"
    "                // is applied as a silent jump: no hurt animation, no top-up prop.\n"
    "                double applied = _realBal;\n"
    "                if (double.IsNaN(applied) || val >= applied - 1e-9) wantSnap = true;\n"
    "                lock (_hits) { _bankedBal = val; _bankedSnap = wantSnap; _bankedValid = true; }\n"
    "            } catch (Exception ex) {\n"
    "                Fail(ex.Message);\n"
    "            } finally {\n"
    "                Interlocked.Exchange(ref _pollInFlight, 0);\n"
    "            }\n"
    "        });\n"
    "    }\n"
    "\n"
    "    // No usable access_token: the desktop app is closed, or it has been idle long\n"
    "    // enough that its token expired. The tablet shows the hint instead of a number.\n"
    "    void FailNoToken() {\n"
    "        lock (_hits) {\n"
    "            _connected = false;\n"
    "            _status = S_NOKEY;\n"
    "            _lastPollResult = \"no access_token\";\n"
    "        }\n"
    "        Log(\"poll skipped: no access_token - open the Kimi desktop app to refresh one\");\n"
    "        _dirty = true;\n"
    "    }\n",
    "PollNow",
)

# --------------------------------------------------- 12. Kimi 数据层（C#） ----
KIMI_LAYER = r'''    // ---------------------------------------------------------- Kimi quota ---
    //
    // Kimi's membership quota is not reachable with an API key. The Desktop app
    // keeps a short-lived access_token (JWT, ~15 min) in its Local Storage
    // leveldb, so the pet reads it on every poll and calls the same endpoint the
    // app itself calls:
    //
    //   POST .../MembershipService/GetSubscriptionStats   Authorization: Bearer <token>
    //   {"subscriptionBalance":{"amountUsedRatio":0.37,...},
    //    "boosterWallets":[{"moneyLeft":{"priceInCents":"2148"},...}]}
    //
    // Read-only: files are opened share-read (the app keeps them open), and the
    // token is used in memory only - never written to disk and never logged.

    static string KimiLsDir {
        get {
            string appData = Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
            return Path.Combine(appData, "kimi-desktop", "Local Storage", "leveldb");
        }
    }

    static string KimiStatsUrl {
        get {
            return Get("DSHPET_KIMI_URL",
                "https://www.kimi.com/apiv2/kimi.gateway.membership.v2.MembershipService/GetSubscriptionStats");
        }
    }

    static byte[] ReadShared(string path) {
        using (FileStream fs = new FileStream(path, FileMode.Open, FileAccess.Read,
                                              FileShare.ReadWrite | FileShare.Delete)) {
            using (MemoryStream ms = new MemoryStream()) {
                fs.CopyTo(ms);
                return ms.ToArray();
            }
        }
    }

    static int ReadVarint(byte[] b, ref int i) {
        int val = 0, shift = 0;
        while (i < b.Length) {
            byte c = b[i++];
            val |= (c & 0x7F) << shift;
            if ((c & 0x80) == 0) return val;
            shift += 7;
            if (shift > 35) break;
        }
        return -1;
    }

    // Local Storage values carry a 1-byte encoding tag: 0 = UTF-16LE, 1 = UTF-8.
    static string DecodeLsValue(byte[] v) {
        if (v.Length == 0) return "";
        if (v.Length >= 4 && v[1] == 0 && v[0] != 0) return Encoding.Unicode.GetString(v);
        if (v[0] == 0) {
            int n = v.Length - 1;
            if (n % 2 != 0) n--;
            return n <= 0 ? "" : Encoding.Unicode.GetString(v, 1, n);
        }
        if (v[0] == 1) return Encoding.UTF8.GetString(v, 1, v.Length - 1);
        return Encoding.UTF8.GetString(v);
    }

    // leveldb stores a write batch entry as [tag][keyLen varint][key][valLen varint][value].
    // Anchoring on the key and honouring the length prefix yields the EXACT value: a
    // greedy regex would also swallow bytes of the following record, and a token with
    // trailing junk is rejected by the server.
    static string FindLsValue(byte[] b, string key) {
        byte[] k = Encoding.UTF8.GetBytes(key);
        for (int i = 0; i + k.Length < b.Length; i++) {
            if (b[i] != k[0]) continue;
            bool same = true;
            for (int j = 1; j < k.Length; j++) {
                if (b[i + j] != k[j]) { same = false; break; }
            }
            if (!same) continue;
            int p = i + k.Length;
            int len = ReadVarint(b, ref p);
            if (len <= 0 || len > 8192 || p + len > b.Length) continue;
            byte[] v = new byte[len];
            Array.Copy(b, p, v, 0, len);
            string sVal = DecodeLsValue(v);
            if (sVal.Length >= 40) return sVal;
        }
        return null;
    }

    static long JwtExp(string token) {
        try {
            string[] parts = token.Split('.');
            if (parts.Length < 2) return 0;
            string p = parts[1].Replace('-', '+').Replace('_', '/');
            while (p.Length % 4 != 0) p += "=";
            string json = Encoding.UTF8.GetString(Convert.FromBase64String(p));
            int i = json.IndexOf("\"exp\"");
            if (i < 0) return 0;
            i = json.IndexOf(':', i) + 1;
            int e = i;
            while (e < json.Length && (char.IsDigit(json[e]) || json[e] == ' ')) e++;
            long v;
            return long.TryParse(json.Substring(i, e - i).Trim(), out v) ? v : 0;
        } catch { return 0; }
    }

    // Newest still-valid access_token across the leveldb files (newest file first).
    string ReadKimiToken() {
        string explicitToken = Get("DSHPET_KIMI_TOKEN", "");
        if (explicitToken.Length > 0) return explicitToken;
        string dir = Get("DSHPET_KIMI_LS", KimiLsDir);
        if (!Directory.Exists(dir)) return null;
        string[] files;
        try { files = Directory.GetFiles(dir); } catch { return null; }
        Array.Sort(files, delegate(string a, string b) {
            return File.GetLastWriteTimeUtc(b).CompareTo(File.GetLastWriteTimeUtc(a));
        });
        long now = DateTimeOffset.UtcNow.ToUnixTimeSeconds();
        string best = null;
        long bestExp = 0;
        foreach (string f in files) {
            try {
                FileInfo fi = new FileInfo(f);
                if (fi.Length == 0 || fi.Length > 8L * 1024 * 1024) continue;
                string tok = FindLsValue(ReadShared(f), "access_token");
                if (tok == null || !tok.StartsWith("eyJ")) continue;
                long exp = JwtExp(tok);
                if (exp <= now + 20) continue;
                if (exp > bestExp) { bestExp = exp; best = tok; }
            } catch { }
        }
        return best;
    }

    string FetchKimi(string token) {
        HttpRequestMessage req = new HttpRequestMessage(HttpMethod.Post, KimiStatsUrl);
        req.Headers.TryAddWithoutValidation("Authorization", "Bearer " + token);
        req.Headers.TryAddWithoutValidation("Accept", "application/json");
        req.Headers.TryAddWithoutValidation("Connect-Protocol-Version", "1");
        req.Content = new StringContent("{}", Encoding.UTF8, "application/json");
        HttpResponseMessage resp = Http.SendAsync(req).GetAwaiter().GetResult();
        string body = resp.Content.ReadAsStringAsync().GetAwaiter().GetResult();
        if (!resp.IsSuccessStatusCode) throw new Exception("HTTP " + (int)resp.StatusCode);
        return body;
    }

    // First number that follows <key> at or after <from>; NaN when absent.
    static double JsonNumberAfter(string json, string key, int from) {
        if (from < 0) return double.NaN;
        int i = json.IndexOf(key, from);
        if (i < 0) return double.NaN;
        int c = json.IndexOf(':', i);
        if (c < 0) return double.NaN;
        int e = c + 1;
        while (e < json.Length && (json[e] == ' ' || json[e] == '"')) e++;
        int st = e;
        while (e < json.Length && (char.IsDigit(json[e]) || json[e] == '.' || json[e] == '-' ||
                                   json[e] == '+' || json[e] == 'e' || json[e] == 'E')) e++;
        double v;
        return double.TryParse(json.Substring(st, e - st), NumberStyles.Float,
                               CultureInfo.InvariantCulture, out v) ? v : double.NaN;
    }

    static string JsonStringAfter(string json, string key, int from) {
        if (from < 0) return null;
        int i = json.IndexOf(key, from);
        if (i < 0) return null;
        int c = json.IndexOf(':', i);
        if (c < 0) return null;
        int q1 = json.IndexOf('"', c + 1);
        if (q1 < 0) return null;
        int q2 = json.IndexOf('"', q1 + 1);
        if (q2 < 0) return null;
        return json.Substring(q1 + 1, q2 - q1 - 1);
    }

    // Turns the stats payload into the single number the widget prints, keeping the
    // panel caption, the currency sign and the charge step in sync with the mode.
    bool ParseKimiValue(string body, out double value, out string error) {
        value = double.NaN;
        error = null;
        if (string.IsNullOrEmpty(body) ||
            (body.IndexOf("subscriptionBalance") < 0 && body.IndexOf("boosterWallets") < 0)) {
            error = "unexpected payload: " + Trunc(body);
            return false;
        }
        double used = JsonNumberAfter(body, "\"amountUsedRatio\"", 0);
        int ml = body.IndexOf("\"moneyLeft\"");
        double leftCents = JsonNumberAfter(body, "\"priceInCents\"", ml);
        string notice = JsonStringAfter(body, "\"tip\"", body.IndexOf("\"notice\""));
        double planRemain = double.IsNaN(used) ? double.NaN : Math.Max(0, (1 - used) * 100);
        double extraCny = double.IsNaN(leftCents) ? double.NaN : leftCents / 100.0;

        if (!double.IsNaN(planRemain) && planRemain > 0.5) {
            value = Math.Round(planRemain, 2);
            _step = 1.0;
            _panelLabel = "\u5269\u4F59\u989D\u5EA6";        // remaining plan quota
            _panelSym = "";
            _panelSuffix = "%";
        } else {
            if (double.IsNaN(extraCny)) {
                error = "plan exhausted and no Extra Usage wallet in payload";
                return false;
            }
            value = Math.Round(extraCny, 4);
            _step = 0.01;
            _panelLabel = "\u989D\u5916\u989D\u5EA6";        // Extra Usage balance
            _panelSym = "\u00A5";
            _panelSuffix = "";
        }
        Log("kimi ok: planUsed=" + (double.IsNaN(used) ? "?" : used.ToString("0.####", CultureInfo.InvariantCulture)) +
            " planRemain=" + (double.IsNaN(planRemain) ? "?" : planRemain.ToString("0.##", CultureInfo.InvariantCulture)) +
            " extraLeft=" + (double.IsNaN(extraCny) ? "?" : extraCny.ToString("0.00", CultureInfo.InvariantCulture)) +
            " mode=" + (_panelSuffix.Length > 0 ? "plan%" : "extraCNY") +
            (string.IsNullOrEmpty(notice) ? "" : " notice=" + Trunc(notice)));
        return true;
    }

'''

rep("    string FetchBalance() {\n", KIMI_LAYER + "    string FetchBalance() {\n", "kimi layer")

# ------------------------------------------------------- 13. 数值文本格式 ----
rep(
    "    string BalanceText() {\n"
    "        return double.IsNaN(DrawnBalance) ? \"--\"\n"
    "             : DrawnBalance.ToString(\"0.00\", CultureInfo.InvariantCulture);\n"
    "    }\n",
    "    string BalanceText() {\n"
    "        if (double.IsNaN(DrawnBalance)) return \"--\";\n"
    "        // Percentage mode reads better without decimals; CNY keeps its cents.\n"
    "        return _panelSuffix.Length > 0\n"
    "             ? DrawnBalance.ToString(\"0\", CultureInfo.InvariantCulture)\n"
    "             : DrawnBalance.ToString(\"0.00\", CultureInfo.InvariantCulture);\n"
    "    }\n",
    "BalanceText",
)

# --------------------------------------------- 14. 面板绘制：符号与后缀 ----
rep(
    "                    SizeF sc = g.MeasureString(\"\\u00A5\", fc);\n",
    "                    SizeF sc = g.MeasureString(_panelSym, fc);\n"
    "                    SizeF ssuf = g.MeasureString(_panelSuffix, fc);\n",
    "panel measure",
)
rep(
    "                        float total = sb.Width + sc.Width;\n",
    "                        float total = sb.Width + sc.Width + ssuf.Width;\n",
    "panel total width",
)
rep(
    "                        g.DrawString(\"\\u00A5\", fc, sh, left + 1.5f, top + sb.Height * 0.24f + 1.5f);\n"
    "                        g.DrawString(txt, fb, sh, left + sc.Width + 1.5f, top + 1.5f);\n"
    "                        g.DrawString(\"\\u00A5\", fc, bc, left, top + sb.Height * 0.24f);\n"
    "                        g.DrawString(txt, fb, bb, left + sc.Width, top);\n",
    "                        g.DrawString(_panelSym, fc, sh, left + 1.5f, top + sb.Height * 0.24f + 1.5f);\n"
    "                        g.DrawString(txt, fb, sh, left + sc.Width + 1.5f, top + 1.5f);\n"
    "                        g.DrawString(_panelSuffix, fc, sh, left + sc.Width + sb.Width + 1.5f,\n"
    "                                     top + sb.Height * 0.24f + 1.5f);\n"
    "                        g.DrawString(_panelSym, fc, bc, left, top + sb.Height * 0.24f);\n"
    "                        g.DrawString(txt, fb, bb, left + sc.Width, top);\n"
    "                        g.DrawString(_panelSuffix, fc, bc, left + sc.Width + sb.Width,\n"
    "                                     top + sb.Height * 0.24f);\n",
    "panel draws",
)
rep(
    "                    g.DrawString(S_LABEL, f, shadow, new RectangleF(lr.X + 1.5f, lr.Y + 1.5f, lr.Width, lr.Height), sf);\n"
    "                    g.DrawString(S_LABEL, f, b, lr, sf);\n",
    "                    g.DrawString(_panelLabel, f, shadow, new RectangleF(lr.X + 1.5f, lr.Y + 1.5f, lr.Width, lr.Height), sf);\n"
    "                    g.DrawString(_panelLabel, f, b, lr, sf);\n",
    "panel label",
)

# --------------------------------------------------------- 15. 飘字单位 ----
rep(
    "        fl.Text = \"-\" + amount.ToString(\"0.####\", CultureInfo.InvariantCulture);\n",
    "        string amt = amount >= 1.0 ? amount.ToString(\"0.##\", CultureInfo.InvariantCulture)\n"
    "                                   : amount.ToString(\"0.####\", CultureInfo.InvariantCulture);\n"
    "        fl.Text = \"-\" + amt + _panelSuffix;\n",
    "floater text",
)

# --------------------------------------------------------- 16. 步进 _step ----
rep(
    "                if (_pending >= StepYuan - 1e-9) take = StepYuan;\n",
    "                if (_pending >= _step - 1e-9) take = _step;\n",
    "take step",
)
rep(
    "                double cap = StepYuan * MaxCuesPerPoll;\n",
    "                double cap = _step * MaxCuesPerPoll;\n",
    "debt cap",
)

# ------------------------------------------------------------------- apply ---
for e in EDITS:
    if e[0] == "replace":
        _, old, new, tag = e
        n = s.count(old)
        if n != 1:
            raise SystemExit("anchor '%s' matched %d times (expected 1)" % (tag, n))
        s = s.replace(old, new, 1)
    elif e[0] == "replace_all":
        _, old, new, tag = e
        n = s.count(old)
        if n < 1:
            raise SystemExit("anchor '%s' not found" % tag)
        s = s.replace(old, new)
    else:
        _, start, end, new, tag, keep_end = e
        i = s.find(start)
        if i < 0:
            raise SystemExit("splice start for '%s' not found" % tag)
        j = s.find(end, i + len(start))
        if j < 0:
            raise SystemExit("splice end for '%s' not found" % tag)
        tail = s[j:] if keep_end else s[j + len(end):]
        s = s[:i] + new + tail

assert all(ord(c) < 128 for c in s), "non-ASCII introduced"
with open(DST, "w", encoding="ascii", newline="") as fh:
    fh.write(s)
print("written %s (%d bytes, %d edits)" % (DST, len(s), len(EDITS)))

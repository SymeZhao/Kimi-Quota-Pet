<#
  kimi_quota.ps1  --  第 1 步：Kimi 会员额度数据适配器（只读）

  做什么：
    1) 从 Kimi 桌面版的本机登录态里取出 access_token
       来源： %APPDATA%\kimi-desktop\Local Storage\leveldb
       方式： 以共享读打开文件（不复制、不写、不改 Kimi 任何数据），
              正规解析 leveldb WAL 记录拿到精确的键值，失败则退回正则兜底
    2) 用它调用 Kimi 官方额度接口
       POST https://www.kimi.com/apiv2/kimi.gateway.membership.v2.MembershipService/GetSubscriptionStats
    3) 解析出「剩余额度百分比 / 重置时间 / 额度包」，打印给人看，并把脱敏原始 JSON 存一份

  不做什么：
    * 不调用 RefreshToken（不碰你的 refresh_token，不会让桌面版掉线）
    * 不消耗任何额度、不写 Kimi 目录、不改注册表
    * token 只在本进程内存里用：日志与样本 JSON 里都不含 token

  用法（PowerShell 5.1 / 7 均可）：
    powershell -NoProfile -ExecutionPolicy Bypass -File kimi_quota.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File kimi_quota.ps1 -Raw      # 额外打印完整 JSON
    powershell -NoProfile -ExecutionPolicy Bypass -File kimi_quota.ps1 -Json     # 只输出一行机器可读结果
#>
param(
    [switch]$Raw,
    [switch]$Json,
    [int]$TimeoutSec = 20
)

$ErrorActionPreference = 'Stop'
$script:Here = $PSScriptRoot
if (-not $script:Here) { $script:Here = (Get-Location).Path }
$script:SampleFile = Join-Path $script:Here 'kimi_quota_sample.json'
$script:LogFile = Join-Path $script:Here 'kimi_quota.log'

$script:StatsUrl = 'https://www.kimi.com/apiv2/kimi.gateway.membership.v2.MembershipService/GetSubscriptionStats'
$script:SubUrl = 'https://www.kimi.com/apiv2/kimi.gateway.membership.v2.MembershipService/GetSubscription'

function Write-Log([string]$msg) {
    try {
        $line = (Get-Date).ToString('s') + ' ' + $msg
        Add-Content -LiteralPath $script:LogFile -Value $line -Encoding UTF8
    } catch { }
}

# --------------------------------------------------------------- file access --
# Chrome/Electron keeps leveldb files open with share-read; open with the same
# sharing flags so we can read a live database without touching it.
function Read-FileShared([string]$path) {
    $share = [System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete
    $fs = New-Object System.IO.FileStream($path, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, $share)
    try {
        $ms = New-Object System.IO.MemoryStream
        $fs.CopyTo($ms)
        return $ms.ToArray()
    } finally {
        $fs.Dispose()
    }
}

function Read-Varint([byte[]]$b, [ref]$i) {
    $val = 0; $shift = 0
    while ($i.Value -lt $b.Length) {
        $by = $b[$i.Value]; $i.Value++
        $val = $val -bor ((($by -band 0x7F)) -shl $shift)
        if (($by -band 0x80) -eq 0) { return $val }
        $shift += 7
        if ($shift -gt 35) { break }
    }
    return -1
}

# Local Storage values carry a 1-byte encoding tag: 0 = UTF-16LE, 1 = UTF-8/Latin-1
function ConvertFrom-LsValue([byte[]]$v) {
    if ($v.Length -eq 0) { return '' }
    if ($v.Length -ge 4 -and $v[1] -eq 0 -and $v[0] -ne 0) {
        return [System.Text.Encoding]::Unicode.GetString($v)
    }
    $tag = $v[0]
    if ($tag -eq 0) {
        $n = $v.Length - 1
        if ($n % 2 -ne 0) { $n = $n - 1 }
        if ($n -le 0) { return '' }
        return [System.Text.Encoding]::Unicode.GetString($v, 1, $n)
    }
    if ($tag -eq 1) { return [System.Text.Encoding]::UTF8.GetString($v, 1, $v.Length - 1) }
    return [System.Text.Encoding]::UTF8.GetString($v)
}

function ConvertFrom-WriteBatch([byte[]]$d) {
    $res = @{}
    if ($d.Length -lt 12) { return $res }
    $count = [BitConverter]::ToUInt32($d, 8)
    $i = 12
    for ($k = 0; $k -lt $count; $k++) {
        if ($i -ge $d.Length) { break }
        $tag = $d[$i]; $i++
        $ref = [ref]$i
        $klen = Read-Varint $d $ref
        $i = $ref.Value
        if ($klen -lt 0 -or ($i + $klen) -gt $d.Length) { break }
        $key = [System.Text.Encoding]::UTF8.GetString($d, $i, $klen)
        $i += $klen
        if ($tag -eq 0) { continue }                       # deletion
        $ref = [ref]$i
        $vlen = Read-Varint $d $ref
        $i = $ref.Value
        if ($vlen -lt 0 -or ($i + $vlen) -gt $d.Length) { break }
        $val = New-Object byte[] $vlen
        if ($vlen -gt 0) { [Array]::Copy($d, $i, $val, 0, $vlen) }
        $i += $vlen
        $name = ($key -split "[`0`1]")[-1]
        $res[$name] = (ConvertFrom-LsValue $val)
    }
    return $res
}

# leveldb write-ahead log: [crc u32][len u16][type u8][payload], 32 KB blocks
function Read-LevelDbLog([byte[]]$b) {
    $records = New-Object System.Collections.ArrayList
    $blockSize = 32768
    $pos = 0
    $pending = $null
    while (($pos + 7) -le $b.Length) {
        $blockLeft = $blockSize - ($pos % $blockSize)
        if ($blockLeft -lt 7) { $pos += $blockLeft; continue }
        $len = [BitConverter]::ToUInt16($b, $pos + 4)
        $type = $b[$pos + 6]
        $pos += 7
        if ($type -eq 0) { continue }
        if ($len -eq 0 -or ($pos + $len) -gt $b.Length) { break }
        $data = New-Object byte[] $len
        [Array]::Copy($b, $pos, $data, 0, $len)
        $pos += $len
        switch ($type) {
            1 { [void]$records.Add($data) }
            2 { $pending = New-Object System.IO.MemoryStream; $pending.Write($data, 0, $data.Length) }
            3 { if ($pending) { $pending.Write($data, 0, $data.Length) } }
            4 {
                if ($pending) {
                    $pending.Write($data, 0, $data.Length)
                    [void]$records.Add($pending.ToArray())
                    $pending = $null
                }
            }
        }
    }
    return , $records
}

# --------------------------------------------------------------- jwt helpers --
function ConvertFrom-Base64Url([string]$s) {
    $t = $s.Replace('-', '+').Replace('_', '/')
    switch ($t.Length % 4) {
        2 { $t += '==' }
        3 { $t += '=' }
    }
    return [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($t))
}

function Get-JwtClaims([string]$token) {
    try {
        $parts = $token.Split('.')
        if ($parts.Length -ne 3) { return $null }
        return (ConvertFrom-Base64Url $parts[1]) | ConvertFrom-Json
    } catch { return $null }
}

# ------------------------------------------------------------ token discovery --
function Get-KimiTokens {
    $lsDir = Join-Path $env:APPDATA 'kimi-desktop\Local Storage\leveldb'
    $result = @{ Dir = $lsDir; Found = (New-Object System.Collections.ArrayList); Error = $null }
    if (-not (Test-Path -LiteralPath $lsDir)) {
        $result.Error = '没有找到 Kimi 桌面版数据目录（Kimi 桌面版没装过？）'
        return $result
    }

    $files = @(Get-ChildItem -LiteralPath $lsDir -File -ErrorAction SilentlyContinue |
               Where-Object { $_.Extension -in '.log', '.ldb' } |
               Sort-Object LastWriteTime -Descending)

    # pass 1: real leveldb WAL parsing (exact values)
    foreach ($f in $files) {
        if ($f.Length -eq 0) { continue }
        try { $bytes = Read-FileShared $f.FullName } catch { continue }
        if ($f.Extension -ne '.log') { continue }          # .ldb tables need block decoding; WAL is where fresh tokens live
        try { $records = Read-LevelDbLog $bytes } catch { continue }
        foreach ($rec in $records) {
            $pairs = $null
            try { $pairs = ConvertFrom-WriteBatch $rec } catch { continue }
            if (-not $pairs) { continue }
            foreach ($k in $pairs.Keys) {
                if ($k -eq 'access_token' -or $k -eq 'refresh_token' -or $k -like '*access_token*') {
                    $v = [string]$pairs[$k]
                    if ($v.Length -ge 40 -and $v.StartsWith('eyJ')) {
                        [void]$result.Found.Add(@{ Name = $k; Value = $v; File = $f.Name; How = 'wal' })
                    }
                }
            }
        }
    }

    # pass 2: regex fallback over every file (covers compacted .ldb / odd layouts)
    if ($result.Found.Count -eq 0) {
        $latin = [System.Text.Encoding]::GetEncoding(28591)
        foreach ($f in $files) {
            if ($f.Length -eq 0) { continue }
            try { $bytes = Read-FileShared $f.FullName } catch { continue }
            $text = $latin.GetString($bytes)
            foreach ($m in [regex]::Matches($text, 'access_token')) {
                $start = $m.Index + $m.Length
                $len = [Math]::Min(900, $text.Length - $start)
                if ($len -le 0) { continue }
                $seg = $text.Substring($start, $len)
                foreach ($jm in [regex]::Matches($seg, '[A-Za-z0-9_\-\.]{100,}')) {
                    $cand = $jm.Value
                    if ($cand.StartsWith('eyJ') -and $cand.Split('.').Length -eq 3) {
                        [void]$result.Found.Add(@{ Name = 'access_token'; Value = $cand; File = $f.Name; How = 'regex' })
                    }
                }
            }
            if ($result.Found.Count -gt 0) { break }
        }
    }

    return $result
}

# ---------------------------------------------------------------- http call ---
function Invoke-KimiPost([string]$url, [string]$token, [int]$timeoutSec) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Method = 'POST'
    $req.ContentType = 'application/json'
    $req.Accept = 'application/json'
    $req.UserAgent = 'kimi-quota-adapter/0.1'
    $req.Timeout = $timeoutSec * 1000
    $req.Headers.Add('Connect-Protocol-Version', '1')
    $req.Headers.Add('Authorization', 'Bearer ' + $token)
    $payload = [System.Text.Encoding]::UTF8.GetBytes('{}')
    $req.ContentLength = $payload.Length
    $st = $req.GetRequestStream()
    $st.Write($payload, 0, $payload.Length)
    $st.Close()

    try {
        $resp = $req.GetResponse()
    } catch [System.Net.WebException] {
        $r = $_.Exception.Response
        if ($r) {
            $sr = New-Object System.IO.StreamReader($r.GetResponseStream(), [System.Text.Encoding]::UTF8)
            $body = $sr.ReadToEnd(); $sr.Close()
            return @{ Status = [int]$r.StatusCode; Body = $body }
        }
        throw
    }
    $sr = New-Object System.IO.StreamReader($resp.GetResponseStream(), [System.Text.Encoding]::UTF8)
    $body = $sr.ReadToEnd(); $sr.Close()
    $code = [int]$resp.StatusCode
    $resp.Close()
    return @{ Status = $code; Body = $body }
}

# --------------------------------------------------------- response parsing ---
function Get-List($node, [string]$name) {
    # Callers must wrap the result in @(): a 1-element array returned from a
    # function gets unwrapped, so the call site re-wraps it to keep indexing sane.
    if (-not $node) { return @() }
    $p = $node.PSObject.Properties[$name]
    if (-not $p) { return @() }
    if ($null -eq $p.Value) { return @() }
    if ($p.Value -is [System.Array]) { return $p.Value }
    return @($p.Value)
}

function Get-Cny($money) {
    if (-not $money) { return $null }
    if (-not $money.PSObject.Properties['priceInCents']) { return $null }
    $cents = [double]$money.priceInCents
    return [Math]::Round($cents / 100, 2)
}

function Format-Epoch([object]$v) {
    if (-not $v) { return '' }
    try { return ([DateTimeOffset]::FromUnixTimeSeconds([int64]$v)).ToLocalTime().ToString('yyyy-MM-dd HH:mm:ss') } catch { return [string]$v }
}

function Show-Quota([string]$body) {
    $j = $body | ConvertFrom-Json
    $lines = New-Object System.Collections.ArrayList
    $subs = @(Get-List $j 'subscriptionBalance')
    if ($subs.Count -eq 0) { [void]$lines.Add('未返回 subscriptionBalance（额度结构可能变了，看样本 JSON）') }
    foreach ($s in $subs) {
        $used = $null
        if ($s.PSObject.Properties['amountUsedRatio']) { $used = [double]$s.amountUsedRatio }
        $codeUsed = $null
        if ($s.PSObject.Properties['kimiCodeUsedRatio']) { $codeUsed = [double]$s.kimiCodeUsedRatio }
        $feat = [string]$s.feature; $unit = [string]$s.unit; $dom = [string]$s.domain
        if ($null -ne $used) {
            [void]$lines.Add(('  会员额度  : {0} / {1} / {2}  已用 {3:N2}%  ->  剩余 {4:N2}%' -f $feat, $unit, $dom, ($used * 100), ((1 - $used) * 100)))
        }
        if ($null -ne $codeUsed) {
            [void]$lines.Add(('  Kimi Code : 已用 {0:N2}%  ->  剩余 {1:N2}%' -f ($codeUsed * 100), ((1 - $codeUsed) * 100)))
        }
        if ($s.PSObject.Properties['expireTime'] -and $s.expireTime) {
            [void]$lines.Add(('  到期时间  : {0}' -f $s.expireTime))
        }
        if ($s.PSObject.Properties['upcomingExpiration'] -and $s.upcomingExpiration.timestamp) {
            [void]$lines.Add(('  下一周期  : {0}' -f $s.upcomingExpiration.timestamp))
        }
    }
    foreach ($w in @('ratelimitCode5h', 'ratelimitCode7d')) {
        $p = $j.PSObject.Properties[$w]
        if ($p -and $p.Value) {
            $en = $p.Value.enabled
            [void]$lines.Add(('  {0,-9} : enabled={1}  reset={2}' -f $w, $en, $p.Value.resetTime))
        }
    }
    $wallets = @(Get-List $j 'boosterWallets')
    [void]$lines.Add(('  额外额度  : {0} 个钱包' -f $wallets.Count))
    foreach ($w in $wallets) {
        $left = Get-Cny $w.moneyLeft
        $total = Get-Cny $w.moneyTotal
        $usedM = Get-Cny $w.monthlyUsed
        $lim = Get-Cny $w.topupLimit
        [void]$lines.Add(('             余额 {0} / {1} 元   (本月已用 {2} 元, 状态 {3}, 可充值 {4}, 充值上限 {5} 元)' -f `
            $left, $total, $usedM, $w.status, $w.allowTopup, $lim))
    }
    $nt = $j.PSObject.Properties['notice']
    if ($nt -and $nt.Value -and $nt.Value.tip) {
        [void]$lines.Add(('  站内提示  : {0}' -f $nt.Value.tip))
    }
    [void]$lines.Add(('  顶层字段  : {0}' -f (($j.PSObject.Properties | ForEach-Object { $_.Name }) -join ', ')))
    return $lines
}

# -------------------------------------------------------------------- main ----
function Main {
    $now = [int][DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    $t = Get-KimiTokens
    if ($t.Error) { throw $t.Error }
    if ($t.Found.Count -eq 0) {
        throw ('没有从本机读到可用的 access_token' + "`n" +
               '  - 请确认 Kimi 桌面版已经登录并处于运行状态（它在后台持续续期，关闭后 token 几分钟就失效）' + "`n" +
               ('  - 数据目录： {0}' -f $t.Dir))
    }

    $best = $null
    foreach ($c in $t.Found) {
        $claims = Get-JwtClaims $c.Value
        $exp = $null
        if ($claims -and $claims.PSObject.Properties['exp']) { $exp = [int64]$claims.exp }
        if ($null -eq $exp) { continue }
        if ($exp -le ($now + 15)) { continue }               # already (nearly) expired
        if ((-not $best) -or ($exp -gt $best.Exp)) {
            $best = @{ Token = $c.Value; Exp = $exp; File = $c.File; How = $c.How; Claims = $claims }
        }
    }
    if (-not $best) {
        $expList = ($t.Found | ForEach-Object { $c = Get-JwtClaims $_.Value; if ($c) { Format-Epoch $c.exp } else { '?' } }) -join ', '
        throw ('读到了 token 但都已过期（exp: {0}）' -f $expList + "`n" +
               '  - 打开 Kimi 桌面版，等它刷新一次登录态再试（token 生命周期只有几分钟）')
    }

    $ttl = $best.Exp - $now
    $resp = Invoke-KimiPost $script:StatsUrl $best.Token $TimeoutSec

    if (-not $Json) {
        Write-Host ''
        Write-Host 'Kimi 会员额度（只读适配器）' -ForegroundColor Cyan
        Write-Host ('  数据来源  : {0}  [{1}]' -f $t.Dir, $best.File)
        Write-Host ('  取值方式  : {0} 解析' -f $(if ($best.How -eq 'wal') { 'leveldb WAL 正规' } else { '正则兜底' }))
        Write-Host ('  令牌状态  : 有效，还有 {0} 分 {1} 秒（到期 {2}）' -f [int]($ttl / 60), ($ttl % 60), (Format-Epoch $best.Exp))
        if ($best.Claims) {
            $mLevel = ''
            $cLevel = ''
            if ($best.Claims.PSObject.Properties['membership'] -and $best.Claims.membership) { $mLevel = [string]$best.Claims.membership.level }
            if ($best.Claims.PSObject.Properties['code_membership'] -and $best.Claims.code_membership) { $cLevel = [string]$best.Claims.code_membership.level }
            Write-Host ('  账号标识  : membership.level={0}  code_membership.level={1}' -f $mLevel, $cLevel)
        }
        Write-Host ('  接口结果  : HTTP {0}  ({1} 字节)' -f $resp.Status, $resp.Body.Length)
    }

    $summary = $null
    if ($resp.Status -eq 200) {
        try {
            $lines = Show-Quota $resp.Body
            if (-not $Json) { foreach ($l in $lines) { Write-Host $l } }
            $j = $resp.Body | ConvertFrom-Json
            $subs = @(Get-List $j 'subscriptionBalance')
            $usedRatio = $null
            $codeRatio = $null
            if ($subs.Count -gt 0) {
                if ($subs[0].PSObject.Properties['amountUsedRatio']) { $usedRatio = [double]$subs[0].amountUsedRatio }
                if ($subs[0].PSObject.Properties['kimiCodeUsedRatio']) { $codeRatio = [double]$subs[0].kimiCodeUsedRatio }
            }
            $wallets = @(Get-List $j 'boosterWallets')
            $left = $null; $total = $null; $usedM = $null
            if ($wallets.Count -gt 0) {
                $left = Get-Cny $wallets[0].moneyLeft
                $total = Get-Cny $wallets[0].moneyTotal
                $usedM = Get-Cny $wallets[0].monthlyUsed
            }
            $tip = $null
            $nt = $j.PSObject.Properties['notice']
            if ($nt -and $nt.Value -and $nt.Value.tip) { $tip = [string]$nt.Value.tip }
            $summary = @{
                ok = $true
                remaining_percent = $(if ($null -ne $usedRatio) { [Math]::Round((1 - $usedRatio) * 100, 2) } else { $null })
                used_percent = $(if ($null -ne $usedRatio) { [Math]::Round($usedRatio * 100, 2) } else { $null })
                kimi_code_remaining_percent = $(if ($null -ne $codeRatio) { [Math]::Round((1 - $codeRatio) * 100, 2) } else { $null })
                extra_usage_left_cny = $left
                extra_usage_total_cny = $total
                extra_usage_month_used_cny = $usedM
                plan_expire_time = $(if ($subs.Count -gt 0 -and $subs[0].expireTime) { [string]$subs[0].expireTime } else { $null })
                notice = $tip
                token_ttl_seconds = $ttl
                token_source = $best.File
            }
        } catch {
            $summary = @{ ok = $false; error = '返回不是合法 JSON: ' + $_.Exception.Message }
            if (-not $Json) { Write-Host ('  解析失败  : {0}' -f $_.Exception.Message) -ForegroundColor Yellow }
        }
        try {
            $resp.Body | Set-Content -LiteralPath $script:SampleFile -Encoding UTF8
            if (-not $Json) { Write-Host ('  原始样本  : {0}（不含 token，可直接打开看）' -f $script:SampleFile) }
        } catch { }
        Write-Log ('ok http=200 ttl={0}s source={1} remaining={2}' -f $ttl, $best.File, $summary.remaining_percent)
    } else {
        if (-not $Json) {
            Write-Host ('  接口失败  : HTTP {0}' -f $resp.Status) -ForegroundColor Yellow
            Write-Host ('  返回内容  : {0}' -f $resp.Body)
            if ($resp.Status -eq 401 -or $resp.Status -eq 403) {
                Write-Host '  -> token 被拒：可能是刚过期，打开 Kimi 桌面版刷新一下再试' -ForegroundColor Yellow
            }
        }
        $summary = @{ ok = $false; error = ('HTTP ' + $resp.Status); status = $resp.Status }
        Write-Log ('fail http={0} ttl={1}s source={2}' -f $resp.Status, $ttl, $best.File)
    }

    if ($Raw -and -not $Json) {
        Write-Host ''
        Write-Host '--- 完整 JSON ---'
        Write-Host $resp.Body
    }
    if ($Json) {
        Write-Host ($summary | ConvertTo-Json -Compress)
    }
    Write-Host ''
}

try {
    Main
    exit 0
} catch {
    $msg = $_.Exception.Message
    if ($Json) {
        Write-Host (@{ ok = $false; error = $msg } | ConvertTo-Json -Compress)
    } else {
        Write-Host ''
        Write-Host '读取失败：' -ForegroundColor Red
        Write-Host $msg
        Write-Host ''
    }
    Write-Log ('error ' + ($msg -replace "`r?`n", ' | '))
    exit 1
}

# 毎日取得（daily_fetch.py）を Windows のタスクスケジューラに登録する。
# 使い方（リポジトリのルートで）:
#   powershell -ExecutionPolicy Bypass -File .claude\skills\x-account-fetch\scripts\register_daily_task.ps1
#   powershell -ExecutionPolicy Bypass -File .claude\skills\x-account-fetch\scripts\register_daily_task.ps1 -At 07:30
# 試しに今すぐ動かす:  Start-ScheduledTask -TaskName lollpop_daily_fetch
# 結果を見る:          Get-ScheduledTaskInfo -TaskName lollpop_daily_fetch   （LastTaskResult 0 が成功）
# 解除する:            Unregister-ScheduledTask -TaskName lollpop_daily_fetch -Confirm:$false
#
# このファイルは Windows PowerShell 5.1 が日本語を読めるよう UTF-8（BOM 付き）で保存している。

param(
    [string]$At = "06:00",
    [string]$TaskName = "lollpop_daily_fetch"
)

$ErrorActionPreference = "Stop"
# 手元のチェックアウト（取得データ work\x_fetch\ を持つ本体）。どのワークツリーからこのファイルを実行しても本体を指すよう、
# 共有の .git の場所から求める（専用ワークツリーから実行しても、データの置き場を取り違えないため）
$commonDir = (& git -C $PSScriptRoot rev-parse --path-format=absolute --git-common-dir).Trim()
if ($LASTEXITCODE -ne 0) { throw "git の場所を求められない: $PSScriptRoot" }
$repoRoot = (Resolve-Path (Split-Path $commonDir -Parent)).Path
$script = Join-Path $repoRoot ".claude\skills\x-account-fetch\scripts\daily_fetch.py"

# セトリ取り込み専用のワークツリー。毎朝 run_latest.py が origin/main に合わせてから回すので、ここでは作業しない。
# 手元のチェックアウトは別セッションがブランチを切り替えて使うため、そこのスクリプトだと main の修正が効かない（2026-10-13）
$cronRoot = "${repoRoot}_wt_cron"
if (-not (Test-Path $cronRoot)) {
    & git -C $repoRoot fetch -q origin main
    & git -C $repoRoot worktree add -q --detach $cronRoot origin/main
    if ($LASTEXITCODE -ne 0) { throw "専用ワークツリーを作れない: $cronRoot" }
}

# python3 のシムや WindowsApps のスタブはタスクスケジューラから呼べないことがあるので、実体の pythonw.exe を使う。
# pythonw はコンソール窓を出さない（毎朝ウィンドウが開かない）。出力は work/x_fetch/logs/daily_fetch.log に残る
$python = (Get-Command python -ErrorAction Stop).Source
if ($python -like "*WindowsApps*") {
    throw "python が WindowsApps のスタブに解決された: $python。Python 本体のパスを PATH の先に置いてから再実行する"
}
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "pythonw.exe が見つからない: $pythonw" }

# 取得のあとに、セトリの取り込み PR を作ってマージするスクリプトを続けて回す（タスクの Action は上から順に実行される）。
# 専用ワークツリーの run_latest.py が origin/main に合わせてから daily_setlist_pr.py を呼ぶ。gh が PATH に無ければ PR 側だけが中断してログに残る
$prScript = Join-Path $cronRoot ".claude\skills\setlist-analysis\scripts\run_latest.py"
# 最後に、取得データを非公開リポジトリ lollpop_data へ退避する（ID で和集合を取って積み増す。main に直接 push）。
# 取得が失敗した日も回してよい（変化が無ければコミットしない）
$pushScript = Join-Path $repoRoot ".claude\skills\x-data-sync\scripts\sync_x_data.py"
$pushLog = Join-Path $repoRoot "work\x_fetch\logs\daily_data_push.log"
$action = @(
    (New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $repoRoot),
    (New-ScheduledTaskAction -Execute $pythonw -Argument "`"$prScript`" --data-root `"$repoRoot`"" -WorkingDirectory $cronRoot),
    (New-ScheduledTaskAction -Execute $pythonw -Argument "`"$pushScript`" push --log `"$pushLog`"" -WorkingDirectory $repoRoot)
)
$trigger = New-ScheduledTaskTrigger -Daily -At $At
# StartWhenAvailable: PC が止まっていて時刻を逃したら、次に起動したときに回す（取れなかった日は次の実行でまとめて取る）
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
# ログオン中だけ実行する。パスワードをタスクに保存しないため
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "lollpop_docs: X 投稿を毎日取得し（daily_fetch.py）、セトリの取り込み PR を作り（daily_setlist_pr.py）、lollpop_data へ退避する（sync_x_data.py push）" -Force | Out-Null

Write-Output "登録した: $TaskName（毎日 $At）"
Write-Output "  実行1: $pythonw `"$script`""
Write-Output "  実行2: $pythonw `"$prScript`" --data-root `"$repoRoot`"（作業フォルダ: $cronRoot）"
Write-Output "  実行3: $pythonw `"$pushScript`" push --log `"$pushLog`""
Write-Output "  作業フォルダ: $repoRoot"

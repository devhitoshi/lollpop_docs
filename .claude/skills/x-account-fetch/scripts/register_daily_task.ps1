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
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..\..\..")).Path
$script = Join-Path $PSScriptRoot "daily_fetch.py"

# python3 のシムや WindowsApps のスタブはタスクスケジューラから呼べないことがあるので、実体の pythonw.exe を使う。
# pythonw はコンソール窓を出さない（毎朝ウィンドウが開かない）。出力は work/x_fetch/logs/daily_fetch.log に残る
$python = (Get-Command python -ErrorAction Stop).Source
if ($python -like "*WindowsApps*") {
    throw "python が WindowsApps のスタブに解決された: $python。Python 本体のパスを PATH の先に置いてから再実行する"
}
$pythonw = Join-Path (Split-Path $python) "pythonw.exe"
if (-not (Test-Path $pythonw)) { throw "pythonw.exe が見つからない: $pythonw" }

# 取得のあとに、セトリの取り込み PR を作るスクリプトを続けて回す（タスクの Action は上から順に実行される）。
# PR を作るところまでで、マージはしない。gh が PATH に無ければ PR 側だけが中断してログに残る
$prScript = Join-Path $repoRoot ".claude\skills\setlist-analysis\scripts\daily_setlist_pr.py"
$action = @(
    (New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $repoRoot),
    (New-ScheduledTaskAction -Execute $pythonw -Argument "`"$prScript`"" -WorkingDirectory $repoRoot)
)
$trigger = New-ScheduledTaskTrigger -Daily -At $At
# StartWhenAvailable: PC が止まっていて時刻を逃したら、次に起動したときに回す（取れなかった日は次の実行でまとめて取る）
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit (New-TimeSpan -Hours 1) -MultipleInstances IgnoreNew
# ログオン中だけ実行する。パスワードをタスクに保存しないため
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal `
    -Description "lollpop_docs: X 投稿を毎日取得し（daily_fetch.py）、セトリの取り込み PR を作る（daily_setlist_pr.py）" -Force | Out-Null

Write-Output "登録した: $TaskName（毎日 $At）"
Write-Output "  実行1: $pythonw `"$script`""
Write-Output "  実行2: $pythonw `"$prScript`""
Write-Output "  作業フォルダ: $repoRoot"

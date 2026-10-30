param([string]$PythonExe)
$ErrorActionPreference = 'Stop'
if (-not $PythonExe) { $PythonExe = (& py -3 -c 'import sys; print(sys.executable)').Trim() }
$root = Split-Path $PSScriptRoot
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('codex-alerts-gui-' + [guid]::NewGuid().ToString('N'))
$target = Join-Path $testRoot 'App'
$codex = Join-Path $testRoot 'Codex'
& (Join-Path $root 'install.ps1') -PythonExe $PythonExe -InstallDir $target -CodexHome $codex -NoStart -NoShortcuts | Out-Null
try {
    & $PythonExe (Join-Path $target 'alerts.py') --test
    $deadline = [DateTime]::UtcNow.AddSeconds(15)
    $success = $false
    while ([DateTime]::UtcNow -lt $deadline) {
        Start-Sleep -Milliseconds 500
        $state = & $PythonExe (Join-Path $target 'alerts.py') --status | ConvertFrom-Json
        if ($state.running -and $state.status.window_visible -and $state.status.pending_alerts -gt 0) {
            $success = $true
            break
        }
    }
    if (-not $success) { throw 'GUI did not report a mapped window and pending test event.' }
    Write-Output 'PASS: isolated Python/Tk/Win32 daemon initialized and mapped a test popup.'
    Write-Output 'This checks program state; a person must still verify actual visibility and usability.'
} finally {
    & (Join-Path $target 'uninstall.ps1') | Out-Null
}

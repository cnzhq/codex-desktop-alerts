param([string]$PythonExe)
$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot
$testRoot = Join-Path ([IO.Path]::GetTempPath()) ('codex-alerts-integration-' + [guid]::NewGuid().ToString('N'))
$target = Join-Path $testRoot 'App With Spaces'
$codex = Join-Path $testRoot 'Codex With Spaces'
New-Item -ItemType Directory -Path $codex -Force | Out-Null
$original = '{"description":"test","hooks":{"Stop":[{"hooks":[{"type":"command","command":"echo keep"}]}]}}'
[IO.File]::WriteAllText((Join-Path $codex 'hooks.json'), $original)
if (-not $PythonExe) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe = (& py -3 -c 'import sys; print(sys.executable)').Trim()
    } else { $PythonExe = (& python -c 'import sys; print(sys.executable)').Trim() }
}
& (Join-Path $root 'install.ps1') -PythonExe $pythonExe -InstallDir $target -CodexHome $codex -Preview -NoStart -NoShortcuts
if (Test-Path -LiteralPath $target) { throw 'Preview wrote files.' }
& (Join-Path $root 'install.ps1') -PythonExe $pythonExe -InstallDir $target -CodexHome $codex -NoStart -NoShortcuts
$first = Get-Content -LiteralPath (Join-Path $codex 'hooks.json') -Raw
& (Join-Path $root 'install.ps1') -PythonExe $pythonExe -InstallDir $target -CodexHome $codex -NoStart -NoShortcuts
if ((Get-Content -LiteralPath (Join-Path $codex 'hooks.json') -Raw) -ne $first) { throw 'Not idempotent.' }
$runtimeStatus = & $pythonExe (Join-Path $target 'alerts.py') --status | ConvertFrom-Json
if ($runtimeStatus.location -ne $target) { throw 'Custom install directory ignored by runtime.' }
& (Join-Path $target 'uninstall.ps1')
$restored = Get-Content -LiteralPath (Join-Path $codex 'hooks.json') -Raw | ConvertFrom-Json
if ($restored.hooks.Stop.Count -ne 1 -or $restored.hooks.Stop[0].hooks[0].command -ne 'echo keep') { throw 'Other hooks changed.' }
Write-Output ('PASS: isolated install/upgrade/uninstall; artifacts retained at ' + $testRoot)

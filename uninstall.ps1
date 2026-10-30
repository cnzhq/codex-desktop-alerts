[CmdletBinding()]
param([string]$InstallDir = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$InstallDir = (Resolve-Path -LiteralPath $InstallDir).Path
$manifestPath = Join-Path $InstallDir 'manifest.json'
if (-not (Test-Path -LiteralPath $manifestPath)) { throw 'Pass -InstallDir pointing to an installed copy.' }
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$pythonExe = $manifest.python_exe
& $pythonExe (Join-Path $InstallDir 'manage.py') uninstall --install-dir $InstallDir
if ($LASTEXITCODE -ne 0) { throw 'Hook cleanup failed; shortcuts were retained. Review the error above.' }
$shell = New-Object -ComObject WScript.Shell
$allowedNames = @('Codex Desktop Alerts.lnk', 'Codex Alerts.lnk', 'Test Codex Alerts.lnk')
foreach ($shortcutPath in @($manifest.shortcuts)) {
    if (($allowedNames -contains [IO.Path]::GetFileName($shortcutPath)) -and (Test-Path -LiteralPath $shortcutPath)) {
        $shortcut = $shell.CreateShortcut($shortcutPath)
        $ownedArgs = @('--daemon','--panel','--test') | ForEach-Object { '"' + (Join-Path $InstallDir 'alerts.py') + '" ' + $_ }
        if ($ownedArgs -contains $shortcut.Arguments) { Remove-Item -LiteralPath $shortcutPath }
    }
}
Write-Output 'Disabled: own hooks and recorded shortcuts removed. Other hooks, app files, backups and history retained.'
Write-Output 'Reload VS Code to unload cached hooks. You can manually remove the install folder afterward.'

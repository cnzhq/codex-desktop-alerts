[CmdletBinding()]
param(
    [string]$PythonExe,
    [string]$InstallDir = (Join-Path $env:LOCALAPPDATA 'CodexDesktopAlerts'),
    [string]$CodexHome = $(if ($env:CODEX_HOME) { $env:CODEX_HOME } else { Join-Path $env:USERPROFILE '.codex' }),
    [switch]$Preview,
    [switch]$NoAutoStart,
    [switch]$NoShortcuts,
    [switch]$NoStart
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
if ([Environment]::OSVersion.Platform -ne 'Win32NT') { throw 'Windows is required.' }
if (-not $PythonExe) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $PythonExe = (& py -3 -c 'import sys; print(sys.executable)').Trim()
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PythonExe = (& python -c 'import sys; print(sys.executable)').Trim()
    } else { throw 'Install Python 3.11+ with Tcl/Tk, then rerun. No Python is downloaded automatically.' }
}
$PythonExe = (Resolve-Path -LiteralPath $PythonExe).Path
& $PythonExe -c 'import sys, tkinter; assert sys.version_info >= (3, 11), "Python 3.11+ required"'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ with tkinter is required.' }
$pythonwExe = Join-Path (Split-Path $PythonExe) 'pythonw.exe'
if (-not (Test-Path -LiteralPath $pythonwExe)) { throw 'pythonw.exe not found beside python.exe.' }
$InstallDir = [IO.Path]::GetFullPath($InstallDir)
$CodexHome = [IO.Path]::GetFullPath($CodexHome)
$manageArgs = @((Join-Path $PSScriptRoot 'manage.py'), 'install', '--install-dir', $InstallDir,
                '--codex-home', $CodexHome, '--python-exe', $PythonExe)
if ($Preview) { $manageArgs += '--preview' }
$result = & $PythonExe @manageArgs
if ($LASTEXITCODE -ne 0) { throw 'Installation failed. Review the error above; no trust settings are bypassed.' }
$result | Write-Output
if ($Preview) {
    Write-Output 'Preview only: no files, shortcuts or processes changed.'
    return
}
$manifestPath = Join-Path $InstallDir 'manifest.json'
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
$shortcutPaths = @($manifest.shortcuts)
$shell = New-Object -ComObject WScript.Shell
$startupPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Codex Desktop Alerts.lnk'
if ($NoAutoStart -or $NoShortcuts) {
    if (Test-Path -LiteralPath $startupPath) {
        $existing = $shell.CreateShortcut($startupPath)
        if ($existing.Arguments -eq ('"' + (Join-Path $InstallDir 'alerts.py') + '" --daemon')) {
            Remove-Item -LiteralPath $startupPath
            $shortcutPaths = @($shortcutPaths | Where-Object { $_ -ne $startupPath })
        }
    }
}
$specs = @()
if (-not $NoShortcuts) {
    $desktop = [Environment]::GetFolderPath('Desktop')
    $specs += @{path=(Join-Path $desktop 'Codex Alerts.lnk'); argument='--panel'}
    $specs += @{path=(Join-Path $desktop 'Test Codex Alerts.lnk'); argument='--test'}
    if (-not $NoAutoStart) { $specs += @{path=$startupPath; argument='--daemon'} }
}
foreach ($spec in $specs) {
    if (Test-Path -LiteralPath $spec.path) {
        $existing = $shell.CreateShortcut($spec.path)
        if ($existing.Arguments -ne ('"' + (Join-Path $InstallDir 'alerts.py') + '" ' + $spec.argument)) {
            throw ('Shortcut already belongs to another target: ' + $spec.path)
        }
    }
    $shortcut = $shell.CreateShortcut($spec.path)
    $shortcut.TargetPath = $pythonwExe
    $shortcut.Arguments = '"' + (Join-Path $InstallDir 'alerts.py') + '" ' + $spec.argument
    $shortcut.WorkingDirectory = $InstallDir
    $shortcut.WindowStyle = 7
    $shortcut.Description = 'Codex Desktop Alerts'
    $shortcut.Save()
    $shortcutPaths += $spec.path
    $manifest.shortcuts = @($shortcutPaths | Sort-Object -Unique)
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [IO.File]::WriteAllText($manifestPath, ($manifest | ConvertTo-Json -Depth 20), $utf8)
}
if (-not $NoStart) {
    Start-Process -FilePath $pythonwExe -ArgumentList @(('"' + (Join-Path $InstallDir 'alerts.py') + '"'), '--daemon') -WindowStyle Hidden
}
Write-Output 'Installed. Review and trust these exact hooks using Codex /hooks, then reload VS Code.'
Write-Output 'Run the desktop Test Codex Alerts shortcut to verify the popup.'

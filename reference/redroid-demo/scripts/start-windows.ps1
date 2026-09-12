param(
    [string]$Distribution = "Ubuntu-24.04",
    [string]$DemoPath = (Split-Path -Parent $PSScriptRoot),
    [ValidateSet("start", "stop", "check")][string]$Action = "start"
)
$ErrorActionPreference = "Stop"
if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    throw "WSL is not installed. Prepare WSL2 Ubuntu 24.04 with its own Docker Engine first."
}
# Each filesystem path is an argument, never interpolated into a shell command.
# Use a Linux path (e.g. /home/user/demo) directly, or translate an existing Windows path.
if ($DemoPath.StartsWith("/")) {
    $LinuxPath = $DemoPath.TrimEnd("/")
} else {
    $Resolved = (Resolve-Path -LiteralPath $DemoPath).Path
    $LinuxPath = (& wsl.exe --distribution $Distribution --exec wslpath -a -u $Resolved)
    if ($LASTEXITCODE -ne 0) { throw "Unable to convert the project path in WSL: $Resolved" }
    $LinuxPath = ($LinuxPath | Out-String).Trim()
}
$ScriptName = @{start="start.sh"; stop="stop.sh"; check="environment.sh"}[$Action]
& wsl.exe --distribution $Distribution --exec bash "${LinuxPath}/scripts/${ScriptName}"
if ($LASTEXITCODE -ne 0) { throw "WSL Demo $Action failed (exit $LASTEXITCODE). See the diagnostic above." }

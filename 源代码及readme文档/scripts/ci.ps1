$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$previousPythonUtf8 = [Environment]::GetEnvironmentVariable("PYTHONUTF8", "Process")
$previousPythonIoEncoding = [Environment]::GetEnvironmentVariable("PYTHONIOENCODING", "Process")
[Environment]::SetEnvironmentVariable("PYTHONUTF8", "1", "Process")
[Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "Process")

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,
        [Parameter(Mandatory = $true)]
        [string[]]$ArgumentList
    )

    & $FilePath @ArgumentList
    if ($LASTEXITCODE -ne 0) {
        throw "命令执行失败（退出码 ${LASTEXITCODE}）：$FilePath $($ArgumentList -join ' ')"
    }
}

$projectDir = Split-Path -Parent $PSScriptRoot
Push-Location -LiteralPath $projectDir
try {
    Invoke-Checked -FilePath "uv" -ArgumentList @("sync", "--locked", "--extra", "dev", "--no-editable")
    Invoke-Checked -FilePath "uv" -ArgumentList @("run", "--no-sync", "ruff", "check", ".")
    Invoke-Checked -FilePath "uv" -ArgumentList @("run", "--no-sync", "pytest", "-q")
    Invoke-Checked -FilePath "uv" -ArgumentList @("run", "--no-sync", "synapse", "smoke")
    Invoke-Checked -FilePath "uv" -ArgumentList @("build")
}
finally {
    Pop-Location
    [Environment]::SetEnvironmentVariable("PYTHONUTF8", $previousPythonUtf8, "Process")
    [Environment]::SetEnvironmentVariable("PYTHONIOENCODING", $previousPythonIoEncoding, "Process")
}

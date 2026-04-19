[CmdletBinding()]
param(
    [string]$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
)

$ErrorActionPreference = "Stop"

function Invoke-CommandArray {
    param(
        [string[]]$Command,
        [string[]]$Arguments
    )

    if ($Command.Length -gt 1) {
        return & $Command[0] $Command[1..($Command.Length - 1)] @Arguments
    }

    return & $Command[0] @Arguments
}

function Resolve-PythonLauncher {
    $candidates = @(
        @{ Name = "py -3.12"; Command = @("py", "-3.12") },
        @{ Name = "py -3.11"; Command = @("py", "-3.11") },
        @{ Name = "python"; Command = @("python") }
    )

    foreach ($candidate in $candidates) {
        try {
            $output = Invoke-CommandArray -Command $candidate.Command -Arguments @("-c", "import sys; print(sys.executable)") 2>$null
            if ($LASTEXITCODE -eq 0 -and $output) {
                return @{
                    Name = $candidate.Name
                    Command = $candidate.Command
                    Executable = $output.Trim()
                }
            }
        } catch {
            continue
        }
    }

    return $null
}

Write-Host "ProjectRoot: $ProjectRoot"
$launcher = Resolve-PythonLauncher
if (-not $launcher) {
    Write-Error @"
Python launcher was not found.
Try one of the following after installing Python 3.11 or later:
  py -3.12 -m venv .venv
  py -3.11 -m venv .venv
  python -m venv .venv
"@
}

Set-Location $ProjectRoot
$venvPath = Join-Path $ProjectRoot ".venv"
if (-not (Test-Path $venvPath)) {
    Write-Host "Creating virtual environment with $($launcher.Name)"
    Invoke-CommandArray -Command $launcher.Command -Arguments @("-m", "venv", $venvPath)
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create virtual environment."
    }
} else {
    Write-Host "Reusing existing virtual environment: $venvPath"
}

$venvPython = Join-Path $venvPath "Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    throw "Virtual environment python not found at $venvPython"
}

Write-Host "Upgrading pip"
& $venvPython -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) {
    throw "pip upgrade failed."
}

Write-Host "Installing project package"
& $venvPython -m pip install -e .
if ($LASTEXITCODE -ne 0) {
    throw "Editable install failed."
}

Write-Host "Installing development requirements"
& $venvPython -m pip install -r requirements-dev.txt
if ($LASTEXITCODE -ne 0) {
    throw "Development dependency install failed."
}

Write-Host "Bootstrap completed."

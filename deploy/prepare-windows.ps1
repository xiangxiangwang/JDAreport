param([string]$Python = "py", [string]$PythonVersion = "3.13")
$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

if ($Python -eq "py") {
    & $Python "-$PythonVersion" -m venv .venv
} else {
    & $Python -m venv .venv
}
if ($LASTEXITCODE -ne 0) { throw "Python 3.12 or 3.13 is required; install it before continuing." }
$venvPython = Join-Path $projectRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw "Dependency installation failed." }

if (-not (Test-Path .env)) { Copy-Item .env.example .env }
New-Item -ItemType Directory -Force -Path instance | Out-Null

# Rebuild private-file ACLs rather than inheriting broad directory access.
# Access is limited to the installing account, SYSTEM and local Administrators.
$currentSid = [System.Security.Principal.WindowsIdentity]::GetCurrent().User
foreach ($path in @((Join-Path $projectRoot ".env"), (Join-Path $projectRoot "instance"))) {
    $isDirectory = (Get-Item $path).PSIsContainer
    if ($isDirectory) {
        $acl = New-Object System.Security.AccessControl.DirectorySecurity
    } else {
        $acl = New-Object System.Security.AccessControl.FileSecurity
    }
    $acl.SetOwner($currentSid)
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in @($currentSid, [System.Security.Principal.SecurityIdentifier]::new("S-1-5-18"), [System.Security.Principal.SecurityIdentifier]::new("S-1-5-32-544"))) {
        if ($isDirectory) {
            $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($sid, "FullControl", "ContainerInherit,ObjectInherit", "None", "Allow")
        } else {
            $rule = [System.Security.AccessControl.FileSystemAccessRule]::new($sid, "FullControl", "Allow")
        }
        $acl.AddAccessRule($rule)
    }
    Set-Acl -Path $path -AclObject $acl
}

& $venvPython -c "import pyodbc; print('Available ODBC drivers:', ', '.join(pyodbc.drivers()))"
if ($LASTEXITCODE -ne 0) { throw "ODBC driver inspection failed." }
Write-Host "Preparation finished. Install Microsoft ODBC Driver 18 if it is not listed."
Write-Host "Next: run deploy/configure.py with database host, database name and read-only username."
Write-Host "Enter the database password at its hidden interactive prompt."
Write-Host "If the service uses another account, grant it read access to .env and write access to instance."

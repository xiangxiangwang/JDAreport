param([Parameter(Mandatory=$true)][string]$SiteAddress, [int]$Port=8088, [int]$BackendPort=8089)
$ErrorActionPreference='Stop'
if ($SiteAddress -notmatch '^[a-zA-Z0-9.-]+$') { throw 'Use an IP address or DNS hostname for SiteAddress.' }
if ($Port -lt 1 -or $Port -gt 65535 -or $BackendPort -lt 1 -or $BackendPort -gt 65535 -or $Port -eq $BackendPort) { throw 'Use two distinct valid ports.' }
$root=Split-Path -Parent $PSScriptRoot
Set-Location $root
if (-not (Test-Path '.venv\Scripts\python.exe') -or -not (Test-Path 'proxy\caddy.exe')) { throw 'Install the Python environment and Caddy first.' }
foreach ($portNumber in @($Port,$BackendPort)) {
    if (Get-NetTCPConnection -LocalPort $portNumber -State Listen -ErrorAction SilentlyContinue) { throw "Port $portNumber is already occupied." }
}
New-Item -ItemType Directory -Force -Path logs,tls | Out-Null

# Task runtime uses the built-in LOCAL SERVICE account; no account password is saved.
& icacls.exe $root /grant '*S-1-5-19:(OI)(CI)(RX)' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not grant runtime directory read access.' }
& icacls.exe "$root\.env" /grant '*S-1-5-19:(R)' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not grant runtime configuration read access.' }
foreach ($directory in @('instance','logs','tls')) {
    # Limit writable folders to the installing user, Administrators, SYSTEM, LOCAL SERVICE.
    $acl=New-Object System.Security.AccessControl.DirectorySecurity
    $userSid=[Security.Principal.WindowsIdentity]::GetCurrent().User
    $acl.SetOwner($userSid)
    $acl.SetAccessRuleProtection($true,$false)
    foreach ($sid in @($userSid,[Security.Principal.SecurityIdentifier]::new('S-1-5-18'),[Security.Principal.SecurityIdentifier]::new('S-1-5-32-544'))) {
        $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new($sid,'FullControl','ContainerInherit,ObjectInherit','None','Allow'))
    }
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-5-19'),'Modify','ContainerInherit,ObjectInherit','None','Allow'))
    Set-Acl -Path (Join-Path $root $directory) -AclObject $acl
}

$storageRoot=(Join-Path $root 'tls').Replace('\','/')
$config=@"
{
    admin off
    auto_https disable_redirects
    storage file_system {
        root $storageRoot
    }
}
https://${SiteAddress}:$Port {
    tls internal
    reverse_proxy 127.0.0.1:$BackendPort
}
"@
[IO.File]::WriteAllText((Join-Path $root 'proxy\Caddyfile'),$config,[Text.UTF8Encoding]::new($false))
& "$root\proxy\caddy.exe" validate --config "$root\proxy\Caddyfile"
if ($LASTEXITCODE -ne 0) { throw 'HTTPS proxy configuration is invalid.' }

foreach ($name in @('JDAReport-App','JDAReport-Proxy')) {
    if (Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue) { throw "Task $name already exists; inspect it before updating." }
}
$startup=New-ScheduledTaskTrigger -AtStartup
$repeating=New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 1)
$settings=New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -StartWhenAvailable
$principal=New-ScheduledTaskPrincipal -UserId 'S-1-5-19' -LogonType ServiceAccount -RunLevel Limited
foreach ($entry in @(@('JDAReport-App','run-app.cmd'),@('JDAReport-Proxy','run-proxy.cmd'))) {
    $runner=Join-Path $PSScriptRoot $entry[1]
    $action=New-ScheduledTaskAction -Execute "$env:WINDIR\System32\cmd.exe" -Argument "/d /c `"$runner`"" -WorkingDirectory $root
    Register-ScheduledTask -TaskName $entry[0] -Action $action -Trigger @($startup,$repeating) -Settings $settings -Principal $principal -Description 'JDA reporting website; runs as LOCAL SERVICE.' | Out-Null
}
if (-not (Get-NetFirewallRule -Name 'JDAReport-HTTPS' -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name 'JDAReport-HTTPS' -DisplayName 'JDA Report HTTPS' -Enabled True -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Port -RemoteAddress LocalSubnet | Out-Null
}
Start-ScheduledTask -TaskName 'JDAReport-App'
Start-ScheduledTask -TaskName 'JDAReport-Proxy'
Write-Output "Background tasks started. HTTPS on $Port is allowed from the local subnet; backend $BackendPort must remain on 127.0.0.1."
Write-Output 'Distribute only tls/pki/authorities/local/root.crt through your company trust process; keep all .key files private.'

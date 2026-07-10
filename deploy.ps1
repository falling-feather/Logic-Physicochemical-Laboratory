#Requires -Version 5.1

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$WinSwPath,

    [Parameter(Mandatory = $true)]
    [string]$StaticExecutable,

    [Parameter(Mandatory = $true)]
    [string]$CaddyExecutable,

    [string]$OutputDir = "C:\englab\service-bundle",
    [string]$InstallRoot = $PSScriptRoot,
    [string]$PythonExecutable = "python",
    [string]$DatabaseUrlValue = "%ASTRA_DATABASE_URL%",
    [ValidateSet("NT AUTHORITY\LocalService", "NT AUTHORITY\NetworkService")]
    [string]$ServiceAccount = "NT AUTHORITY\LocalService",
    [ValidateRange(1024, 65535)]
    [int]$StaticPort = 9010,
    [ValidateRange(1024, 65535)]
    [int]$ApiPort = 9011,
    [ValidateRange(1024, 65535)]
    [int]$ProxyPort = 9012
)

$ErrorActionPreference = "Stop"

if ($StaticPort -eq $ApiPort -or $StaticPort -eq $ProxyPort -or $ApiPort -eq $ProxyPort) {
    throw "StaticPort, ApiPort and ProxyPort must be unique."
}

$generator = Join-Path $PSScriptRoot "backend\scripts\windows_service_drill_bundle.py"
if (-not (Test-Path -LiteralPath $generator -PathType Leaf)) {
    throw "Service bundle generator not found: $generator"
}

$pythonCommand = Get-Command $PythonExecutable -ErrorAction Stop

Write-Host "[INFO] Generating the reviewed WinSW/Caddy four-service bundle." -ForegroundColor Cyan
Write-Host "[INFO] This command does not download tools, open firewall ports, install services, or start processes." -ForegroundColor Cyan

$arguments = @(
    $generator,
    "--output-dir", $OutputDir,
    "--winsw-path", $WinSwPath,
    "--static-executable", $StaticExecutable,
    "--python-executable", $pythonCommand.Source,
    "--caddy-executable", $CaddyExecutable,
    "--install-root", $InstallRoot,
    "--database-url-value", $DatabaseUrlValue,
    "--service-account", $ServiceAccount,
    "--static-port", $StaticPort,
    "--api-port", $ApiPort,
    "--proxy-port", $ProxyPort
)

& $pythonCommand.Source @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Service bundle generation failed with exit code $LASTEXITCODE."
}

Write-Host "[OK] Bundle generated. Review hashes, XML, Caddyfile, ACLs, and rollback backup before installation." -ForegroundColor Green
Write-Host "[NEXT] Follow the deployment guide (doc/04); install/start commands are emitted in the JSON report." -ForegroundColor Yellow

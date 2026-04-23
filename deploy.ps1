#Requires -RunAsAdministrator
# ═══════════════════════════════════════════════════
#  工科实验室 · Windows 一键部署脚本
#  用法: 右键 → "以管理员身份运行 PowerShell" → .\deploy.ps1
# ═══════════════════════════════════════════════════
param(
    [int]$Port = 910,
    [string]$InstallDir = "C:\englab",
    [string]$RepoUrl = "https://github.com/falling-feather/Logic-Physicochemical-Laboratory.git",
    [string]$ServiceName = "EngLab"
)

$ErrorActionPreference = "Stop"

function Write-Info  { Write-Host "[INFO]  $args" -ForegroundColor Cyan }
function Write-Ok    { Write-Host "[OK]    $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "[WARN]  $args" -ForegroundColor Yellow }
function Write-Fail  { Write-Host "[FAIL]  $args" -ForegroundColor Red; exit 1 }

Write-Host ""
Write-Host "╔══════════════════════════════════════════╗" -ForegroundColor Blue
Write-Host "║   工科实验室 · Windows 一键部署            ║" -ForegroundColor Blue
Write-Host "║   端口: $Port                              ║" -ForegroundColor Blue
Write-Host "║   目录: $InstallDir                    ║" -ForegroundColor Blue
Write-Host "╚══════════════════════════════════════════╝" -ForegroundColor Blue
Write-Host ""

# ═══════════════════════════════════════
# 1. 检查前置依赖
# ═══════════════════════════════════════
Write-Info "检查前置依赖..."

# Git
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Write-Fail "未找到 git，请先安装: https://git-scm.com/download/win"
}
$gitVer = (git --version) -replace 'git version ', ''
Write-Ok "Git $gitVer"

# CMake
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Fail "未找到 cmake，请先安装: https://cmake.org/download/"
}
$cmakeVer = ((cmake --version | Select-Object -First 1) -split ' ')[-1]
Write-Ok "CMake $cmakeVer"

# C++ 编译器 — 检查 Visual Studio Build Tools 或 MinGW
$hasVS = $false
$hasMingw = $false
$generator = ""

# 检查 Visual Studio
$vsWhere = "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe"
if (Test-Path $vsWhere) {
    $vsPath = & $vsWhere -latest -property installationPath
    if ($vsPath) {
        $hasVS = $true
        $generator = "Visual Studio 17 2022"
        # 也兼容 VS 2019
        $vsVersion = & $vsWhere -latest -property installationVersion
        if ($vsVersion -match "^16\.") {
            $generator = "Visual Studio 16 2019"
        }
        Write-Ok "Visual Studio ($generator)"
    }
}

# 检查 MinGW
if (-not $hasVS) {
    if (Get-Command g++ -ErrorAction SilentlyContinue) {
        $hasMingw = $true
        $generator = "MinGW Makefiles"
        $gppVer = (g++ --version | Select-Object -First 1)
        Write-Ok "MinGW g++ ($gppVer)"
    }
}

if (-not $hasVS -and -not $hasMingw) {
    Write-Fail "未找到 C++ 编译器。请安装以下任一:`n  1. Visual Studio Build Tools: https://visualstudio.microsoft.com/visual-cpp-build-tools/`n  2. MinGW-w64: https://www.mingw-w64.org/"
}

# ═══════════════════════════════════════
# 2. 克隆 / 更新代码
# ═══════════════════════════════════════
Write-Info "获取项目代码..."

if (Test-Path "$InstallDir\.git") {
    Write-Info "检测到已有仓库，执行 git pull..."
    Push-Location $InstallDir
    git pull --ff-only
    Pop-Location
    Write-Ok "代码更新完成"
} else {
    if (Test-Path $InstallDir) {
        $backup = "${InstallDir}.bak.$(Get-Date -Format 'yyyyMMddHHmmss')"
        Write-Warn "目录已存在但非 git 仓库，备份到 $backup"
        Rename-Item $InstallDir $backup
    }
    git clone $RepoUrl $InstallDir
    Write-Ok "代码克隆完成"
}

# ═══════════════════════════════════════
# 3. 编译 C++ 服务器
# ═══════════════════════════════════════
Write-Info "编译 C++ 服务器（首次编译需下载 httplib 依赖，可能需要数分钟）..."

Push-Location "$InstallDir\server"

if ($hasVS) {
    cmake -B build -S . -G $generator -A x64 -DCMAKE_BUILD_TYPE=Release 2>&1 | Select-Object -Last 5
    cmake --build build --config Release 2>&1 | Select-Object -Last 5
    $binary = "$InstallDir\server\build\Release\englab_server.exe"
} else {
    cmake -B build -S . -G $generator -DCMAKE_BUILD_TYPE=Release 2>&1 | Select-Object -Last 5
    cmake --build build --config Release 2>&1 | Select-Object -Last 5
    $binary = "$InstallDir\server\build\englab_server.exe"
}

Pop-Location

if (-not (Test-Path $binary)) {
    Write-Fail "编译失败，未找到 $binary"
}
Write-Ok "编译完成: $binary"

# ═══════════════════════════════════════
# 4. 防火墙放行
# ═══════════════════════════════════════
Write-Info "配置 Windows 防火墙..."

$ruleName = "EngLab Server (Port $Port)"
$existingRule = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existingRule) {
    Remove-NetFirewallRule -DisplayName $ruleName
}
New-NetFirewallRule -DisplayName $ruleName `
    -Direction Inbound -Protocol TCP -LocalPort $Port `
    -Action Allow -Profile Any | Out-Null
Write-Ok "防火墙已放行端口 $Port (TCP 入站)"

# ═══════════════════════════════════════
# 5. 注册 Windows 服务 (使用 NSSM)
# ═══════════════════════════════════════
Write-Info "注册 Windows 服务..."

$nssmDir = "$InstallDir\tools"
$nssmExe = "$nssmDir\nssm.exe"

if (-not (Test-Path $nssmExe)) {
    Write-Info "下载 NSSM (Non-Sucking Service Manager)..."
    $nssmUrl = "https://nssm.cc/release/nssm-2.24.zip"
    $nssmZip = "$env:TEMP\nssm.zip"

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $nssmUrl -OutFile $nssmZip -UseBasicParsing
        Expand-Archive -Path $nssmZip -DestinationPath "$env:TEMP\nssm" -Force
        New-Item -ItemType Directory -Path $nssmDir -Force | Out-Null
        Copy-Item "$env:TEMP\nssm\nssm-2.24\win64\nssm.exe" $nssmExe -Force
        Remove-Item $nssmZip -Force -ErrorAction SilentlyContinue
        Remove-Item "$env:TEMP\nssm" -Recurse -Force -ErrorAction SilentlyContinue
        Write-Ok "NSSM 下载完成"
    } catch {
        Write-Warn "NSSM 自动下载失败，尝试备用方案（sc.exe 直接注册）..."
        $nssmExe = $null
    }
}

# 停止并删除旧服务
$svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($svc) {
    Write-Info "停止旧服务..."
    Stop-Service -Name $ServiceName -Force -ErrorAction SilentlyContinue
    if ($nssmExe) {
        & $nssmExe remove $ServiceName confirm 2>&1 | Out-Null
    } else {
        sc.exe delete $ServiceName 2>&1 | Out-Null
    }
    Start-Sleep -Seconds 2
}

if ($nssmExe) {
    # 使用 NSSM 注册（支持自动重启、日志输出）
    & $nssmExe install $ServiceName $binary "-p $Port -r $InstallDir"
    & $nssmExe set $ServiceName AppDirectory $InstallDir
    & $nssmExe set $ServiceName Description "EngLab Interactive Science Platform (Port $Port)"
    & $nssmExe set $ServiceName Start SERVICE_AUTO_START
    & $nssmExe set $ServiceName AppStdout "$InstallDir\logs\stdout.log"
    & $nssmExe set $ServiceName AppStderr "$InstallDir\logs\stderr.log"
    & $nssmExe set $ServiceName AppRotateFiles 1
    & $nssmExe set $ServiceName AppRotateBytes 5242880
    New-Item -ItemType Directory -Path "$InstallDir\logs" -Force | Out-Null
    Write-Ok "NSSM 服务注册完成"
} else {
    # 备用方案：使用 sc.exe（不支持自动重启日志）
    $binArgs = "-p $Port -r $InstallDir"
    sc.exe create $ServiceName binPath= "`"$binary`" $binArgs" start= auto | Out-Null
    sc.exe description $ServiceName "EngLab Interactive Science Platform (Port $Port)" | Out-Null
    Write-Ok "Windows 服务注册完成 (sc.exe)"
}

# ═══════════════════════════════════════
# 6. 启动服务
# ═══════════════════════════════════════
Write-Info "启动服务..."

Start-Service -Name $ServiceName
Start-Sleep -Seconds 3

$svc = Get-Service -Name $ServiceName
if ($svc.Status -eq "Running") {
    Write-Ok "服务启动成功 ($ServiceName)"
} else {
    Write-Fail "服务启动失败 (状态: $($svc.Status))，请检查日志: $InstallDir\logs\"
}

# ═══════════════════════════════════════
# 7. 健康检查
# ═══════════════════════════════════════
Write-Info "执行健康检查..."

try {
    $health = Invoke-RestMethod -Uri "http://localhost:$Port/api/health" -TimeoutSec 5
    if ($health.status -eq "ok") {
        Write-Ok "健康检查通过: $($health | ConvertTo-Json -Compress)"
    } else {
        Write-Warn "返回异常: $($health | ConvertTo-Json -Compress)"
    }
} catch {
    Write-Warn "健康检查未通过（服务可能还在启动中）"
    Write-Warn "稍后手动验证: curl http://localhost:${Port}/api/health"
}

# ═══════════════════════════════════════
# 完成
# ═══════════════════════════════════════
Write-Host ""
Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
Write-Host "║  ✅ 部署完成！                                           ║" -ForegroundColor Green
Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Green
Write-Host "║                                                          ║" -ForegroundColor Green
Write-Host "║  访问地址:  http://<服务器IP>:$Port                         ║" -ForegroundColor Green
Write-Host "║                                                          ║" -ForegroundColor Green
Write-Host "║  常用命令 (管理员 PowerShell):                             ║" -ForegroundColor Green
Write-Host "║    Get-Service $ServiceName                查看状态          ║" -ForegroundColor Green
Write-Host "║    Restart-Service $ServiceName            重启服务          ║" -ForegroundColor Green
Write-Host "║    Stop-Service $ServiceName               停止服务          ║" -ForegroundColor Green
Write-Host "║    Get-Content $InstallDir\logs\stdout.log -Tail 50   ║" -ForegroundColor Green
Write-Host "║                                                          ║" -ForegroundColor Green
Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
Write-Host ""

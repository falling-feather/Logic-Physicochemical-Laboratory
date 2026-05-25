# 工科实验室 · Windows 云服务器部署文档

## 一、环境要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / Windows Server 2016+ |
| 软件依赖 | **Git**、**CMake ≥ 3.14**、**Visual Studio Build Tools**（或 MinGW-w64） |
| 网络 | 公网 IP，开放 **910** 端口（TCP 入站） |
| 磁盘空间 | ≥ 500 MB（源码 + VS 编译产物 + 依赖） |

### 依赖下载地址

| 软件 | 下载地址 |
|------|---------|
| Git for Windows | https://git-scm.com/download/win |
| CMake | https://cmake.org/download/ （安装时勾选"添加到 PATH"） |
| Visual Studio Build Tools | https://visualstudio.microsoft.com/visual-cpp-build-tools/ （选择"使用 C++ 的桌面开发"工作负载） |

> **验证安装**：打开 PowerShell，分别运行 `git --version`、`cmake --version` 确认可用。

## 二、服务架构

```
用户浏览器  ──▶  云服务器:910  ──▶  englab_server.exe (C++ 原生 HTTP 服务)
                                     ├── 静态文件服务 (index.html / CSS / JS)
                                     └── REST API (/api/health, /api/info)
```

- 单进程 `.exe`，无外部运行时依赖
- 通过 NSSM 注册为 Windows 服务，支持开机自启 + 崩溃自动重启
- 日志输出到 `C:\englab\logs\`

## 三、一键部署（推荐）

### 步骤

1. 安装好上述依赖软件（Git、CMake、VS Build Tools）
2. **以管理员身份**打开 PowerShell
3. 如果首次运行脚本，先放行执行策略：
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
   ```
4. 执行部署脚本：
   ```powershell
   # 方式 A：先克隆再运行
   git clone https://github.com/falling-feather/Logic-Physicochemical-Laboratory.git C:\englab
   cd C:\englab
   .\deploy.ps1

   # 方式 B：自定义参数
   .\deploy.ps1 -Port 910 -InstallDir "D:\englab"
   ```

脚本自动完成：检查依赖 → 克隆/更新代码 → 编译 → 防火墙放行 → 下载 NSSM → 注册 Windows 服务 → 启动 → 健康检查。

## 四、手动部署步骤

### 4.1 克隆项目

```powershell
git clone https://github.com/falling-feather/Logic-Physicochemical-Laboratory.git C:\englab
```

### 4.2 编译服务器

**以管理员 PowerShell 或"Developer Command Prompt for VS"执行：**

```powershell
cd C:\englab\server

# Visual Studio (自动检测版本)
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release

# 编译产物
# VS: C:\englab\server\build\Release\englab_server.exe
# MinGW: C:\englab\server\build\englab_server.exe
```

### 4.3 测试运行

```powershell
cd C:\englab
.\server\build\Release\englab_server.exe -p 910 -r C:\englab
# 浏览器访问 http://localhost:910 确认正常
# Ctrl+C 停止
```

### 4.4 防火墙放行

```powershell
New-NetFirewallRule -DisplayName "EngLab Server (Port 910)" `
    -Direction Inbound -Protocol TCP -LocalPort 910 `
    -Action Allow -Profile Any
```

### 4.5 注册 Windows 服务

推荐使用 [NSSM](https://nssm.cc/)（Non-Sucking Service Manager）：

```powershell
# 下载 NSSM
Invoke-WebRequest -Uri "https://nssm.cc/release/nssm-2.24.zip" -OutFile nssm.zip
Expand-Archive nssm.zip -DestinationPath C:\englab\tools
Copy-Item C:\englab\tools\nssm-2.24\win64\nssm.exe C:\englab\tools\nssm.exe

# 注册服务
C:\englab\tools\nssm.exe install EngLab "C:\englab\server\build\Release\englab_server.exe" "-p 910 -r C:\englab"
C:\englab\tools\nssm.exe set EngLab AppDirectory C:\englab
C:\englab\tools\nssm.exe set EngLab Description "EngLab Interactive Science Platform"
C:\englab\tools\nssm.exe set EngLab Start SERVICE_AUTO_START
C:\englab\tools\nssm.exe set EngLab AppStdout C:\englab\logs\stdout.log
C:\englab\tools\nssm.exe set EngLab AppStderr C:\englab\logs\stderr.log
New-Item -ItemType Directory -Path C:\englab\logs -Force

# 启动
Start-Service EngLab
```

## 五、运维命令

以管理员 PowerShell 执行：

| 操作 | 命令 |
|------|------|
| 查看状态 | `Get-Service EngLab` |
| 启动服务 | `Start-Service EngLab` |
| 停止服务 | `Stop-Service EngLab` |
| 重启服务 | `Restart-Service EngLab` |
| 查看日志 | `Get-Content C:\englab\logs\stdout.log -Tail 50` |
| 查看错误日志 | `Get-Content C:\englab\logs\stderr.log -Tail 50` |
| 健康检查 | `Invoke-RestMethod http://localhost:910/api/health` |
| 卸载服务 | `C:\englab\tools\nssm.exe remove EngLab confirm` |

### 更新部署

```powershell
cd C:\englab
Stop-Service EngLab
git pull
cd server
cmake --build build --config Release
Start-Service EngLab
```

## 六、云服务器安全组

除了 Windows 防火墙，还需在云厂商控制台（阿里云/腾讯云/华为云等）的**安全组**中放行：

| 方向 | 协议 | 端口 | 来源 |
|------|------|------|------|
| 入站 | TCP | 910 | 0.0.0.0/0 |

> ⚠️ 这一步很容易遗漏，如果 Windows 防火墙已放行但外网仍无法访问，请检查安全组设置。

## 七、故障排查

| 症状 | 排查方法 |
|------|---------|
| 外网无法访问 | ① 检查安全组是否放行 910 ② `Test-NetConnection localhost -Port 910` ③ `netstat -ano \| findstr 910` |
| 服务启动失败 | 查看 `C:\englab\logs\stderr.log`；尝试手动运行 `.\englab_server.exe -p 910 -r C:\englab` 观察报错 |
| 编译失败 (cmake) | 确认已安装 VS Build Tools 的 "C++ 桌面开发" 工作负载；确认 cmake 在 PATH |
| 页面白屏 | `Invoke-RestMethod http://localhost:910/` 检查是否返回 HTML，确认 `-r` 路径正确 |
| 端口被占用 | `netstat -ano \| findstr :910` 找到 PID 后 `taskkill /PID <PID> /F` |

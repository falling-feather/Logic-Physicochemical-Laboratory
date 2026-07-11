# 工科实验室 · C++ 静态服务器

> v6.5 起，新增业务后端位于 `../backend/`。本目录只保留 C++ 静态托管与内部存活探针，不承载用户、课程、作业、学习事件或求值等业务能力。V6.6.59 起不再挂载仓库根目录，只公开 `index.html`、`sw.js`、`pages/`、`shared/`、`UI/`、`codevis/`；V6.6.60 删除旧 `/api/info` 与占位 `/api/eval`，避免反向代理误配时形成第二套业务 API。

## 构建要求
- CMake ≥ 3.14
- C++17 filesystem 完整实现（MSVC 2019+、GCC 9.1+ 或等效 Clang；CMake 会拒绝旧 GCC）

## 构建步骤

```bash
cd server
cmake -B build -S . -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release --target verify_build_manifest
```

首次配置会从官方仓库获取 cpp-httplib，但依赖不再跟随可移动 tag：CMake 固定并复核 v0.18.3 对应提交 `a7bc00e3307fecdb4d67545e93be7b88cfb1e186`。构建结束会在可执行文件旁生成 `englab_server.build-manifest.json`，记录产物大小/SHA-256、CMake/编译器/配置和依赖仓库/版本/commit；`verify_build_manifest` 会重新计算并拒绝清单漂移。

已有通过 commit 复核的 FetchContent checkout 时，可在断网或受控发布机显式复用：

```bash
cmake -B build-offline -S . -DCMAKE_BUILD_TYPE=Release \
  -DASTRA_DEPENDENCIES_OFFLINE=ON \
  -DFETCHCONTENT_SOURCE_DIR_HTTPLIB=/absolute/path/to/verified/httplib-src
cmake --build build-offline --config Release --target verify_build_manifest
```

离线模式缺少显式 source、source 不完整或 `git rev-parse HEAD` 与锁定 commit 不同都会在配置阶段失败。依赖升级必须独立审查：先核对官方 tag 的 commit，再同步 `CMakeLists.txt` 中版本/commit、在线与断网构建证据、公开面 smoke 和发布历史。当前 manifest 保证每个产物可追踪，不承诺不同目录/工具链的二进制逐字节相同。

## 运行

```bash
# 默认端口 9527、监听 127.0.0.1，根目录参数只用于定位显式公开资源
./build/Release/englab_server

# 自定义参数
./build/Release/englab_server -p 8080 -r ../

# 只有反向代理/防火墙方案已确认时才扩大监听
./build/Release/englab_server --host 0.0.0.0 -p 8080 -r ../
```

## API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/health` | GET | 仅供本机/服务守护探测 C++ 静态进程；公网 `/api/*` 必须由反向代理转发到 FastAPI |

## 依赖
- [cpp-httplib](https://github.com/yhirose/cpp-httplib) v0.18.3，固定 commit `a7bc00e3307fecdb4d67545e93be7b88cfb1e186`（CMake FetchContent 获取并复核）

# 工科实验室 · C++ 静态服务器

> v6.5 起，新增业务后端位于 `../backend/`。本目录只保留 C++ 静态托管与内部存活探针，不承载用户、课程、作业、学习事件或求值等业务能力。V6.6.59 起不再挂载仓库根目录，只公开 `index.html`、`sw.js`、`pages/`、`shared/`、`UI/`、`codevis/`；V6.6.60 删除旧 `/api/info` 与占位 `/api/eval`，避免反向代理误配时形成第二套业务 API。

## 构建要求
- CMake ≥ 3.14
- C++17 filesystem 完整实现（MSVC 2019+、GCC 9.1+ 或等效 Clang；CMake 会拒绝旧 GCC）

## 构建步骤

```bash
cd server
cmake -B build -S .
cmake --build build --config Release
```

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
- [cpp-httplib](https://github.com/yhirose/cpp-httplib) v0.18.3 (通过 CMake FetchContent 自动下载)

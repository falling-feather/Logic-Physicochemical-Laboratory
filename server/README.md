# 工科实验室 · C++ 后端服务器

> v6.5 起，新增业务后端位于 `../backend/`。本目录继续保留为 C++ 静态托管与历史 API 服务，不再扩展用户、课程、作业、学习事件等业务能力。

## 构建要求
- CMake ≥ 3.14
- C++17 兼容编译器 (MSVC 2019+, GCC 8+, Clang 8+)

## 构建步骤

```bash
cd server
cmake -B build -S .
cmake --build build --config Release
```

## 运行

```bash
# 默认端口 9527，默认根目录为上级目录(项目根)
./build/Release/englab_server

# 自定义参数
./build/Release/englab_server -p 8080 -r ../
```

## API

| 端点 | 方法 | 描述 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/info` | GET | 服务器信息 |
| `/api/eval` | POST | 数学表达式求值 (待扩展) |

## 依赖
- [cpp-httplib](https://github.com/yhirose/cpp-httplib) v0.18.3 (通过 CMake FetchContent 自动下载)

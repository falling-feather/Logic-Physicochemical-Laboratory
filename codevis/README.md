# 代码空间 · 星序子站

「代码空间」（CodeSpace，目录代号 `codevis/`）是「星序 Astra」平台下属的代码可视化子站，聚焦「把代码执行过程变成可看得见的画面」。
与「工科实验室」同仓部署，通过 `/codevis/` 访问。

## 主色与品牌
- 深太空蓝 `#0a1929` + 震荡青 `#00d4ff`（赛博朋克风）
- 字体：Inter（界面）+ JetBrains Mono（代码）

## 目录结构
```
codevis/
├── index.html              ← 独立 SPA 入口
├── shared/
│   ├── css/   tokens · base · navbar · layout
│   └── js/    router (hash 路由) · main (启动)
└── pages/
    ├── home/        粒子网络背景 + 特性卡片
    └── code-trace/  代码执行追踪播放器
```

## 路由
- `#home`  · 首页
- `#trace` · 代码执行追踪

## 当前阶段
- **Phase 1（已上线）**：站点骨架 + 迁移 code-trace（预设 trace 演示）
- **Phase 2（已上线）**：Runtime 抽象 + 多语言手写沙箱
  - JavaScript：[JS-Interpreter](https://github.com/NeilFraser/JS-Interpreter)（acorn + interpreter）
  - Python：[Skulpt](https://skulpt.org/)（纯 JS Python 3 子集）
  - C / C++：[JSCPP](https://github.com/felixhao28/JSCPP) v2.0.9（纯 JS C++ 子集，不支持 namespace/class）
- **Phase 3（规划）**：数据结构画布（链表 / 树 / 图节点动画）

## 沙箱 API 速查
所有后端共享相同的"标记函数"协议，由 runtime 拦截后驱动可视化：

| 函数 | JS / Python | C / C++ |
|---|---|---|
| 移动指针/高亮 | `markPtr(i, j, j2, arr?)` | `markPtr(int i, int j, int j2)` / `markPtr2(int i, int j)` |
| 标记交换 | `markSwap(arr?)` | `markSwap()` |
| 覆盖数组面板 | `markArray(arr)` | `markArray(int* a, int n)` |
| 写入快照 | `snap(name, value)` | `snapInt(const char* name, int v)` |
| 标准输出 | `print(...)` / `console.log` | `printf` / `cout`（C++） |

> **C/C++ 注意事项**：JSCPP 不支持 `std::xxx` 命名空间限定符，请用 `using namespace std;` 或直接调用 `<cstdio>` 函数。

## 本地预览
```powershell
# 与工科实验室共用同一开发服务器
python -m http.server 8080
# 浏览器访问
# http://localhost:8080/codevis/
```

## 开发约定
- 命名空间统一前缀：`cv-` (CSS class) / `Cv*` (全局对象，如 `CvRouter`/`CvHome`)
- 仅 `CodeTrace` 沿用原命名以便迁移
- 全部 JS 使用 IIFE 暴露至 `window`，无构建步骤
- 严格支持 `prefers-reduced-motion: reduce` 降级

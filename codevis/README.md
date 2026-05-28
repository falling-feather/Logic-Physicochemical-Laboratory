# 代码空间 · 「星序 Astra」子站

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

## 📝 更新日志（子站视角）

> 仅记录与代码空间子站直接相关的变更；平台级更新见 [主站 README](../README.md#-更新日志)。

### v6.1.0-alpha（迭代中 · `feature/v6.1`）
- **alpha2** — 2026-05-26 — 优化代码空间子站交互与更新规划口径
- **alpha1** — 2026-05-26 — 修复 CodeSpace 跳转与文档口径偏差（主站 → 子站入口校准）

### v6.0.0 — 2026-05-25 / 2026-05-26
- 🪐 与「工科实验室星系」并列为「星序 Astra」下属两大子站之一
- 📚 子站定位写入开发者手册多星系开发指南（§17）

### v5.1.3 — 2026-05-24
- 🎛️ Code-trace 交互打磨：复制 / 重置按钮、关键步骤时间轴、左右面板可折叠

### v5.1.2 — 2026-05-24
- ✨ 子站交互整体优化：文案对齐、控件分区、键盘快捷键、首访引导、卡片光晕

### v5.1.0 — 2026-05-24（子站首发独立化）
- 💻 **Codevis 从主站抽离为独立 SPA** `/codevis/`，拥有独立 `index.html` + 命名空间隔离（`cv-` / `Cv*`）
- 🔧 引入 **Runtime 抽象层**，统一标记函数协议（`markPtr` / `markSwap` / `markArray` / `snap` / `print`）
- 🧪 三沙箱后端落地：
  - JavaScript — JS-Interpreter（acorn + interpreter）
  - Python — Skulpt（Python 3 子集）
  - C / C++ — JSCPP v2.0.9（不支持 namespace/class）

### v5.0.x — 2026-04-22 ~ 2026-05
- 🌌 codevis 作为「代码空间」学科首次在主站星系大屏中落地（彼时仍嵌在主站内）

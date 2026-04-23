# 工科实验室 移动端适配审视报告（v4.1.1 基线）

> **审视日期**: 2026-04-22 | **方法**: 代码扫描（CSS @media + Canvas 触控事件）| **范围**: viewport / 断点 / 触控事件 / Canvas 适配 / 触控设备样式
>
> 本文档是 **只读审视产出**，未对代码做任何修改。

---

## 一、概览

| 维度 | 检查方法 | 结果 |
|------|---------|------|
| viewport meta | grep `viewport` in `index.html` | ✅ `<meta name="viewport" content="width=device-width, initial-scale=1.0">` |
| 响应式断点 | 全局 `@media[^{]+max-width` 扫描 | ✅ 1024 / 768 / 640 / 480 四档 |
| 触控设备样式 | `(hover: none) and (pointer: coarse)` | ✅ 在 `responsive.css` 已实现卡片 `:active`、44px 触摸目标、卫星标签常显等 |
| Canvas 触控事件配套 | `touchstart` / `touchmove` / `touchend` 监听 | ✅ 4 个有拖拽的 Canvas 全部配齐 |
| Canvas DPR 适配 | 各实验 `_resize()` 方法 | ✅ 已普遍采用 `dpr * rect.width` 模式 |

---

## 二、断点体系

### 共享层（`shared/css/responsive.css`）

| 断点 | 触发条件 | 主要变化 |
|------|---------|---------|
| 平板 | `max-width: 1024px` | bento-grid 转 2 列、demo-layout 转单列、footer 单列 |
| 移动 | `max-width: 768px` | 顶 nav 转 icon-only + 44px 触摸目标、page-hero 单列 |
| 小屏 | `max-width: 480px` | 进一步缩小内边距与字号（具体见 responsive.css L214） |

### 学科层（按需细化）

- `pages/biology/biology.css`：6 处 768px、1 处 480px、1 处 600px（`gmut-controls` 等单独翻栏）
- `pages/chemistry/chemistry.css`：3 处 768px + 1 处 480px
- `pages/algorithms/algorithms.css`：6 处 768px（多个 `*-controls` 翻栏）
- `pages/mathematics/mathematics.css`：（已扫描，断点已覆盖）
- `pages/physics/physics.css`：（已扫描，断点已覆盖）

### 工具层

- `module-selector.css`、`experiment-export.css`、`experiment-favorites.css`、`experiment-guide.css`、`experiment-quiz.css`、`experiment-rating.css` 均有 768px / 640px 断点

---

## 三、Canvas 触控事件配套核查

### 真问题扫描结果 — 0 处

| 文件 | mousedown | touchstart | mousemove | touchmove | 是否齐全 |
|------|-----------|-----------|-----------|-----------|---------|
| `pages/physics/electromagnetic.js` | ✅ L391 | ✅ L399 | ✅ L392 | ✅ L400 | ✅ |
| `pages/physics/fluid-dynamics.js` | ✅ L437 | ✅ L444 | ✅ L438 | ✅ L445 | ✅ |
| `pages/physics/physics.js` (父类) | ✅ L147 | ✅ L167 | ✅ L152 | ✅ L173 | ✅ |
| `pages/physics/waves.js` | — (hover 探针无需 down) | ✅ L235 | ✅ L226 | ✅ L231 | ✅ |
| `pages/mathematics/mathematics.js` | ✅ L341 | ✅ (内含) | ✅ L303/347 | ✅ L307 | ✅ |
| `pages/biology/cell-structure.js` | — (无拖拽) | ✅ L95 (单击放大) | ✅ L81 (hover 提示) | — | ⚠️ 微小 |

> **`cell-structure.js` 微小提示**：移动端无 mousemove → hover 高亮失效；用户必须先 tap 一次才放大，无中间状态。现状可接受（W3C 标准触控行为）。

### 其他 57 个实验

经扫描 `canvas\.addEventListener\(['"]mouse(down|move)`，仅出现在上述 6 个文件。其余 57 个实验通过控制面板（按钮/滑块/select）操作，**Canvas 仅作为渲染输出**，不需要 touch 事件配套。

---

## 四、触控设备 CSS 增强

`shared/css/responsive.css` L36-74 已通过 `@media (hover: none) and (pointer: coarse)` 区分触控设备：

| 优化项 | 状态 |
|--------|------|
| 卡片去除 hover transform | ✅ |
| 卡片 `:active` 替代 hover | ✅ |
| 卫星标签常显（无 hover 触发） | ✅ |
| 顶部 nav 44px 触摸目标 | ✅ |
| Back-to-top 按钮 48px | ✅ |

模态框：`physics-zoom-modal__host`、`biology-zoom-modal__host` 均设置 `touch-action: none`，由 JS 接管所有手势 ✅

---

## 五、潜在改进点（非缺陷）

| 项 | 描述 | 优先级 |
|----|------|--------|
| P-01 | 真机测试覆盖度 0（仅 CSS + 代码层确认，未在 iPhone/Android 真机验证手势灵敏度） | 中 |
| P-02 | `cell-structure.js` 移动端无 hover 预览，需先 tap 才放大 | 低 |
| P-03 | 60+ 实验若未来增加 Canvas 内点击交互（如标签选中、图元高亮），需为每个补 touchstart 处理 | 设计提醒 |
| P-04 | 弹窗类组件（quiz / guide / rating）在小屏的滚动行为需手动测试 | 中 |

---

## 六、总体结论

> **该项目移动端适配已基本完善**，无系统性缺陷，无需安排修复 Batch。

亮点：
- 全局/学科/工具三层断点覆盖完整
- Canvas 拖拽实验 100% 触控配套齐全
- 触控设备专属样式分支已实现

后续若启动移动端深度优化，建议优先级：
1. 安排一轮真机回归测试（任务 P-01），结合截图记录定型
2. 评估 `cell-structure.js` 是否需要 long-press 替代 hover 预览（任务 P-02）
3. 制定"未来新增 Canvas 交互必配 touch 事件"的开发规范（任务 P-03）

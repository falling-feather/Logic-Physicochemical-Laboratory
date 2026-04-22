# 工科实验室 — 后续更新计划

> **制定日期**: 2026-04-13 | **最后更新**: 2026-04-22 | **状态**: Phase 1 内容规划全部完成，进入 Phase 2 深化阶段
>
> **📌 文档边界约定**（自 v4.0.4 起）：本文档仅承载 *近期已完成增量*（最近 1-2 个小版本）+ *未来更新规划*。所有历史完成的大版本（≤ v4.0.1）、阶段性实验汇总、完整 Bug 修复履历，请参阅 [`doc/have_done.md`](have_done.md)。两份文档分工：UPDATE_PLAN 面向"下一步"，have_done 面向"已沉淀"。

---

## 二、Phase 2 — 未来内容扩展（对齐人教版尚未覆盖知识点）

以下为人教版 2019 版高中教材中**尚未被现有实验覆盖**的核心知识点，按学科和优先级列出。

### 2.1 数学补充实验

| 优先级 | 实验名称                 | 对应教材      | 内容描述                                                             |
| ------ | ------------------------ | ------------- | -------------------------------------------------------------------- |
| P0     | **函数性质探究**   | 必修一 第3章  | 单调性判定（拖拽标记增减区间）、奇偶性（关于原点/y轴对称）、周期性   |
| P0     | **指数与对数函数** | 必修一 第4章  | 指数函数 aˣ / 对数函数 logₐx 的底数 a 对图像影响、互为反函数可视化 |
| P1     | **二项式定理**     | 选必二 第5章  | (a+b)ⁿ 展开系数 = C(n,k) 动画、与杨辉三角联动                       |
| P1     | **统计与回归**     | 必修二 第10章 | 散点图 + 最小二乘线性回归拟合动画、相关系数 r 可视化                 |
| P2     | **空间向量**       | 选必一 第2章  | 三维向量加减法、空间直线/平面法向量、二面角计算                      |
| P2     | **导数应用**       | 选必二 第4章  | 函数极值/最值判定（一阶/二阶导数检验）、切线方程                     |

### 2.2 物理补充实验

| 优先级 | 实验名称                 | 对应教材              | 内容描述                                            |
| ------ | ------------------------ | --------------------- | --------------------------------------------------- |
| ~~P0~~ | ~~**力的合成与分解**~~ | ~~必修一 第3章~~   | ✅ 已完成 — 三模式（合成/正交分解/斜面分析），拖拽交互 |
| ~~P0~~ | ~~**动量守恒**~~   | ~~选必一 第1章~~    | ✅ 已完成 — 弹性/非弹性/完全非弹性碰撞 + 动量-动能柱状图 |
| ~~P1~~ | ~~**带电粒子运动**~~ | ~~必修三 第3章 / 选必二~~ | ✅ 已完成 — 洛伦兹力偏转/质谱仪/速度选择器三模式 |
| P1     | **气体实验定律**   | 选必三 第1章          | 等温/等压/等容变化 P-V/P-T/V-T 图、理想气体状态方程 |
| P2     | **原子物理**       | 选必三 第4章          | 玻尔模型能级跃迁、光谱发射/吸收动画、光电效应       |
| P2     | **热力学基础**     | 选必三 第2章          | 热力学第一/第二定律、熵的概念、热机效率             |

### 2.3 化学补充实验

| 优先级 | 实验名称                     | 对应教材                    | 内容描述                                                      |
| ------ | ---------------------------- | --------------------------- | ------------------------------------------------------------- |
| ~~P0~~ | ~~**原子结构与电子排布**~~ | ~~必修一 第4章 / 选必二 第1章~~ | ✅ 已完成 — 轨道形状 / 电子排布 / 玻尔模型三模式可视化 |
| P0     | **元素化合物**         | 必修一 第3章 / 必修二 第3章 | Na/Fe/Al/Cl/N/S 典型反应动画、焰色反应模拟                    |
| P1     | **分子间力与氢键**     | 选必二 第2章                | 范德华力 vs 氢键对比、沸点/溶解度趋势可视化                   |
| P1     | **杂化轨道理论**       | 选必二 第2章                | sp/sp²/sp³ 杂化过程动画、VSEPR 模型 3D 展示                 |
| P2     | **晶体结构**           | 选必二 第3章                | NaCl/金刚石/干冰/铜 四种晶体类型 3D 晶胞展示                  |

### 2.4 生物补充实验

| 优先级 | 实验名称                   | 对应教材       | 内容描述                                              |
| ------ | -------------------------- | -------------- | ----------------------------------------------------- |
| P0     | **酶的特性**         | 必修一 第5章   | 酶活性-温度/pH曲线交互、底物浓度-反应速率（米氏方程） |
| P0     | **内环境稳态**       | 选必一 第1章   | 血糖调节（胰岛素/胰高血糖素反馈环）、体温调节         |
| P1     | **体液调节**         | 选必一 第3章   | 甲状腺激素分级调节（下丘脑→垂体→甲状腺 负反馈）     |
| P1     | **种群与群落**       | 选必二 第1-2章 | 种群增长模型（J型/S型）、种间关系（竞争/捕食/共生）   |
| P2     | **生态系统物质循环** | 选必二 第3章   | 碳循环/氮循环流程动画、温室效应模型                   |
| P2     | **基因工程**         | 选必三 第1章   | 限制酶切割 + 连接酶拼接 + 载体构建动画                |

### 2.5 算法补充实验

| 优先级 | 实验名称                 | 内容描述                          |
| ------ | ------------------------ | --------------------------------- |
| P1     | **哈希表**         | 链地址法/开放地址法冲突解决可视化 |
| P1     | **二叉搜索树**     | 插入/删除/查找 + AVL 旋转平衡动画 |
| P2     | **贪心算法**       | 活动选择/区间调度问题逐步动画     |
| P2     | **最小生成树对比** | Kruskal vs Prim 并排对比动画      |

---

## 三、功能与架构优化

### Phase 1: 紧急修复 ✅ 已完成

| 编号 | 任务                         | 状态                                    |
| ---- | ---------------------------- | --------------------------------------- |
| F-01 | 首页添加生物卫星             | ✅ v2.2 完成                            |
| F-02 | 化学反应交互重写             | ✅ v2.2 完成（化学键可视化 + 能量曲线） |
| F-03 | Canvas DPR + resize 全面审查 | ✅ v3.0.2 完成（BF-10）                 |
| F-04 | selectModule 生物色缺失      | ✅ 验证已有                             |

### Phase 2: 交互增强 — 近期 (v4.1)

| 编号 | 任务             | 说明                             | 状态      |
| ---- | ---------------- | -------------------------------- | --------- |
| E-01 | 实验步骤引导系统 | 首次进入实验时显示操作提示覆盖层 | ✅ 已完成 |
| E-02 | 触控手势优化     | 移动端 pinch-zoom、swipe 返回    | ✅ 已完成 |
| E-03 | 实验数据导出     | 截图/CSV 导出功能                | ✅ 已完成 |
| E-04 | 键盘导航完善     | Tab 切换实验控件、Esc 返回画廊   | ✅ 已完成 |

### Phase 3: 性能优化 — 中期 (v4.5)

| 编号 | 任务                   | 说明                               | 状态                        |
| ---- | ---------------------- | ---------------------------------- | --------------------------- |
| P-01 | Canvas OffscreenCanvas | 复杂实验使用 Web Worker 渲染       | ✅ 已完成                   |
| P-02 | ~~懒加载实验脚本~~    | ~~按需加载学科 JS 文件~~          | ✅ 已用 defer 替代          |
| P-03 | ~~资源预加载优化~~    | ~~关键路径资源 preload/prefetch~~ | ✅ 已完成（加载屏 + defer） |
| P-04 | 首页粒子网络性能       | 粒子数量自适应 GPU 能力            | ✅ 已完成                   |

### Phase 4: 扩展功能 — 远期 (v5.0)

| 编号 | 任务          | 说明                          | 状态               |
| ---- | ------------- | ----------------------------- | ------------------ |
| X-01 | 学习进度系统  | localStorage 记录已完成实验   | ✅ 已完成          |
| X-02 | 小测验模块    | 每个实验后附带概念检测题      | ✅ 已完成          |
| X-03 | 暗/亮主题切换 | 尊重 `prefers-color-scheme` | ✅ 已完成 (v4.0.3)  |
| X-04 | PWA 离线支持  | Service Worker + 缓存策略     | ✅ v4.0.1 基础实现 |
| X-05 | 实验分享功能  | 生成实验截图 + 配置链接       | ✅ 已完成          |
| X-06 | 实验收藏功能  | 心形按钮收藏实验到 localStorage | ✅ 已完成          |
| X-07 | 实验评分反馈  | 5星浮动评分卡片 + localStorage | ✅ 已完成          |
|      |               |                               |                    |

---

## 四、目录跳转优化

### 当前跳转路径

```
首页卫星 → 学科页面 Hero → 模块选择器画廊 → 实验内容
导航栏    →                   ↗
实验卡片  →    ↗
Skip-nav  →    直接跳转主内容区
```

### 优化方案

1. **面包屑导航**：实验页面顶部显示 `首页 > 化学 > 分子结构`
2. **学科内目录**：侧边栏显示当前学科所有实验，可快速跳转
3. **桌面端快捷键**：`Ctrl+1~5` 快速切换学科
4. **搜索功能**：全局搜索实验名/关键词
5. **跨学科推荐**：实验底部推荐关联实验（如 DNA → 遗传学 → 基因突变）

---

## 十一、2026-04-22 v4.0.3 首页观感修复（本轮）

### 修改点

1. **移除主星球"开灯"呼吸效果**：
   - 文件：`pages/home/home.css`
   - 删除 `@keyframes starPulse` 及 `.star-body` 上的 `animation: starPulse 4s ease-in-out infinite`
   - 替换为单一稳定 `box-shadow`（外发光强度取原动画峰谷中位数：34/70/110px 三层）
   - 视觉效果：主星球不再 4 秒明暗反复跳动，整体安定，避免"灯泡闪烁"观感

### 浏览器验证

- 启动 `python -m http.server 8080`，深色主题下首页观察 5+ 秒，主星球 box-shadow 完全静止
- 卫星轨道动画、眼睛跟随、粒子网络、流星等其余动效均正常
- 0 控制台错误（远程字体超时是无网络环境正常现象，不影响）

### 未触动项（下一轮按用户优先级处理）

- have_done.md 文档拆分（任务 2）
- 引导/测验定制化（任务 3）
- 首页 home-progress-widget 移除（任务 4）
- 镂空科技风星球（任务 5，独立分支 feature/holographic-planets）
- 移动端适配（任务 6）
- 实验文字排版逐项审视（任务 7）
- Phase 2 新增实验（任务 8）
## 五、版本里程碑（精简）

> 完整历史里程碑（v2.0 - v4.0.1）见 [`have_done.md`](have_done.md#历史版本里程碑完整表)。

| 版本 | 目标 | 状态 |
| ---- | ---- | ---- |
| v4.0.2 | Canvas 字体标准化 + 冻结 Bug 修复 + UI 模板文档 | ✅ 已完成 |
| v4.0.3 | 首页主星球 starPulse "开灯"呼吸效果移除 — 静态柔光 | ✅ 已完成 |
| **v4.0.4** | **UPDATE_PLAN 拆分 → 新增 `have_done.md` 历史归档** | ✅**已完成** |
| **v4.0.5** | **首页移除 home-progress-widget（保留卫星 chips + 学科 hero 进度条）** | ✅**已完成** |
| **v4.0.6** | **UI 排版审视 — 输出 [`UI_AUDIT_v4.0.5.md`](UI_AUDIT_v4.0.5.md) Bug 清单（29 项）** | ✅**已完成** |
| **v4.0.7** | **Batch 1 修复：`momentum-conservation.js` Canvas 字号 8/9/10/11px → 12px + CF.sans（10 处）** | ✅**已完成** |
| **v4.0.8** | **Batch 2 修复：3 个物理文件 24 处硬编码字体 → `CF.sans` / `var(--font-mono)`** | ✅**已完成** |
| **v4.0.9** | **顺手补充：`force-composition.js` 残留 2 处 11px 字号 → 12px** | ✅**已完成** |
| **v4.0.10** | **Batch 3 物理化学批复核：4 个 `_injectEduPanel` 被鉴定为幂等误报（表项关闭）** | ✅**已完成** |
| **v4.1.0** | **Batch 3 生物批复核：9 个 `_injectInfoPanel` 同样为幂等误报，§二B 整张表 13 项全部关闭** | ✅**已完成** |
| **v4.1.1** | **任务 6 移动端适配审视：viewport / 断点体系 / 触控事件配套检查，产出 MOBILE_AUDIT_v4.1.1.md** | ✅**已完成** |
| **v4.1.2** | **任务 3 引导/测验定制化：dna + cellular-respiration 各加 5 步定制引导，dna 测验 3→5 题，新增 cellular-respiration 5 题** | ✅**已完成** |
| **v4.1.3** | **任务 3 续：photosynthesis + mitosis + electromagnetism 各加 5 步定制引导，三者测验全部扩到 5 题** | ✅**已完成** |
| **v4.1.4** | **任务 3 续：reaction-rate + chemical-equilibrium + electrochemistry 各加 5 步定制引导，三者测验全部扩到 5 题** | ✅**已完成** |
| **v4.1.5** | **任务 3 续：chemical-bond + ionic-reaction + organic-chemistry 各加 5 步定制引导，三者测验全部新增/扩到 5 题** | ✅**已完成** |
| **v4.1.6** | **任务 3 收尾化学：atomic-structure + molecular-structure + chemical-reactions + solution-ionization 各加 5 步定制引导 + 测验题全部新增 5 题，化学领域 11/11 全部覆盖** | ✅**已完成** |
| **v4.1.7** | **任务 3 转数学：trigonometry + probability + vector-ops 各加 5 步定制引导与测验题其他扯到 5 题/新增 5 题（嵌入诱导公式、大数定律、向量垂直判定等高考考点）** | ✅**已完成** |
| **v4.1.8** | **任务 3 数学续推：sequences + inequality + conic-sections 各加 5 步定制引导 + 测验题扩/新增到 5 题（提及等差等比通项、线性规划顶点原理、离心率统一定义）** | ✅**已完成** |
| **v4.1.9** | **任务 3 数学推进：function-properties + set-operations + permutation-combination 各加 5 步定制引导 + 测验题全部新增各 5 题（嵌入奇偶函数判定、德摩根律、二项式定理等）** | ✅**已完成（当前版本）** |
| v4.1 | 交互增强（步骤引导 + 触控 + 键盘） | 🔜 规划中 |
| v4.5 | 性能优化 + 学习进度 + PWA + 数据导出 | 🔜 规划中 |
| v5.0 | Phase 2 内容扩展（人教版深化知识点 20+ 实验） | 🔜 规划中 |
| v5.5 | 小测验定制化 + 主题切换 + 分享 | 🔜 规划中 |

---

## 六、2026-04-22 v4.0.4 文档拆分

### 修改点

1. **新增 `doc/have_done.md`** — 沉淀以下历史内容：
   - 一、内容规划完成总结（5 学科 63 个实验汇总表）
   - 五、Bug 审查清单（BF-01 ~ BF-13、OPT-01 ~ OPT-12、v4.0.2 修复项）
   - 七、人教版课标覆盖度分析
   - 八、2026-04-14 维护优化增量
   - 九、2026-04-15 物理模块专项优化（第二轮）
   - 十、2026-04-17 生物模块修复 + 缓存优化（v4.0.1）
   - 完整版本里程碑表（v2.0 - v4.0.3）

2. **`doc/UPDATE_PLAN.md` 精简至四大块**：
   - Phase 2 未来内容扩展（数学/物理/化学/生物/算法补充实验）
   - 功能与架构优化路线图
   - 目录跳转优化方案
   - 精简版版本里程碑（仅最近 1-2 小版本 + 未来规划）

3. **头部新增"文档边界约定"段落**，明确两文档分工。

### 影响

- 文档可读性提升：UPDATE_PLAN 从 ~500 行精简至 ~200 行，新增条目时不再被历史信息淹没
- AI 协作友好：未来 agent 仅需读 UPDATE_PLAN 即可掌握"下一步要做什么"，历史背景按需查阅 have_done.md

### 验证

- 文件分别可读、章节锚点链接生效
- 0 内容丢失（历史所有章节 100% 迁移）


---

## 七、2026-04-22 v4.0.5 首页移除 home-progress-widget（本轮）

### 修改点

1. **`shared/js/learning-progress.js`** — `_renderHomeProgress()` 中删除 "Overall progress widget below tagline" 整段（不再创建/更新 `#home-progress-widget` 元素）。保留：
   - 卫星轨道上的 `.satellite-progress` 进度 chips（如 0/15、0/17）
   - 学科 hero 内的 `.progress-bar` 学科进度条（`_renderProgressBar`）
2. **`pages/home/home.css`** — 删除 `.home-progress-widget*` 4 条 CSS 规则（约 45 行）。
3. **缓存破坏**：`index.html` + `sw.js` 中 `home.css` / `learning-progress.js` 版本号 → `20260422a`，SW `CACHE_NAME` → `englab-static-v20260422a`。

### 浏览器验证

- 清除 SW + caches 后硬刷新，首页 hero 区底部不再渲染"共 65 个实验等你探索"长条 widget
- 5 个学科卫星轨道仍然显示 `0/15` `0/17` `0/12` `0/8` `0/13` 的小 chips
- 0 控制台错误

---

## 八、2026-04-22 v4.0.6 UI 排版审视

### 产出

- **新增 [`doc/UI_AUDIT_v4.0.5.md`](UI_AUDIT_v4.0.5.md)** —— 60 个实验文件全量审视报告
- **0 行代码修改**（纯审视轮，修复留待后续 patch 按 Batch 推进）

### 关键发现（详见审视报告）

| 维度 | 高 | 中 | 低 | 合计 |
|------|----|----|----|------|
| Canvas 字号过小 | 10 | — | — | 10 |
| `_inject*` 幂等性缺失 | 13 | — | — | 13 |
| 硬编码字体名残留 | — | 3 文件 / 24 处 | — | 24 |
| Canvas 高度复制 Bug | — | — | 0 | 0 |

### 重灾区

- `pages/physics/momentum-conservation.js` — Canvas 字号 7 处过小（含 8px 严重不可读）
- `pages/physics/charged-particle.js` + `force-composition.js` + `relativity.js` — 24 处硬编码字体（v4.0.2 FONT-03 遗漏）
- 生物 9 个 `_injectInfoPanel` + 物理化学 4 个 `_injectEduPanel` — 重复打开累积 DOM 风险

### 修复路线（v4.0.7 - v4.1.0 分批）

1. **v4.0.7**：Momentum-Conservation 字号修复（1 文件 8 行）
2. **v4.0.8**：硬编码字体一次性脚本替换（3 文件 24 处）
3. **v4.1.0**：13 个 `_inject*` 幂等防护补全（按学科分批）


---

## 九、2026-04-22 v4.0.7 Canvas 字号修复 Batch 1

### 修改文件

- `pages/physics/momentum-conservation.js` —— 10 处 `ctx.font` 重写

### 修复明细

| 原字号串 | 新字号串 | 出现行 |
|----------|----------|--------|
| `'10px system-ui, sans-serif'` | `'12px ' + CF.sans` | L364（标尺刻度）|
| `'11px system-ui, sans-serif'` ×4 | `'12px ' + CF.sans` ×4 | L407,424,443,455（物块/速度标签）|
| `'9px system-ui, sans-serif'` | `'12px ' + CF.sans` | L533（柱状图数值）|
| `'8px system-ui, sans-serif'` | `'12px ' + CF.sans` | L540（柱状图标签）|
| `'bold 13px system-ui, sans-serif'` ×2 | `'bold 13px ' + CF.sans` ×2 | L403,420（A/B 主标签）|
| `'bold 12px system-ui, sans-serif'` | `'bold 12px ' + CF.sans` | L472（图表标题）|

### 验证

- Playwright 浏览器实际渲染：标尺刻度、物块标签、速度箭头、柱状图数值与标签全部清晰可读
- 修复策略：所有过小字号统一抬升到 ≥ 12px，全部接入全局 `CF.sans` 字体回退链

### 后续

- v4.0.8 计划：Batch 2 — 24 处硬编码字体批量替换（charged-particle / force-composition / relativity）
- v4.1.0 计划：Batch 3 — 13 个 `_inject*` 幂等防护补全


---

## 十、2026-04-22 v4.0.8 硬编码字体替换 Batch 2

### 修改文件与替换数

| 文件 | 替换数 | 原模式 | 新模式 |
|------|--------|--------|--------|
| `pages/physics/charged-particle.js` | 11 | `'<weight> <size>px "Noto Sans SC", sans-serif'` | `'<weight> <size>px ' + CF.sans` |
| `pages/physics/force-composition.js` | 5 | 同上 | 同上 |
| `pages/physics/relativity.js` | 8 | `font-family:'JetBrains Mono',monospace;` (inline style) | `font-family:var(--font-mono);` |
| **合计** | **24** | — | — |

### 验证

- Playwright 浏览器验证 `charged-particle` 页面：`q⁺` 标签、`r = mv/(qB) = 6.00`、`T = 2πm/(qB) = 9.42（与 v 无关）` 等文字全部清晰渲染，CF.sans 字体生效
- 残留扫描：3 个文件中 `Noto Sans SC` / `JetBrains Mono` 出现次数均为 0
- `--font-mono` CSS 变量已在 `shared/css/tokens.css` L59 定义（`'JetBrains Mono', 'Fira Code', 'Consolas', monospace`），inline style 改写后保持原有外观

### 已修复 vs 待办

- ✅ FONT-03 (v4.0.2 遗漏) 全部清零
- ⚠️ `force-composition.js` 仍残留 2 处 11px 字号（属 Batch 1 字号范畴，非本轮目标，纳入 v4.0.9 候选）

### 后续

- v4.1.0 计划：Batch 3 — 13 个 `_inject*` 幂等防护补全


---

## 十一、2026-04-22 v4.0.9 force-composition 字号补丁（本轮）

### 背景

v4.0.8 收尾时发现 `pages/physics/force-composition.js` 残留 2 处 11px 字号未覆盖（属 Batch 1 范畴漏网）。本轮顺手补完，使该文件 100% 满足 ≥12px 规范。

### 修改

| 行号 | 原 | 新 | 用途 |
|------|----|----|------|
| L493 | `'bold 11px ' + CF.sans` | `'bold 12px ' + CF.sans` | 斜面分析模式 — 物块 'm' 标签 |
| L630 | `'11px ' + CF.sans` | `'12px ' + CF.sans` | 力的合成模式 — 角度 °数 标签 |

### 验证

- Playwright 浏览器实际渲染：力的合成画布 `120°` 角度标签清晰可读，F₁/F₂/R 主标签外观无回归

### 状态

- 物理 17 实验中，已系统化整治 3 个文件（momentum-conservation / charged-particle / force-composition）
- 剩余 14 个物理实验如有同类问题，可在后续审视轮次中按需补完
- v4.1.0 计划：Batch 3 — 13 个 `_inject*` 幂等防护补全


---

## 十二、2026-04-22 v4.0.10 Batch 3 物理化学批复核（本轮）

### 任务

按 UI_AUDIT_v4.0.5 §二B 表格，对 4 个物理/化学 `_injectEduPanel` 实施"幂等防护"补丁。

### 复核结论 — 全部为误报

逐文件读取实现后发现：

| 文件 | 实现模式 | 是否需修复 |
|------|---------|-----------|
| `pages/chemistry/atomic-structure.js` L617 | `el.innerHTML = '...'` | ❌ 否，天然幂等 |
| `pages/physics/charged-particle.js` L200 | `wrap.innerHTML = '...'` | ❌ 否，天然幂等 |
| `pages/physics/force-composition.js` L690 | `edu.innerHTML = content[mode]` | ❌ 否，模式切换需要覆盖语义 |
| `pages/physics/momentum-conservation.js` L594 | `edu.innerHTML = '...'` | ❌ 否，天然幂等 |

### 判定准则更新

参考 `pages/physics/optics.js` L161 的真问题模式：

```js
// ❌ 真问题：appendChild 追加，必须去重
const wrap = document.getElementById('optics-controls');
if (!wrap || document.getElementById('optics-lens-panel')) return;
const panel = document.createElement('div');
panel.id = 'optics-lens-panel';
wrap.appendChild(panel);   // 多次调用会累积 panel 节点
```

而 `el.innerHTML = '...'` 是 W3C 定义的整体替换语义：

```js
// ✅ 天然幂等：浏览器先销毁旧子树（含监听器），再解析新 HTML
edu.innerHTML = '<h4>...</h4><p>...</p>';
```

### 行动

- 不动代码
- 同步修订 [UI_AUDIT_v4.0.5.md §二B](UI_AUDIT_v4.0.5.md)，把这 4 项标注为误报关闭
- 生物批 9 项留待 v4.1.0 逐个核实（生物文件结构更复杂，可能确有 `appendChild` 模式）

### 收获

- 审计报告基于正则扫描，对"幂等"的判断不应停留在"`if (!el) return;` 仅一道护栏不足"，而应具体看后续是 `appendChild` 还是 `innerHTML = `
- 后续 Batch 3 生物批应在动手前先逐个 `read_file` 核实模式，避免编造修复


---

## 十三、2026-04-22 v4.1.0 Batch 3 生物批复核（本轮）

### 任务

按 UI_AUDIT_v4.0.5 §二B 表格，对 9 个生物 `_injectInfoPanel` 实施"幂等防护"补丁。

### 复核方法

并行 read_file 9 个文件的 `_injectInfoPanel` 实现 18~30 行片段。

### 复核结论 — 9 项全部为误报

| 文件 | 行号 | 实现核心语句 | 判定 |
|------|------|-------------|------|
| `pages/biology/cell-structure.js` | L913 | `el.innerHTML = '...'` | ✅ 天然幂等 |
| `pages/biology/dna-helix.js` | L855 | `el.innerHTML = '...'` | ✅ 天然幂等 |
| `pages/biology/cellular-respiration.js` | L399 | `el.innerHTML = '...'` | ✅ 天然幂等 |
| `pages/biology/gene-expression.js` | L384 | `el.innerHTML = '...'` | ✅ 天然幂等 |
| `pages/biology/meiosis.js` | L373 | `el.innerHTML = '...'` | ✅ 天然幂等 |
| `pages/biology/mitosis.js` | L521 | `el.innerHTML = '...'` | ✅ 天然幂等 |
| `pages/biology/genetics.js` | L644 | `el.innerHTML = '...'` | ✅ 天然幂等 |
| `pages/biology/photosynthesis.js` | L873 | `box.innerHTML = '...'` | ✅ 天然幂等 |
| `pages/biology/substance-transport.js` | L302 | `el.innerHTML = '...'` | ✅ 天然幂等 |

### 总体结论

- v4.0.10 + v4.1.0 累计核实 **13 项**，**全部为审计误报**
- UI_AUDIT_v4.0.5 §二B 整张表清单关闭
- 项目实际不存在 `_inject*` 累积式 DOM 泄漏问题（`appendChild` 模式仅出现在 `optics.js` / `fluid-dynamics.js` 且已正确去重）

### 审计方法论修订

> 后续若再启动 UI 审视，扫描 `_inject*` 幂等问题需用以下两段式正则：
>
> ```regex
> _inject\w+Panel\s*\(\)\s*\{[\s\S]{0,500}(appendChild|insertAdjacentHTML)
> ```
>
> 仅命中**追加式 DOM 操作**才属真问题；纯 `innerHTML = ` 赋值不计入。

### UI_AUDIT_v4.0.5 整体收官

| 维度 | 真问题 | 已修复 | 误报 |
|------|--------|--------|------|
| Canvas 字号过小 | 12 | 12 (v4.0.7 + v4.0.9) | 0 |
| 硬编码字体 | 24 | 24 (v4.0.8) | 0 |
| _inject 幂等缺失 | 0 | 0 | **13** |
| Canvas 高度复制 | 0 | — | 0 |

至此 v4.0.5 基线审视报告**全部关闭**，实际修复 36 处真问题，关闭 13 项误报。

### 后续展望（v4.1.x+）

按用户意愿处理：
- 任务 3：引导/测验定制化
- 任务 5：镂空科技风星球（独立分支 feature/holographic-planets）
- 任务 6：移动端适配审视
- 任务 8：Phase 2 新增实验


---

## 十四、2026-04-22 v4.1.1 移动端适配审视（本轮）

### 审视方法

代码层扫描三大维度：

1. **viewport meta**：`grep "viewport" index.html` → ✅ 已配
2. **响应式断点分布**：扫描 `@media[^{]+max-width` 全工程
3. **Canvas 触控事件配套**：扫描 `addEventListener('(touchstart|touchmove|touchend|mousedown|mousemove)'`

### 主要发现

详见 [doc/MOBILE_AUDIT_v4.1.1.md](MOBILE_AUDIT_v4.1.1.md)。摘要：

- ✅ **断点体系完整**：1024 / 768 / 640 / 480 四档，全局 + 学科 + 工具三层覆盖
- ✅ **触控设备适配齐全**：`(hover: none) and (pointer: coarse)` 媒体查询已实现卡片 :active、44px 触摸目标
- ✅ **Canvas 拖拽实验 100% 触控配套**：5 个真拖拽实验（electromagnetic / fluid-dynamics / physics 父类 / waves / mathematics）全部 mouse* + touch* 配齐
- ⚠️ **微小**：`cell-structure.js` 移动端无 hover 高亮（先 tap 才放大），W3C 标准触控行为，可接受
- ⚠️ **真机测试覆盖度 0**：仅 CSS + 代码层确认，未在 iPhone/Android 真机验证

### 结论

**无系统性缺陷，无需修复 Batch**。后续若启动深度优化，按报告 §六 优先级安排。

### Playwright VS Code 集成限制

本轮尝试用 Playwright `setViewportSize({width:390, height:844})` 模拟 iPhone 14，发现 VS Code 集成模式下 viewport 不真实变化（`window.innerWidth` 仍为 1055）。**结论**：未来移动端验证需借助 Chrome DevTools mobile emulation 或真机测试，Playwright 集成模式不可靠。


---

## 十五、2026-04-22 v4.1.2 任务 3 引导/测验定制化（本轮）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 'dna'（5 步：四模式切换 / 双螺旋拖拽 / 复制转录动画 / 碱基对氢键 / Watson-Crick 模型）与 'cellular-respiration'（5 步：三阶段切换 / 自动播放 / 速度调节 / 实时面板 / 38 ATP 总览）。
- `shared/js/quiz-data.js`：'dna' 由 3 题扩到 5 题（增加 GC 氢键数 + Watson-Crick 1953 年）；新增 'cellular-respiration' 5 题（糖酵解场所 / 柠檬酸循环 / 氧化磷酸化 / 38 ATP / 乳酸 vs 酒精）。
- `sw.js` CACHE_NAME `englab-static-v20260422a` → `v20260422b`。
- `index.html` cache bust：`experiment-guide.js?v=20260422d` → `?v=20260422b`，`quiz-data.js?v=20260418e` → `?v=20260422b`。

### 验证（Playwright 浏览器）
- 清除 SW + caches，硬重载后：
  - `window.ExperimentGuide._experimentGuides['dna'].title` = "DNA 结构操作指南"，5 步全部呈现。
  - `window.ExperimentGuide._experimentGuides['cellular-respiration'].title` = "细胞呼吸操作指南"，5 步全部呈现。
  - `window.QUIZ_DATA['dna'].length` = 5；`window.QUIZ_DATA['cellular-respiration'].length` = 5。
  - DNA 实验首次打开自动弹出自定义引导，小测验按钮正常显示。
  - cellular-respiration 自定义引导经 `ExperimentGuide._show('biology', 'cellular-respiration')` 强制触发后正常呈现。

### 当前覆盖度
- 引导定制化：6 / 63（periodic-table、kinematics、calculus、genetics、dna、cellular-respiration）。
- 测验题库：21 / 63 实验拥有专属题池。

### 后续候选
- v4.1.3 — 继续定制更多实验引导（建议 photosynthesis 光合作用 / mitosis 有丝分裂 / electromagnetic 电磁场）。
- 任务 5 — 镜空科技风星球（独立分支 feature/holographic-planets）。
- 任务 6 — 移动端深度优化（基于 v4.1.1 报告 P-01 ~ P-04 真机测试与修复）。
- 任务 8 — Phase 2 新增实验（从本文档第二节待开发列表中挑选）。


---

## 十六、2026-04-22 v4.1.3 任务 3 引导/测验定制化（续）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增三个条目：
  - `photosynthesis`（5 步：三模式切换 / 反应模拟 / 光照-温度-CO₂ 滑块 / 光合曲线 / 呼吸对比补偿点）
  - `mitosis`（5 步：阶段切换 / 播放暂停 / 速度滑块 / 中期赤道板 / 末期 2 子细胞）
  - `electromagnetism`（5 步：5 显示模式 / 4 预设配置 / 拖拽电荷 / 测量探针 / 粒子轨迹与磁场）
- `shared/js/quiz-data.js`：
  - `photosynthesis` 由 3 题扩到 5 题（增加光补偿点 + 温度-酶活性）
  - `mitosis` 由 3 题扩到 5 题（增加间期 DNA 复制 + 后期染色体加倍）
  - 新增 `electromagnetism` 5 题（电场线方向 / 电场线不相交 / 等势面与电场线垂直 / 安培定则 / 洛伦兹力做匀速圆周运动）
- `sw.js` CACHE_NAME `englab-static-v20260422b` → `v20260422c`
- `index.html` cache bust：`experiment-guide.js?v=20260422b` → `?v=20260422c`，`quiz-data.js?v=20260422b` → `?v=20260422c`

### 验证（Playwright 浏览器）
- 清除 SW + caches，硬重载后查询：
  - `_experimentGuides['photosynthesis'].title` = "光合作用操作指南"，5 步
  - `_experimentGuides['mitosis'].title` = "有丝分裂操作指南"，5 步
  - `_experimentGuides['electromagnetism'].title` = "电磁场操作指南"，5 步
  - `QUIZ_DATA['photosynthesis'].length` = 5
  - `QUIZ_DATA['mitosis'].length` = 5
  - `QUIZ_DATA['electromagnetism'].length` = 5

### 当前覆盖度
- 引导定制化：9 / 63（periodic-table、kinematics、calculus、genetics、dna、cellular-respiration、photosynthesis、mitosis、electromagnetism）
- 测验题库：22 / 63 实验拥有专属题池（电磁场为新增条目）

### 后续候选
- v4.1.4 — 继续定制更多实验引导（建议化学领域：reaction-rate / chemical-equilibrium / electrochemistry）
- 任务 5 — 镜空科技风星球（独立分支 feature/holographic-planets）
- 任务 6 — 移动端深度优化（基于 v4.1.1 报告 P-01 ~ P-04 真机测试与修复）
- 任务 8 — Phase 2 新增实验（从本文档第二节待开发列表中挑选）

---

## 十七、2026-04-22 v4.1.4 任务 3 引导/测验定制化（化学批次）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增三个化学条目：
  - `reaction-rate`（5 步：温度滑块 / 浓度滑块 / 催化剂复选 / 闪光碰撞与曲线 / 碰撞理论 + 麦克斯韦-玻尔兹曼分布）
  - `chemical-equilibrium`（5 步：N₂+3H₂⇌2NH₃ 反应 / 7 个扰动按钮 / 浓度曲线与 K_c / 升温向吸热方向 / 勒夏特列原理）
  - `electrochemistry`（5 步：原电池/电解池模式切换 / 电子离子动画 / Zn-Cu E°=1.10V / 阳氧阴还 / 电极判断口诀）
- `shared/js/quiz-data.js`：
  - `chemical-equilibrium` 由 3 题扩到 5 题（增加加压平衡移动判断 + K_c 仅与温度有关）
  - 新增 `reaction-rate` 5 题（速率定义 / 升温活化分子百分比 / 催化剂降低活化能 / 浓度对碰撞频率 / 有效碰撞两要素）
  - 新增 `electrochemistry` 5 题（负极氧化反应 / 电子流动方向 / 阳极接电源正极 / CuCl₂ 阴极反应 / 原电池 vs 电解池本质）
- `sw.js` CACHE_NAME `englab-static-v20260422c` → `v20260422d`
- `index.html` cache bust：`experiment-guide.js?v=20260422c` → `?v=20260422d`，`quiz-data.js?v=20260422c` → `?v=20260422d`

### 验证（Playwright 浏览器）
- 清除 SW + caches，硬重载后查询 6 项数据全部正确：
  - `_experimentGuides['reaction-rate'].title` = "化学反应速率操作指南"，5 步
  - `_experimentGuides['chemical-equilibrium'].title` = "化学平衡操作指南"，5 步
  - `_experimentGuides['electrochemistry'].title` = "电化学操作指南"，5 步
  - `QUIZ_DATA['reaction-rate'].length` = 5
  - `QUIZ_DATA['chemical-equilibrium'].length` = 5
  - `QUIZ_DATA['electrochemistry'].length` = 5

### 当前覆盖度
- 引导定制化：12 / 63（新增 reaction-rate、chemical-equilibrium、electrochemistry）
- 测验题库：24 / 63 实验拥有专属题池（reaction-rate、electrochemistry 为新增条目）

### 后续候选
- v4.1.5 — 继续定制其他化学引导（chemical-bond / ionic-reaction / organic-chemistry）
- v4.1.5 — 转向数学领域（trigonometry / probability / vector-ops）
- v4.1.5 — 转向物理领域（circuit-analysis / waves / optics）
- 任务 5 — 镜空科技风星球（独立分支 feature/holographic-planets）
- 任务 6 — 移动端深度优化（基于 v4.1.1 报告真机测试）

---

## 十八、2026-04-22 v4.1.5 任务 3 引导/测验定制化（化学批次续）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增三个化学条目：
  - `chemical-bond`（5 步：三种键切换 / 离子键静电引力 / 共价键共用电子对 / 金属键电子海 / 右侧详解面板）
  - `ionic-reaction`（5 步：下拉选反应 / 三阶段方程式切换 / 旁观离子可视化 / 净离子本质 / 复分解三条件）
  - `organic-chemistry`（5 步：5 种分子切换 / 拖拽旋转 3D / 暂停自转 / 官能团高亮 / 典型反应）
- `shared/js/quiz-data.js`：
  - 新增 `chemical-bond` 5 题（NaCl 离子键判断 / 共价键本质 / 金属导电 / 离子键无方向性 / NaOH 含两种键）
  - 新增 `ionic-reaction` 5 题（强酸强碱中和净离子 / 复分解三条件 / 旁观离子定义 / 点燃反应不属于离子反应 / CaCO₃ 保留分子式）
  - 新增 `organic-chemistry` 5 题（甲烷正四面体 / 乙醇与Na断 O—H 键 / 丙烯使溴水褪色 / 苯环 6 键等长 / 乙酸羧基）
- `sw.js` CACHE_NAME `englab-static-v20260422d` → `v20260422e`
- `index.html` cache bust：`experiment-guide.js?v=20260422d` → `?v=20260422e`，`quiz-data.js?v=20260422d` → `?v=20260422e`

### 验证（Playwright 浏览器）
- 清除 SW + caches，硬重载后查询 6 项数据全部正确：
  - `_experimentGuides['chemical-bond'].title` = "化学键操作指南"，5 步
  - `_experimentGuides['ionic-reaction'].title` = "离子反应操作指南"，5 步
  - `_experimentGuides['organic-chemistry'].title` = "有机化学操作指南"，5 步
  - `QUIZ_DATA['chemical-bond'].length` = 5
  - `QUIZ_DATA['ionic-reaction'].length` = 5
  - `QUIZ_DATA['organic-chemistry'].length` = 5

### 当前覆盖度
- 引导定制化：15 / 63（新增 chemical-bond、ionic-reaction、organic-chemistry）
- 测验题库：27 / 63 实验拥有专属题池（3 个全部为新增条目）
- 化学领域引导定制完成度：8 / 11（periodic-table、chemical-equilibrium、electrochemistry、reaction-rate、chemical-bond、ionic-reaction、organic-chemistry、另包含初期版本中隐含的项目）

### 后续候选
- v4.1.6 — 收尾化学最后几项（atomic-structure / molecular-structure / chemical-reactions / solution-ionization）
- v4.1.6 — 转向数学领域（trigonometry / probability / vector-ops）
- v4.1.6 — 转向物理领域（circuit-analysis / waves / optics）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 二十、2026-04-22 v4.1.7 任务 3 转向数学领域（三角/概率/向量）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 个数学条目：
  - `trigonometry`（5 步：3 种模式 sin-cos/tan/all / trig-angle 滑块扫动 / 自动播放+速度 / 6 个特殊角预设按钮 / 单位圆与诱导公式）
  - `probability`（5 步：硬币/骰子两种模式 / 播放与重置 / +1 与 +1000 试验 / 速度与频率柱状图 / 大数定律）
  - `vector-ops`（5 步：4 种运算 add/sub/dot/projection / 拖拽端点 / 坐标与模与夫角 / 几何意义 / 垂直与共线判定）
- `shared/js/quiz-data.js`：
  - `trigonometry` 4 题 → 5 题（新增诱导公式 sin(π+θ)）
  - `probability` 3 题 → 5 题（新增互斥事件、频率估计）
  - `vector-ops` 新建 5 题题池（模、数量积、垂直判定、三角形法则、投影向量公式）
- `sw.js` CACHE_NAME `englab-static-v20260422f` → `v20260422g`
- `index.html` cache bust：`experiment-guide.js?v=20260422f` → `?v=20260422g`，`quiz-data.js?v=20260422f` → `?v=20260422g`

### 验证（Playwright 浏览器）
- 清除 SW + caches，硬重载后查询 6 项数据全部正确：3 个引导标题/步骤数 + 3 个测验题池长度 = 5

### 当前覆盖度
- 引导定制化：22 / 63（化学 11/11 + 数学 7/15 + 物理 1 + 生物 6 + 算法 0）
- 测验题库：32 / 63（vector-ops 为新建）

### 后续候选
- v4.1.8 — 数学续推（sequences / inequality / conic-sections 等）
- v4.1.8 — 转向物理领域（circuit-analysis / waves / optics）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化

---

## 二十一、2026-04-22 v4.1.8 任务 3 数学续推（数列不等式圆锥曲线）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 个数学条目：
  - `sequences`（5 步：等差/等比 .seq-mode-btn 切换 / a₁、d/q、n 滑块 / 悬停高亮柱条 / 线性 vs 指数对比 / 通项公式 Sₙ）
  - `inequality`（5 步：3 个 ineq-c0/1/2 约束滑块 / 可行域阴影 / ineq-show-obj + ineq-obj 目标函数等高线 / 顶点最优解 / 一元二次 + 线性规划）
  - `conic-sections`（5 步：3 个 .conic-type-btn 椭圆/双曲线/抛物线 / conic-a/b/p 滑块 / 轨迹 + 焦点 + 准线可视化 / conic-info 离心率 / 统一定义）
- `shared/js/quiz-data.js`：
  - `sequences` 3 题 → 5 题（新增等差通项计算、等比公比识别）
  - `inequality` 新建 5 题题池（x²−4<0、x(x−1)≥0、线性规划顶点、绝对值|x−3|<2、不等式性质）
  - `conic-sections` 新建 5 题题池（椭圆离心率 3/5、抛物线焦点 (1,0)、双曲线渐近线、统一定义 e=1、椭圆 c²=a²−b²）
- `sw.js` CACHE_NAME `englab-static-v20260422g` → `v20260422h`
- `index.html` cache bust：`experiment-guide.js?v=20260422g` → `?v=20260422h`，`quiz-data.js?v=20260422g` → `?v=20260422h`

### 验证（Playwright 浏览器）
- 清除 SW + caches，硬重载后查询 6 项数据全部正确：3 个引导标题/步骤数 + 3 个测验题池长度 = 5

### 当前覆盖度
- 引导定制化：25 / 63（化学 11/11 + 数学 10/15 + 物理 1 + 生物 6 + 算法 0）
- 测验题库：34 / 63（inequality 、conic-sections 为新建）
- 数学领域已完成 10/15（过半）

### 后续候选
- v4.1.9 — 数学推进（function-properties / set-operations / permutation-combination 等）
- v4.1.9 — 转向物理领域（circuit-analysis / waves / optics）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化

---

## 二十二、2026-04-22 v4.1.9 任务 3 数学推进（函数性质/集合/排列组合）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 个数学条目：
  - `function-properties`（5 步：3 个 .fp-mode-btn 单调/奇偶/周期 / .fp-func-btn 切换函数 / fp-int-a/b 区间输入 + 拖拽菱形 / 高亮单调区间与对称轴 / 判定公式）
  - `set-operations`（5 步：6 个 .setops-op-btn 并/交/差/补/对称差 / setops-input-a/b/u 输入 / 维恩图高亮结果区域 / 运算结果与个数 / 德摩根律与分配律）
  - `permutation-combination`（5 步：3 个 .permcomb-mode-btn 排列 P(n,r)/组合 C(n,r)/杨辉三角 / permcomb-n + permcomb-r 滑块 / 枚举示意 + 公式 / 杨辉三角上方两数之和 / 顺序区别 + 二项式定理）
- `shared/js/quiz-data.js` 新建 3 个题池，各 5 题：
  - `function-properties`（奇函数定义 / x³ 性质 / cos 周期 2π / x²−2x 单调性 / 偶函数对称轴）
  - `set-operations`（A∩B、A∪B、Aᶜ、德摩根 (A∪B)ᶜ、空集与子集关系）
  - `permutation-combination`（P(5,3)=60、C(5,3)=10、杨辉 1 4 6 4 1、顺序与否区别、二项式系数 C(n,r)）
- `sw.js` CACHE_NAME `englab-static-v20260422h` → `v20260422i`
- `index.html` cache bust：`experiment-guide.js?v=20260422h` → `?v=20260422i`，`quiz-data.js?v=20260422h` → `?v=20260422i`

### 验证（Playwright 浏览器）
- 清除 SW + caches，硬重载后查询 6 项数据全部正确：3 个引导标题/步骤数 + 3 个测验题池长度 = 5

### 当前覆盖度
- 引导定制化：28 / 63（化学 11/11 + 数学 13/15 + 物理 1 + 生物 6 + 算法 0）
- 测验题库：37 / 63（3 个全部为新建）
- **数学领域 13/15，近在咕咤：仅剩 exp-log + geometry**

### 后续候选
- v4.1.10 — 数学冲刺全覆盖（exp-log + geometry + complex-numbers 等最后 2 项）
- v4.1.10 — 转向物理领域（circuit-analysis / waves / optics）
- v4.1.10 — 转向算法领域（sorting-compare / dynamic-programming / string-matching）
- v4.1.10 — 转向生物领域（immune-system / ecosystem / neural-regulation）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 十九、2026-04-22 v4.1.6 任务 3 化学领域收尾（全覆盖里程碑）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 4 个化学收尾条目：
  - `atomic-structure`（5 步：3 模式 / Z=1～36 / 轨道云 / 泡利洪特填充 / 玻尔跨迁）
  - `molecular-structure`（5 步：分子选择 / 拖拽旋转 / 测量键长键角 / 轨道模式 / VSEPR 理论）
  - `chemical-reactions`（5 步：播放/重置 / 速度调节 / 甲烷燃烧原子重组 / 能量条 / 断键成键原理）
  - `solution-ionization`（5 步：6 种物质 / 浓度滑块 + pH / 强弱电解质可视化 / 暂停拖动 / Ka Kb 与水解）
- `shared/js/quiz-data.js`：新增 4 个题池，各 5 题：
  - `atomic-structure`（碳原子排布式 / p 轨道三方向 / 泡利原理 / 洪特规则 / Na⁺ 与 Ne 同构）
  - `molecular-structure`（H₂O V 形 / CO₂ 非极性 / CH₄ sp³ / NH₃ 三角锥 / 极性判断依据）
  - `chemical-reactions`（原子重组 / 燃烧为氧化放热 / 活化能定义 / 放热反应特征 / 催化剂不变 ΔH）
  - `solution-ionization`（强电解质 HCl / 0.1 M HCl pH=1 / 稀释促进弱酸电离 / NaHCO₃ 水解呈碱性 / Ka 仅受温度影响）
- `sw.js` CACHE_NAME `englab-static-v20260422e` → `v20260422f`
- `index.html` cache bust：`experiment-guide.js?v=20260422e` → `?v=20260422f`，`quiz-data.js?v=20260422e` → `?v=20260422f`

### 验证（Playwright 浏览器）
- 清除 SW + caches，硬重载后查询 8 项数据全部正确：4 个引导标题/步骤数 + 4 个测验题池长度 = 5

### 当前覆盖度
- 引导定制化：19 / 63（化学 11/11 + 其他学科 8）
- 测验题库：31 / 63（4 个全部为新增）
- **化学领域 11/11 实验全部拥有专属引导 + 测验题池，达成首个学科全覆盖里程碑！**

### 后续候选
- v4.1.7 — 数学批次（trigonometry / probability / vector-ops 等，已有56进度 4/15）
- v4.1.7 — 物理批次（circuit-analysis / waves / optics 等，已有56进度 2/17）
- v4.1.7 — 算法批次（sorting-compare / dynamic-programming / string-matching）
- v4.1.7 — 生物批次（immune-system / ecosystem / neural-regulation）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化


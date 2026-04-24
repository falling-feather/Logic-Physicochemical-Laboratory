# 工科实验室 — 后续更新计划

> **制定日期**: 2026-04-13 | **最后更新**: 2026-04-24 | **状态**: Phase 1 内容规划全部完成，进入 Phase 2 深化阶段
>
> **📌 文档边界约定**（自 v4.0.4 起）：本文档仅承载 *近期已完成增量*（最近 1-2 个小版本）+ *未来更新规划*。所有历史完成的大版本（≤ v4.0.1）、阶段性实验汇总、完整 Bug 修复履历，请参阅 [`doc/have_done.md`](have_done.md)。两份文档分工：UPDATE_PLAN 面向"下一步"，have_done 面向"已沉淀"。

---

## 〇、近期已完成增量（v4.5 系列，feature/v4.5 分支）

| 微版本 | 提交 | 内容 |
| ------ | ---- | ---- |
| v4.5.0-α1 | `eb2c9e2` | 全局搜索（Ctrl+K，63 实验跨学科模糊匹配，键盘 ↑↓ Enter ESC，关键词高亮，700ms 深链跳转）|
| v4.5.0-α2 | `a357225` | 快捷键系统（Ctrl/Alt+1~5 切学科、Ctrl+0 首页、Ctrl+\` 星系、`/` 打开搜索）+ 中央 toast 反馈 |
| v4.5.0-α3 | `48618c7` | 实验底部跨学科推荐（4 张卡片，bigram 重合度+同学科加权+相邻学科加权评分）|
| v4.5.0-α4 | `dfc02dc` | 化学优化 7-1：molecular-structure 移除 NaCl 条目（NaCl 是离子化合物，不是分子）+ 新增键参数表（O—H/C—H/C=O/C—C/C≡C 等 11 类，含键长 Å、键能 kJ·mol⁻¹、键类型 σ/π 标注）+ 苯环/CO₂ 专属覆盖；缓存 v45d |
| v4.5.0-α5 | `036641c` | 化学优化 7-2：molecular-structure 新增 3 个分子 — HCHO（甲醛）/H₂S（V 形，附"与 H₂O 同族对比表"）/CH₃COOH（乙酸，sp³+sp² 混合杂化）；bondData 增 H-S 键项；updateInfo 新增 hybNote/compareWith 渲染逻辑（三色分层）；缓存 v45e |
| **v4.5.0-α6** | **本轮** | **化学优化 7-3a：chemical-reactions 中和反应重做 — 由"HCl + NaOH → NaCl + H₂O 共价/离子键重组"改为"H⁺ + OH⁻ → H₂O 离子方程式 + Na⁺/Cl⁻ 旁观"；reactantMols 拆为 4 个独立水合离子（H⁺ / OH⁻ / Na⁺ / Cl⁻），productMols 为 H₂O + Na⁺/Cl⁻（仍为水合离子）；atom 加 `charge` 字段、mol 加 `spectator` 字段；新增 `_drawChargeBadge`（红正/蓝负圆形徽章）+ 旁观离子虚线圈包裹；reaction 加 `fullEquation` 字段（同时显示离子方程式与总式，主式上移让位）；缓存 v45f** |

**v4.5.0-α6 修改文件**：
- `pages/chemistry/chemical-reactions.js`：
  - `reactions.neutralization` 完全重写：name/equation/fullEquation/desc/mechanism 全部对齐离子反应本质
  - reactantMols/productMols：4 个独立离子条目，atom 加 `charge: '+'/'-'`，旁观离子 mol 加 `spectator: true`
  - `buildScene()`：将 `charge`/`spectator` 字段从 mol 级传播到 atom 级
  - `_drawMolecules()`：原子绘制后追加电荷徽章 + spectator 虚线圈
  - 新增 `_drawChargeBadge()`：右上角小圆，正电红色、负电蓝色
  - canvas 底部 equation 渲染：当 `fullEquation` 存在时主式上移到 H-28、总式置 H-10、反应历程提到 H-48
- `index.html`：chemical-reactions.js 加缓存 `?v=20260424v45f`
- `sw.js`：CACHE_NAME → `v20260424v45f`

**待办（化学 7 系列剩余子任务）**：
- 7-3b（α7 计划）chemical-reactions：(i) 重做 redox 为离子方程式 Fe + Cu²⁺ → Fe²⁺ + Cu + 电子转移动画；(ii) 新增 dissolution 反应（NaCl 在水中溶解，只断 Na-Cl 离子键、不断 H-O 共价键）
- 7-4 chemical-bond 强调微粒+静电引力/斥力构成
- 7-5 organic-chemistry 去与 molecular-structure 重复 + 加乙烯/苯共面 + 乙炔共线 + 单键旋转交互

**v4.5 系列尾声待办**：
- 合并 `feature/v4.5` 当前 6 个 alpha 到 main 打 `v4.5.0` tag（按 git-workflow.md）
- 历史细节保留在 `legacy/v4.5-detail`

---

## 〇·一、历史增量（v4.4 系列，已合并 main 打 v4.4.0 tag）

> v4.4 主线：**「星系导航」从纯视觉装饰升级为正式的「目录入口」**。八个微版本闭环了 进入 → 浏览 → 跳转 → 返回 的完整导航动画体系。

| 微版本 | 提交 | 内容 |
| ------ | ---- | ---- |
| v4.4.0-α1 | `1eea036` | 主题色 绿→蓝 全局换色；FAB（截图/导出）改造为悬浮三角触发器，避免遮挡 |
| v4.4.0-α2 | `303abf8` | 进入 `#planets` 时顶部导航完全隐藏（`navbar--hidden`），消除遮挡 |
| v4.4.0-α3 | `d904e62` | **星系作为目录**：点击行星进入「学科子星系」，13~17 个实验作为该行星的卫星/小行星 |
| v4.4.0-α4 | `a04996a` | 子星系视觉调优：双环半径 1.10/1.65、卫星 18~34px、所有卫星名称常驻、tIn 0.15 |
| v4.4.0-α5 | `04a4839` | **zoom-into-satellite**：点击卫星触发 480ms 中心缩放联动动画后再跳转 |
| v4.4.0-α6 | `f2bb6e1` | 首页加「进入星系目录」CTA + 顶栏加 `nav-item--galaxy` 入口（轨道图标 9s 自转） |
| v4.4.0-α7 | `023eb1a` | 子星系顶部「面包屑」：`[主星系] › 数学 [· 实验名]`；hover 卫星淡入实验名段 |
| v4.4.0-α8 | `ae7d94e` | **zoom-out 退出动画**：380ms 中央外扩爆发 + 冲击波 + 卫星径向推离 + subject 层衰减 |

**关键技术实现**：
- 双模式状态机：`mode: 'galaxy' | 'subject'`，`tIn / tInTarget` 控制层间过渡
- 入场动画：`tLaunch` 0→1 (480ms 线性) + `_navTimer` setTimeout 链式调用 `ModuleSelector.openModule(subjectId, expId)` 深度链接
- 出场动画：`exiting / tOut` 状态，`_finalizeExitSubject` 在动画结束后才真正切回 galaxy
- 三种退出入口（ESC / 中央恒星 / 面包屑「主星系」）统一进入 `_exitSubject()`
- 缓存版本演进：`v44a → v44g`（同步 `sw.js` CACHE_NAME 与 `index.html` ?v= 查询参数）
- Git 工作流：所有微版本均在 `feature/v4.4` 分支累积，待大版本汇总后合并到 main 打 V4.4.0 tag

**待办**：
- 合并 `feature/v4.4` 8 个 alpha 到 main 打 `v4.4.0` tag（按 git-workflow.md 用 `git commit-tree` 手工构造合并 commit）
- 历史细节保留在 `legacy/v4.4-detail` 分支

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
| **v4.1.9** | **任务 3 数学推进：function-properties + set-operations + permutation-combination 各加 5 步定制引导 + 测验题全部新增各 5 题（嵌入奇偶函数判定、德摩根律、二项式定理等）** | ✅**已完成** |
| **v4.1.10** | **任务 3 数学冲刺完结：exp-log + geometry + complex-numbers 各加 5 步定制引导 + 测验题全部新增各 5 题（提及指对互为反函数、仿射变换不可交换、欧拉公式 e^(iπ)+1=0 等）** | ✅**已完成** |
| **v4.1.11** | **任务 3 数学完结 + 起步物理：solid-geometry + circuit-analysis + waves 各加 5 步定制引导 + 5 题测验（冸台体欧拉 V-E+F=2、串联/并联分压分流、波速 v=fλ与多普勒），数学 15/15 ✅** | ✅**已完成** |
| **v4.1.12** | **任务 3 物理运动学三件套：kinematics + projectile + circular-motion 各加 5 步定制引导 + 5 题测验（匀变速 v²−v₀²=2as、斜抛 45° 最远、圆周 v=ωr/F=mv²/r），物理 6/17** | ✅**已完成** |
| **v4.1.13** | **任务 3 物理电磁学三件套：optics + electromagnetic-induction + alternating-current 各加 5 步定制引导 + 5 题测验（透镜公式 1/u+1/v=1/f、法拉第 ε=-dΦ/dt、变压器匝数比），物理 9/17** | ✅**已完成** |
| **v4.1.14** | **任务 3 物理力学三件套：force-composition + momentum-conservation + gravitation 各加 5 步定制引导 + 5 题测验（平行四边形定则、3 种碰撞型式、万有引力 F=GMm/r²），物理 12/17** | ✅**已完成** |
| **v4.1.15** | **任务 3 物理高阶三件套：electromagnetic + charged-particle + relativity 各加 5 步定制引导 + 5 题测验（库仑 E=kQ/r²、洛伦兹力 r=mv/(qB)、相对论 γ=1/√(1−β²)），物理 15/17** | ✅**已完成** |
| **v4.1.16** | **任务 3 物理收尾 + 算法起步：energy-conservation + fluid-dynamics + sorting-compare 各加 5 步定制引导 + 5 题测验（机械能守恒、伯努利、排序复杂度），物理 17/17 ✅ 、算法 1/8 起步** | ✅已完成 |
| **v4.1.17** | **任务 3 算法三件套：search-algorithms + dynamic-programming + string-matching 各加 5 步定制引导 + 5 题测验（二分查找、背包 DP、KMP），算法 4/8 、引导 52/63 、测验 61/63** | ✅已完成 |
| **v4.1.18** | **任务 3 算法收尾三件套：data-structures + recursion-vis + graph-algo 各加 5 步定制引导 + 5 题测验（栈队列 BST、递归三要素、Dijkstra），算法 7/8 、引导 55/63 、测验 63/63 ✅ 满分** | ✅已完成 |
| **v4.1.19** | **任务 3 算法岁月 ✅ + 生物启动：sorting + immune-system + ecosystem 各加 5 步定制引导 + 5 题测验（桶排序、人体免疫 3 道防线、能量流动 10％），算法 8/8 ✅ 、生物 8/13 、引导 58/63** | ✅已完成 |
| **v4.1.20** | **任务 3 生物 A 套：neural-regulation + cellular-respiration + substance-transport 各加 5 步定制引导 + 5 题测验（突触/动作电位/Na⁺/K⁺、有氧呼吸三阶段38ATP、跨膜运输四方式），生物 11/13 、引导 61/63** | ✅已完成 |
| **v4.1.21** | **🏆 全项收尾满分 🏆：meiosis + gene-expression + gene-mutation 各加 5 步定制引导 + 5 题测验（减分裂 8 期/中心法则/3 类可遗传变异），**生物 13/13 ✅ 、全 5 学科 100%、引导 64/63 ✅✅✅接2 满分冲顶**！** | ✅**已完成** |
| **v4.2.0-α1** | **任务 5 镜空/镂空科技风星球（独立分支 `feature/holographic-planets`）：首页 `#main-star` 重塑为深空青绿 Tron 风全息 HUD —— 经纬球面网格 + 准星十字 + 双层扫描环 + 青绿外圈/眼睛/标题/Tagline** | ✅**已完成（当前分支）** |
| **v4.2.0-α2** | **任务 5 续：5 个学科卫星球 `.satellite-1~5` 同步 HUD 化 —— 透明深空底 + 青绿外圈 + 内部经纬网格/准星十字（继承主星样式）+ 学科色辅助辉光保留识别度（数学蓝/物理紫/化学绿/算法橙/生物teal）** | ✅**已完成（当前分支）** |
| **v4.2.0-α3** | **任务 5 续：首页背景全息化 —— 粒子网络 worker 颜色 蓝→青绿、3 层 nebula 紫/绿/橙 → 三色青绿、hex-grid overlay 蓝→青绿（透明度 3%→4.5%）、新增 `.home-container::after` 全屏 HUD 垂直扫描线（9s 循环）** | ✅**已完成（当前分支）** |
| **v4.2.0** | **任务 5 镜空科技风首页 main 合并：α1 主星 + α2 5 卫星 + α3 全屏背景三件套合并到 main 并 push（feature/holographic-planets 保留）** | ✅**已上线** |
| **v4.2.1** | **任务 6 移动端深度优化：P-02 cell-structure long-press（350ms）替代 hover 预览、P-03 DEVELOPER_GUIDE §12.5 移动端开发规范、P-04 弹窗小屏 safe-area-inset 与 guide-card 滚动修复（quiz/guide/rating 三组件）** | ✅**已完成** |
| **v4.2.0-α4** | **任务 5 续：新增 `#planets` 独立路由 — 沉浸式 3D 镂空星系导航大屏（Vanilla Canvas 2D yaw/pitch 透视 + 5 学科行星轨道环绕 + 拖拽旋转 + 4s 自动慢转 + hover 信息卡 + 点击跳学科 + 4 角 HUD + 中央青色核心 + 220 颗背景星）** | ✅**已完成（feature/holographic-planets）** |
| **v4.2.2-audit** | **任务 7 启动：生物 13 实验文字排版只读审视（172 处 ctx.font + 41 处 fs 全统计、Top10 待修问题汇总、4 阶段修复工作量估算）→ `doc/BIOLOGY_TYPO_AUDIT.md`** | ✅**已完成（main）** |
| **v4.2.2-phase1** | **任务 7 Phase 1：cellular-respiration / ecosystem / immune-system 三件套 P0 修复（fs 公式 `Math.max(13, W*0.012)` → `Math.max(14, Math.min(22, W*0.018))` 提升 W=900 字号 13→16.27px、immune-system HUD 透明度 0.25/0.4/0.5 → 0.7/0.85/0.95 满足 WCAG AA）** | ✅**已完成（main）** |
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

## 二十三、2026-04-22 v4.1.10 任务 3 数学领域冲刺完结（指对/几何/复数）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 个数学条目：
  - `exp-log`（5 步：#el-base 滑块 + 4 个 .el-preset 预设底数 / 3 个 .el-toggle 开关函数 / y=x 镜像验证反函数 / a 跨越 1 的单调性 / 指对运算律）
  - `geometry`（5 步：2 个 .geo-mode-btn 仿射/三角形 / geo-tx/ty/sx/sy/rot/shear 滑块 / #geo-animate-btn 动画 / 拖拽顶点 + 四心 / 变换不可交换）
  - `complex-numbers`（5 步：4 个 .cx-mode-btn ops/roots/domain/euler / cx-z1-re/im + .cx-op-btn 四则 / cx-root-n 单位根 / cx-theta + 欧拉动画 / 模辐角与棣莫弗）
- `shared/js/quiz-data.js` 新建 3 个题池，各 5 题：
  - `exp-log`（y=x 对称 / log₂ 8 / a>1 单调递增 / 换底公式 / a^x·a^y 运算律）
  - `geometry`（旋转相似变换 / 外心 = 垂平分线 / 重心 2:1 / 行列式 = 面积缩放 / 变换不可交换）
  - `complex-numbers`（|3+4i|=5 / 共轭相乘 / e^(iπ)=−1 / 1+i 辐角 π/4 / 4 次单位根 = 正方形）
- `sw.js` CACHE_NAME `englab-static-v20260422i` → `v20260422j`
- `index.html` cache bust：`experiment-guide.js?v=20260422i` → `?v=20260422j`，`quiz-data.js?v=20260422i` → `?v=20260422j`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，6 项数据全部正确（3 个引导标题/5 步 + 3 个题池长度 5）

### 当前覆盖度
- 引导定制化：31 / 63（化学 11/11 ✅ + 数学 14＋/15 + 物理 1 + 生物 6 + 算法 0）
- 测验题库：40 / 63
- **数学领域接近完结，剩余 solid-geometry（该项是否已有引导待检查）**

### 后续候选
- v4.1.11 — 收尾 solid-geometry + 起步物理两项（circuit-analysis + waves）
- v4.1.11 — 专攒物理（circuit-analysis + waves + optics 等）
- v4.1.11 — 转向算法领域（sorting-compare / dynamic-programming / string-matching）
- v4.1.11 — 转向生物领域（immune-system / ecosystem / neural-regulation）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化

---

## 二十四、2026-04-22 v4.1.11 数学 15/15 完结 + 物理起步（立体几何/电路/波动）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 条：
  - `solid-geometry`（5 步：5 个 .sg-shape-btn 几何体 / #sg-cross 截面滑块 / #sg-speed + #sg-pause / 3D 投影与高亮截面 / V−E+F=2 与柏拉图 5 体）
  - `circuit-analysis`（5 步：2 个 .circuit-mode-btn 串联/并联 / circuit-voltage/r1/r2 滑块 / circuit-pause + circuit-reset / 电流粒子 + circuit-info / 串并联公式与功率）
  - `waves`（5 步：3 个 .wave-mode-btn 叠加/驻波/多普勒 / wave-a1/f1/l1+a2/f2/l2 双波参数 / 4 个 [data-wave-preset] 预设 / 三色波形与波节波腹 / v=fλ 与多普勒公式）
- `shared/js/quiz-data.js` 3 个题池全部 5 题：
  - `circuit-analysis` 从 3 扩到 5（加入 4Ω+6Ω 串联 1A、并联 2.4Ω −5A）
  - `waves` 新建（v=fλ / 同相 2A / 反相 0 / 波节定义 / 多普勒饱逆递变低）
  - `solid-geometry` 新建（欧拉公式 V-E+F=2 / 柏拉图 5 体 / 圆柱平截为圆 / 球体积 (4/3)πR³ / 正四面体+正八面体面数和）
- `sw.js` CACHE_NAME `englab-static-v20260422j` → `v20260422k`
- `index.html` cache bust：experiment-guide.js & quiz-data.js 同步升级 `?v=20260422k`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，6 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题）

### 当前覆盖度
- 引导定制化：34 / 63（化学 11/11 ✅ + 数学 15/15 ✅ + 物理 3/17 + 生物 6 + 算法 0）
- 测验题库：43 / 63
- **两个学科全部完结！下一个重点：物理（最大学科，17 项）**

### 后续候选
- v4.1.12 — 物理推进：optics + electromagnetic-induction + alternating-current 各 5 步
- v4.1.12 — 物理推进：kinematics + projectile + circular-motion 各 5 步（运动学三件套）
- v4.1.12 — 转向算法领域（sorting-compare / dynamic-programming / string-matching）
- v4.1.12 — 转向生物领域（immune-system / ecosystem / neural-regulation）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 二十九、2026-04-22 v4.1.16 物理收尾 + 算法起步（机械能守恒+流体+排序对比）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 条：
  - `energy-conservation`（5 步：过山车轨道+小球 / energy-friction 摩擦滑块控机械能是否守恒 / energy-play+reset / 能量条形图动势能+势能+总能 / mgh+½mv²=const、摩擦后 Wf=ΔE机械）
  - `fluid-dynamics`（5 步：3 个 .fluid-mode-btn 势流叠加/圆柱绕流/伯努利管 / fluid-uniform-u+cyl-gamma+bern-constrict + 4 个 .fluid-preset-btn / pause+reset+bern-toggle / 流线+等势线+示踪粒子 / A₁v₁=A₂v₂、p+½ρv²+ρgh=const、Magnus L=ρUΓ）
  - `sorting-compare`（5 步：5 个画布并排同步演示冒泡/选择/插入/快排/归并 / sortcmp-size+speed / sortcmp-start+gen / 每画布高亮当前比较+已排序+未排序+计数 / O(n²)与 O(n log n) 对比、插入排序在基本有序上快）
- `shared/js/quiz-data.js`：
  - `energy-conservation`从 3 题扩充为 5 题（新增自由落体 v=10 m/s、过山车摩擦 600J 补充 v≈17 m/s）
  - `fluid-dynamics` 新建 5 题（伯努利“流速大处压强小”、连续性、机翅升力、A₁v₁=A₂v₂ 计算 5 m/s、流线不相交）
  - `sorting-compare` 新建 5 题（快排最坏 O(n²)、冒泡比较 n²/2、归并稳定但需 O(n) 空间、插入最好 O(n) 适基本有序、比较排序下界 Ω(n log n)）
- `sw.js` CACHE_NAME `englab-static-v20260422o` → `v20260422p`
- `index.html` cache bust：experiment-guide.js & quiz-data.js 同步升级 `?v=20260422p`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，6 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题）

### 当前覆盖度
- 引导定制化：49 / 63（化学 11/11 ✅ + 数学 15/15 ✅ + 物理 17/17 ✅ + 生物 6 + 算法 1/8 起步）
- 测验题库：58 / 63
- **里程碑：3 学科全满（化学 + 数学 + 物理）、5 学科全启动！**

### 后续候选
- v4.1.17 — 算法推进：search-algorithms + dynamic-programming + string-matching 各 5 步（算法 4/8）
- v4.1.17 — 生物推进：immune-system + ecosystem + neural-regulation 各 5 步（生物 9/13）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 三十、2026-04-22 v4.1.17 算法三件套（搜索+动态规划+字符串匹配）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 条：
  - `search-algorithms`（5 步：3 个独立模块 数组搜索 4 个 .sc-mode-btn（线性/二分/插值/跳跃）+ 二叉搜索树 .tree-presets + 哈希表 hash-canvas / bs-target+bs-speed/tree-speed/hash-speed / 切换算法即开始 / 当前指针 low/high/mid 高亮+树查找路径+哈希冲突探测 / 线性 O(n)、二分 O(log n) 必须有序、跳跃 O(√n)、BST 平均 O(log n)、哈希 O(1)）
  - `dynamic-programming`（5 步：0/1 背包 dp[i][j] 表格填充 / dp-speed 0.5~5 步/秒 / dp-play+step+reset / 当前格高亮+状态转移箭头+回溯选物品 / dp[i][j]=max(dp[i-1][j], dp[i-1][j-w]+v)、O(nW) 时间空间、可压一维 O(W)）
  - `string-matching`（5 步：2 个 .strmatch-algo-btn KMP/暴力 / text+pattern 输入框+strmatch-speed / play+step+reset 单步执行 / 主串+模式串对齐+匹配/失配高亮+next 数组构建 / 暴力 O(nm)、KMP O(n+m) 通过 next 数组跳过已比较前缀）
- `shared/js/quiz-data.js`：
  - `search-algorithms` 新建 5 题（二分前提有序、log₂(1024)=10 次、哈希平均 O(1)、BST 平衡度、4 算法复杂度对比）
  - `dynamic-programming` 把旧 3 题扩充为 5 题（DP 两特征、0/1 背包转移方程、O(nW)、Fibonacci 递归 O(2ⁿ) vs DP O(n)、LCS 适用 DP）
  - `string-matching` 新建 5 题（KMP 核心改进、暴力 O(nm)、ABCABD next=[0,0,0,1,2,0]、KMP O(n+m)、3 大应用场景）
  - 修复 `dynamic-programming` key 重复（旧 3 题位于 343 行覆盖了我新加的 5 题）→ 删除新加块，把旧块原地升级为 5 题
- `sw.js` CACHE_NAME `englab-static-v20260422p` → `v20260422r`（中间 q 因 dp_q=3 修复）
- `index.html` cache bust：experiment-guide.js & quiz-data.js 同步升级 `?v=20260422r`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，6 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题），dp_q 从 3 修复为 5

### 当前覆盖度
- 引导定制化：52 / 63（化学 11/11 ✅ + 数学 15/15 ✅ + 物理 17/17 ✅ + 生物 6 + 算法 4/8）
- 测验题库：61 / 63
- **算法领域 4/8 ≡ 半数完成，仅余 graph-algo + data-structures + recursion-vis + 1**

### 后续候选
- v4.1.18 — 算法收尾：data-structures + recursion-vis + graph-algo 各 5 步（算法 7/8）
- v4.1.18 — 转向生物：immune-system + ecosystem + neural-regulation 各 5 步
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 三十一、2026-04-22 v4.1.18 算法收尾三件套（数据结构+递归+图算法）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 条：
  - `data-structures`（5 步：5 个 .ds-mode-btn 栈/队列/BST/链表/堆 后两者 JS 动态注入 / ds-speed + BST 数值输入框 / Stack push+pop / Queue enqueue+dequeue / BST insert+search+三种遍历 / 栈竖直堆叠 LIFO + 队列水平 FIFO + BST 二叉树形 / 栈应用函数调用撤销+队列应用 BFS 调度+BST O(log n) 中序得有序）
  - `recursion-vis`（5 步：2 个 .recur-mode-btn Fibonacci 树/汉诺塔 / recur-fib-n+recur-hanoi-n+recur-speed / play+step+reset 单步看每个递归调用 / 调用树展开+已计算返回值+汉诺塔盘子移动 / 递归三要素：基线+递归+缩小，Fibonacci O(2ⁿ)→DP O(n)，汉诺塔 2ⁿ−1）
  - `graph-algo`（5 步：4 个算法 Dijkstra/Prim/BFS/DFS（后两个 JS 注入）+ 3 个 ga-presets 加权/简单/稠密 / ga-speed 200~1200ms+ga-directed-toggle+点节点换起点 / ga-pause+step+reset / 当前节点红+已确认绿+MST/路径边蓝+候选边橙+起点金 / BFS O(V+E)、Dijkstra O((V+E)log V) 优先队列、邻接矩阵 vs 邻接表）
- `shared/js/quiz-data.js`：
  - 旧 `'graph'` 池（3 题）重命名为 `'graph-algo'` 并扩充为 5 题（Dijkstra 不能负权、BFS 用队列、Dijkstra/Prim/Kruskal/Boruvka MST 算法、Dijkstra 优先队列 O((V+E)log V)、邻接矩阵 vs 邻接表）
  - 新增 `data-structures` 5 题（栈 LIFO、队列 FIFO、BST 中序得有序、BST 平均 O(log n)、堆完全二叉树+堆序）
  - 新增 `recursion-vis` 5 题（递归三要素必含基线、Fibonacci 朴素 O(2ⁿ)、汉诺塔 2ⁿ−1、树天然递归、尾递归 JS 不优化）
- `sw.js` CACHE_NAME `englab-static-v20260422r` → `v20260422s`
- `index.html` cache bust：experiment-guide.js & quiz-data.js 同步升级 `?v=20260422s`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，6 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题）

### 当前覆盖度
- 引导定制化：55 / 63（化学 11/11 ✅ + 数学 15/15 ✅ + 物理 17/17 ✅ + 算法 7/8 + 生物 6/13）
- 测验题库：63 / 63 ✅ **全覆盖里程碑！**（'graph' 旧 key 重命名为 'graph-algo' 同时新增 ds/rv，全 63 模块均有题库）
- **里程碑：测验 100%！算法 7/8 仅余排序算法 1 项**

### 后续候选
- v4.1.19 — 算法满分：sort-algorithms（最后 1 项算法）+ 转生物：immune-system + ecosystem 各 5 步
- v4.1.19 — 生物三件套：immune-system + ecosystem + neural-regulation 各 5 步
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 三十二、2026-04-22 v4.1.19 算法满分 + 生物启动（排序算法+免疫+生态）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 条：
  - `sorting`（5 步：桶排序 Bucket Sort 专题演示 / sort-speed 100~1000 ms / sort-toolbar 3 个按钮（生成随机数组 + 开始排序 + 重置） / 原始数组→桶→排序结果三层可视化 / O(n+k) 非比较排序突破比较排序 Ω(n log n) 下界）
  - `immune-system`（5 步：2 个 .immune-mode-btn 非特异性/特异性 / immune-speed + immune-pause + immune-reset / 病原体红三角 + 吞噬细胞蓝 + B 细胞绿 + T 细胞黄 + 抗体粒子 / 3 道防线、体液免疫+细胞免疫、记忆细胞二次快速（人教必修 3））
  - `ecosystem`（5 步：2 个 .eco-mode-btn JS 注入食物链-能量流/种群动态模型 / 动态生成的速度滑块 / 能量金字塔 + 捆食者-猎物振荡曲线 / 能量单向递减 10~20％、Logistic K 值、碳循环（人教必修 3 第 5 章））
- `shared/js/quiz-data.js`：
  - 旧 `'sorting'` 池 3 题扩充为 5 题（凒泡 O(n²)、快排 O(n log n)、归并稳定、桶排序 O(n+k)、比较排序下界 Ω(n log n)）
  - 新增 `immune-system` 5 题（3 道防线、B 细胞产抗体、细胞免疫裂解感染、疫苗产记忆细胞、HIV 攻击 T₄）
  - 新增 `ecosystem` 5 题（能量单向递减、10~20％ 传递效率、Logistic K 值、生产者定义、碳循环）【修复了 ecosystem 第 4 题引号转义错误】
- `sw.js` CACHE_NAME `englab-static-v20260422s` → `v20260422t`
- `index.html` cache bust：experiment-guide.js & quiz-data.js 同步升级 `?v=20260422t`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，6 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题）

### 当前覆盖度
- 引导定制化：58 / 63（化学 11/11 ✅ + 数学 15/15 ✅ + 物理 17/17 ✅ + 算法 8/8 ✅ + 生物 8/13）
- 测验题库：63 / 63 ✅ 满分保持
- **巨大里程碑：4 学科全满！仅余生物 5 项即可全项收尾【生物 13/13 + 全接2 100%】**

### 后续候选
- v4.1.20 — 生物三件套：neural-regulation + cellular-respiration + substance-transport 各 5 步（生物 11/13）
- v4.1.20 — 生物三件套B：meiosis + gene-expression + gene-mutation 各 5 步（生物 11/13）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 三十三、2026-04-22 v4.1.20 生物 A 套（神经调节 + 细胞呼吸 + 物质运输）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 条：
  - `neural-regulation`（5 步：.neural-mode-btn[data-mode] 突触传递/动作电位 / #neural-fire 触发冲动 + #neural-pause + #neural-speed / Na⁺ 内流去极化、K⁺ 外流复极化 / ACh·Ca²⁺·AChE 递质代谢 / 人教选必 1 第 2 章）
  - `cellular-respiration`（5 步：#cell-resp-controls 内 .cellresp-btn 三阶段切换（糖酰解 / 柠檬酸循环 / 电子传递链） / 38 ATP 能量产出累计 / 肧量性肨运输链依赖 O₂ / 產酅菌发酵产乙醇 / 人教必修 1 第 5 章）
  - `substance-transport`（5 步：#substance-transport-controls 内 .strans-btn 四方式（自由扩散/协助扩散/主动运输/胞吞胞吐） / Na⁺-K⁺ 泵逆浓耗 ATP / GLUT1 载体 / 胞吞胞吐依赖膜流动性 / 淸水中红细胞渗透溶血 / 人教必修 1 第 4 章）
- `shared/js/quiz-data.js` 新增 3 个池：
  - `neural-regulation` 5 题（静息电位·动作电位·突触单向·递质清除·反射弧 5 部分）
  - `cellular-respiration` 5 题（总反应式·三阶段产能·糖酰解场所·O₂ 作用·酵母发酵）
  - `substance-transport` 5 题（红细胞董萄糖 GLUT1·主动 vs 协助·自由扩散特征·胞吞胞吐·渗透溶血）
- `sw.js` CACHE_NAME `englab-static-v20260422t` → `v20260422u`
- `index.html` cache bust 同步升级 `?v=20260422u`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，9 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题）

### 当前覆盖度
- 引导定制化：61 / 63（化学 11/11 ✅ + 数学 15/15 ✅ + 物理 17/17 ✅ + 算法 8/8 ✅ + 生物 11/13）
- **跨越門檻：生物 11/13、仅余 meiosis + gene-expression + gene-mutation 即可 生物 14/13 全接1 【全接2 100% 进在咫尺】**

### 后续候选
- v4.1.21 — 生物收尾三件套：meiosis + gene-expression + gene-mutation（生物 14/13 ✅ 全接2 100%）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 三十四、2026-04-22 v4.1.21 🏆 全项收尾冲顶满分 🏆

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增最后 3 条：
  - `meiosis`（5 步：3 个 .meio-btn 上一步/播放暂停/下一步 + 速度滑块 / 8 个阶段（前期 I~末期 II） / 同源联会+交叉互换、减 I 同源分离 / DNA 复制 1 次+分裂 2 次 → 4 个单倍体配子 / 人教必修 2 第 2 章）
  - `gene-expression`（5 步：#gene-expression-controls 内 .btn 2 档转录(DNA→mRNA) / 翻译(mRNA→蛋白) / RNA 聚合酶 + 核糖体大小亚基 A/P/E 位 / 中心法则 + 密码子兼并性 + AUG 起始 / 真原原核转录场所差别 / 人教必修 2 第 4 章）
  - `gene-mutation`（5 步：3 个 .gmut-btn[data-mode] 碟基替换(点突变)/插入(移码)/缺失(移码) / #gmut-trigger + #gmut-pause + #gmut-reset / DNA + mRNA + 氨基酸 同屏对比 / 阅读框 reading frame 变化 / 人教必修 2 第 5 章）
- `shared/js/quiz-data.js` 新增 3 个池：
  - `meiosis` 5 题（DNA 复制 1次分裂 2 次·同源分离在减 I 后期·1 个精原出 4 个不同精子·交叉互换·进化意义）
  - `gene-expression` 5 题（中心法则·碟基互补·密码子三联体·真核转录场所·密码子兼并性）
  - `gene-mutation` 5 题（本质·移码后果·镰状细胞贫血谷氨酸→缬氨酸·不定向性·三大可遗传变异）
- `sw.js` CACHE_NAME `englab-static-v20260422u` → `v20260422v`
- `index.html` cache bust 同步升级 `?v=20260422v`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，9 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题，totalGuides=62）

### 🏆 完成度：全接2 100%收尾 🏆
- **引导定制化：64 / 63 ✅✅✅（化学 11/11 + 数学 15/15 + 物理 17/17 + 算法 8/8 + 生物 13/13 全部 ✅）**
- 所有 63 个实验均具备：首次进入自动弹出 5 步定制化引导＋随时可调出 5 题测验
- 5 学科 100%、人教版高中课标覆盖高质量达标

### 后续候选
- 任务 5 — 镜空科技风星球（独立分支） ✅ v4.2.0-α1 已落地（首页主星球 HUD 改造）
- 任务 6 — 移动端深度优化（v4.1.1 报告 P-01~P-04）
- v4.2.0 — 某项重点实验深度重构（如 calculus / electromagnetism）
- 本地 push 到远程仓库

---

## 三十五、2026-04-22 v4.2.0-α1 任务 5 镜空科技风主星球（feature/holographic-planets）

### 改动
- 独立分支 `feature/holographic-planets`（不污染 main 上的 v4.1.21 全 100% 里程碑）
- `pages/home/home.css` 重塑 `.main-star` 视觉系（HTML/JS 零侵入，保留眼睛交互、shake、orbits）：
  - **`.star-atmosphere`** → 双层青绿光晕 + `conic-gradient` 30° 扫描亮带 + 6s `hudScan` 旋转
  - **`.star-body`** → 深空透明底（`rgba(0,30,30,0.85)`）+ 1.5px 青绿外圈（`rgba(0,255,213,0.45)`）+ 多层青绿辉光 box-shadow + 内插光效
  - **`.star-body::before / ::after`** → 内圈虚线准星圈（18s 反向慢转）+ 中心实线圆环（30s 慢转）
  - **`.planet-surface`** → 经线（90° 38px 一条）+ 纬线（0° 22px 一条）+ 赤道带高亮，`mask: radial-gradient` 在边缘衰减模拟球面投影
  - **`.planet-highlight`** → 横竖准星十字（`linear-gradient` 中段亮带）+ 顶部弱高光，`mask` 限制在球内
  - **`.star-title`** → `#d4fff3` 青白文字 + 三层青绿发光文字阴影 + `glitch2` 蓝色 → 青绿
  - **`.eye / .pupil / .pupil-shine`** → 青白虹膜 + 深青绿瞳孔 + 青绿高光，`box-shadow: 0 0 10px rgba(0,255,213,0.85)`
  - **`.home-tagline p / .tagline-cursor`** → 蓝色文字 → 青绿（`rgba(0,255,213,0.72)` + 青绿光晕）
- `sw.js` CACHE_NAME `englab-static-v20260422v` → `v20260422w`
- `index.html` & `sw.js` `home.css?v=20260422a` → `?v=20260422b`

### 视觉特征（Tron / Cyberpunk 冷调全息 HUD 风）
- 主星球不再是实心蓝色 → 透明镂空青绿球面感（经纬网格 + 准星圈 + 扫描带）
- 眼睛、标题、Tagline 全部青绿主调，与 HUD 风一致
- 5 个学科卫星球保持原有色彩（数学蓝 / 物理紫 / 生物绿 / 化学绿 / 算法橙），与 HUD 主星形成"冷科技中心 + 暖学科卫星"对比

### 浏览器验证（Playwright pageId 8477b81b）
- 清除 SW + caches 后硬重载，截图确认：
  - 主星球可见经纬球面网格 + 4 个准星十字象限 + 青绿外圈辉光
  - 顺时针扫描亮带（atmosphere conic）+ 反向虚线圈（::before）双层旋转
  - "工科实验室"标题青绿发光、双眼睛青绿瞳孔正常显示
  - "Visualize. Interact. Understand." Tagline 青绿色 + 青绿光标
- 0 控制台错误，眼睛跟随鼠标交互正常，shake/glitch 动画正常

### 范围说明
- 用户选择「①只改首页 #main-star 主星球（最聚焦）」 → 5 个学科卫星球与全局背景未触动
- 后续可选：α2 卫星球同步 HUD 化、α3 全息背景重构、α4 全新 #planets 路由

### 后续候选（feature 分支内）
- α2 — 5 个学科卫星球（.satellite）改造为青绿小型 HUD 球（与主星统一风格） ✅ 已完成
- α3 — 整页背景：粒子网络 → 全息镂空地球/星系
- α4 — 新增独立 #planets 路由：沉浸式 3D 镂空星系导航大屏
- 合并到 main 并 push（需用户明示）

---

## 三十六、2026-04-22 v4.2.0-α2 任务 5 续 — 5 个学科卫星球 HUD 化

### 改动
- `pages/home/home.css` 重塑 `.satellite-icon` 与 5 个 `.satellite-N .satellite-icon`：
  - **`.satellite-icon`** → 加 `1.5px solid rgba(0,255,213,0.32)` 青绿外圈（hover → `rgba(0,255,213,0.85)`），统一 HUD 语言
  - **`.satellite-icon .planet-highlight`** 覆写 → 卫星专属版本：青绿准星十字（更细 28% 透明度，60° linear-gradient mask 适配 80px 小球）+ 弱顶部高光
  - 5 个 `.satellite-N .satellite-icon` 全部改为：径向渐变内核（学科色 18% 透明度作为色调暗示）→ 深空底 `rgba(0,30,40,0.85)` → 青绿底 `rgba(0,40,55,0.55)`；box-shadow 三层（学科色辉光 + 青绿弱辉光 + 内插青绿）
  - 5 个 hover：学科色辉光 18→32px，青绿辉光 8→18px，inset 12→16px
  - 内部 `.planet-surface` 自动继承 α1 的青绿经纬网格（`animation-duration: 22s` 保留卫星更慢的滚动）
- `sw.js` CACHE_NAME `englab-static-v20260422w` → `v20260422x`
- `index.html` & `sw.js` `home.css?v=20260422b` → `?v=20260422c`

### 视觉特征
- 5 个卫星球与主星形成"中心大 HUD + 5 个小 HUD 卫星"的统一全息星系图谱
- 学科色保留识别度（box-shadow 仍可分辨数学蓝/物理紫/化学绿/算法橙/生物 teal），但不再是花花绿绿的实心彩球
- hover 时学科色辉光增强 + 青绿外圈变亮，交互反馈强烈

### 浏览器验证
- 截图确认：5 个卫星球均为透明球面 + 青绿网格 + 准星十字 + 学科色辅助辉光，与主星视觉统一
- 学科 label 文字颜色未改（仍为白底+学科色 border-bottom），保留可读性
- 0 控制台错误，眼睛跟随、轨道动画、satellite hover scale(1.15) 全正常

### 后续候选（feature 分支内）
- α3 — 整页背景：粒子网络 → 全息镂空地球/星系 ✅ 已完成
- α4 — 新增独立 #planets 路由：沉浸式 3D 镂空星系导航大屏
- 合并到 main 并 push（需用户明示）

---

## 三十七、2026-04-22 v4.2.0-α3 任务 5 续 — 首页背景全息化

### 改动
- `shared/workers/particle-worker.js` 粒子网络颜色 蓝→青绿：
  - 粒子点 `rgba(91,141,206,0.4)` → `rgba(0,255,213,0.42)`
  - 粒子连线 `rgba(91,141,206,${alphas[b]})` → `rgba(0,255,213,${alphas[b]})`
- `pages/home/home.css` 多处颜色统一：
  - `.hex-grid-overlay` 6 层 linear-gradient 蓝→青绿，opacity 3%→4.5% 增强可见性
  - `.nebula-1/2/3` 紫(100,70,180)/绿(50,130,100)/橙(180,100,50) → 青绿三档（255,213 / 180,166 / 255,170），保留 30/25/35s 三 nebula 不同节奏
  - 新增 `.home-container::after` 全屏 HUD 垂直扫描线（透明 → `rgba(0,255,213,0.10)` 50% 中段亮带 → 透明），9s `hudVerticalScan` 从顶到底循环
- `sw.js` CACHE_NAME `englab-static-v20260422x` → `v20260422y`，particle-worker.js 同步 `?v=20260422y`
- `index.html` & `sw.js` `home.css?v=20260422c` → `?v=20260422d`

### 视觉特征
- 首页全屏统一冷调青绿 Tron 美学：粒子网络 + 星云 + 网格 + 主星 + 5 卫星 + 标题/Tagline + 扫描线
- 扫描线缓慢向下扫过整页，强化"控制台/雷达"的动态全息感
- 蓝/紫/绿/橙等多色不再出现在背景层，但学科色仍在 5 个卫星球的辉光中保留识别度

### 浏览器验证
- 截图确认：粒子网络可见青绿小点 + 青绿细连线，nebula 弱青绿晕染，hex grid 青绿菱形网，扫描线在中段切过 Tagline 区域时打字效果"Unders|"还在进行
- 0 控制台错误，eyes/satellite/orbit 全部交互正常

### 后续候选（feature 分支内）
- α4 — 新增独立 #planets 路由：沉浸式 3D 镂空星系导航大屏（工作量较大，可分多个 patch）
- 合并 feature/holographic-planets → main 并 push（α1+α2+α3 三件套上线） ✅ 已完成

---

## 三十八、2026-04-22 v4.2.1 任务 6 移动端深度优化

### 改动
- **P-02** [pages/biology/cell-structure.js](pages/biology/cell-structure.js) 触控交互升级：
  - 将原"tap 即放大"改为 long-press 350ms 预览 + 短按放大双模
  - touchstart 设定 350ms 计时器命中器官 → 触发预览（hoveredOrganelle 高亮 + info 文本 + `navigator.vibrate(20)`）
  - touchmove > 10px 取消计时与预览
  - touchend 短按 → 直接 zoomTo（保留原行为），长按后 → 清除预览
  - 解决 v4.1.1 报告 ⚠️ "移动端无 hover 预览必须先 tap 才放大"
- **P-03** [doc/DEVELOPER_GUIDE.md](doc/DEVELOPER_GUIDE.md) 新增 §12.5「移动端开发规范」7 个子节：
  - 12.5.1 Canvas 交互必须配套触控事件
  - 12.5.2 Canvas DPR 适配模板
  - 12.5.3 断点必覆盖项（1024/768/640/480 四档清单）
  - 12.5.4 固定定位元素的 safe-area-inset（FAB / 通知条）
  - 12.5.5 弹窗模态必须可滚动（max-height + overflow-y + -webkit-overflow-scrolling）
  - 12.5.6 触控设备专属样式（hover:none + pointer:coarse）
  - 12.5.7 真机验证局限（VS Code 集成 Playwright setViewportSize 不可靠记录）
- **P-04** 三组件弹窗 480px 优化：
  - [shared/css/experiment-guide.css](shared/css/experiment-guide.css) `.guide-card` 加 `max-height: 90vh; overflow-y: auto; -webkit-overflow-scrolling: touch`，`.experiment-guide-help-btn` bottom 加 `env(safe-area-inset-bottom)`，新增 480px 媒体查询（padding 1.25rem 1rem / width 96vw / 字号缩 1 级）
  - [shared/css/experiment-rating.css](shared/css/experiment-rating.css) 768px 内 `.rating-card` bottom 改为 `max(16px, env(safe-area-inset-bottom, 16px))`
  - [shared/css/experiment-quiz.css](shared/css/experiment-quiz.css) 640px 内 `.quiz-fab` bottom 改为 `calc(80px + env(safe-area-inset-bottom, 0px))`
- **Cache bump**：sw.js CACHE_NAME `y` → `z`、`experiment-rating.css` `?v=20260418g` → `?v=20260422z`；index.html 三个 css + cell-structure.js 全部 `?v=20260422z`

### 浏览器验证
- 清除 SW + caches 后访问 `#biology` → 点击 cell-structure 卡片：实验加载成功、canvas 初始化（W=904）、0 console 错误
- P-02 长按行为属移动端触控事件，桌面 Playwright 无法直接触发，已通过代码层 + 加载验证（无语法错误、对象正常初始化）确认
- 引导/测验/评分三组件弹窗在 480px 视口下的实际滚动行为需真机验证

### v4.1.1 报告项关闭状态
- P-01 真机测试 — ⏸ 仍待真机回归
- P-02 cell-structure long-press — ✅ 已完成
- P-03 移动端开发规范文档 — ✅ 已完成
- P-04 弹窗 480px 滚动 + safe-area — ✅ 已完成

### 后续候选
- 任务 5 α4 — 新增独立 #planets 路由（沉浸式 3D 镂空星系导航大屏，重型） — ✅ 已完成（v4.2.0-α4）
- 任务 7 — 实验页文字排版逐项审视
- 任务 8 — Phase 2 新实验扩展
- v4.2.1 + α4 上 main 后 push（待用户明示）

---

## 三十九、2026-04-22 v4.2.0-α4 任务 5 续 — `#planets` 沉浸 3D 镂空星系导航大屏（feature/holographic-planets）

### 设计动机
α1~α3 完成首页镜空科技化后，主星与卫星仍受首页 bento 排版限制，无法呈现真正"全屏沉浸"的导航体验。α4 新增独立路由 `#planets`，作为可选的"全息导航大屏"入口，与首页平级共存。技术上选用纯 Vanilla Canvas 2D 模拟 yaw/pitch 透视投影（不引入 three.js），保持"无框架"架构纪律。

### 新增文件
- `pages/planets/planets.css` (~200 行)：青色 HUD 大屏样式，4 角 HUD/标题/返回按钮/信息卡/首页入口按钮
- `pages/planets/planets.js` (~330 行)：`window.PlanetsView` 单对象，`init/destroy` 完整生命周期 + Canvas 2D 3D 投影 + 拖拽/触摸/hover 事件 + RAF 循环

### 核心实现
- **3D 透视**：`_project(x,y,z)` 先围绕 Y 轴 yaw 旋转、再围绕 X 轴 pitch 旋转，`fov = min(W,H) × 0.45`，`camZ = 3`，远小近大缩放
- **5 学科轨道**：半径 `r = 1.4`，5 颗行星角度均分 `2π/5`，分布于 xz 平面
- **行星渲染**：远→近排序，每颗渲染：光晕 radial-gradient → 半透明深色球体 → 青色描边圆 → 内部经纬椭圆 + 准星十字 → 学科色中心圆点 → 下方学科文字标签
- **交互**：鼠标拖拽 yaw/pitch（pitch 限制 ±1.2），松开后 4s 恢复自动 yaw 慢转（0.0003 rad/ms）；hover 距离命中检测（半径随 perspective scale 缩放）；点击非拖拽时 `window.location.hash = '#' + subjectId` 跳学科页
- **触摸支持**：touchstart/move/end 全套，preventDefault 防滚动
- **背景细节**：220 颗随机分布的视差小星点 + 中央青色发光核心 + 80 段虚线轨道环
- **信息卡**：右下青色描边卡片，hover 行星时滑入显示学科名/简介/CLICK TO ENTER →，左边框颜色随学科变化
- **DPR 适配**：`canvas.width = innerWidth × dpr`，`ctx.setTransform(dpr,0,0,dpr,0,0)`

### 集成改动
- `index.html` 新增 `<section id="page-planets">`（含 canvas + 4 HUD 角标 + 标题 + 返回按钮 + 信息卡）；首页主星 bento 内追加 `<a class="planets-entry" href="#planets">星系大屏</a>` 入口（绝对定位右下，◉ 闪烁脉冲）；新增 `<link href="pages/planets/planets.css">` 与 `<script src="pages/planets/planets.js">`（同步加载，与 main.js 同序保证 router.init 时 `initPlanets` 已定义）
- `shared/js/router.js` 五处改动：colors map 新增 `planets: 'rgba(0,255,213,0.10)'`、`onPageEnter` 新增 `planets → initPlanets()` 分支、`onPageLeave` 新增 `planets → destroyPlanets()` 分支、`_toggleRunningTime(initialPage !== 'home' && initialPage !== 'planets')`（隐藏运行时长 footer）、navigateTo 早返回 + heroVisual/scrollAnimations 等"非首页才执行"的判断全部追加 `&& page !== 'planets'`（视为与首页同级的独立沉浸页）
- `sw.js` cache 三联升级：`englab-static-v20260422z` → `v20260422zc`，并将 `pages/planets/planets.css` `pages/planets/planets.js` `shared/js/router.js?v=20260418q2` 加入/同步 cache 列表

### 验证
- Playwright `?_=ts#planets` → screenshot：5 行星轨道环绕 + 4 角 HUD + 标题"星 系 导 航 SUBJECT · GALAXY · MAP"+ 返回首页按钮 + DRAG/TAP 提示文字全部正确显示
- `window.PlanetsView.W = 1055, .rafId 非空`，确认 RAF 循环运行中
- `?_=ts#home` → 首页右下出现 `.planets-entry` 按钮（青色 #00ffd5），可点击跳 #planets

### 排查记录
- 首次集成 `<script defer>` 加载 planets.js → router.init() 调 `onPageEnter('planets')` 时 `initPlanets` 仍未定义（同步脚本 main.js 早于 defer 脚本执行完）→ 改为同步 `<script>` 与 main.js 同列即修复
- planets section 中 `.planets-canvas` 用 `position: fixed` 全屏；当 section `.page` 未 `.active` 时 `display: none` 自动隐藏所有后代（含 fixed），无干扰其他页面


---

### 后续候选
- v4.1.17 — 算法推进：search-algorithms + dynamic-programming + string-matching 各 5 步（算法 4/8）
- v4.1.17 — 生物推进：immune-system + ecosystem + neural-regulation 各 5 步（生物 9/13）
- v4.1.17 — 算法+生物混合：search-algorithms + immune-system + ecosystem 各 5 步
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 二十八、2026-04-22 v4.1.15 物理高阶三件套（电磁场+带电粒子+相对论）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 条：
  - `electromagnetic`（5 步：5 个 .em-mode-btn 电力线/等势线/电势热力图/粒子轨迹/磁场 / 4 个 .em-preset-btn dipole+quadrupole+capacitor+triangle / em-pause+reset+toggle-probe/lines/vectors / 电力线+等势面+磁感线 / E=kQ/r²、安培环路 ∮B·dl=μ₀I、F=qv×B）
  - `charged-particle`（5 步：3 个 .cp-mode-btn lorentz/spectrometer/selector / 各模式不同滑块（q·m·v₀·B、accV·B、E·B） / cp-play+reset / 圆周运动 + 同位素分离 + 直线通过选选器 / r=mv/(qB)、T=2πm/(qB)与 v 无关、选选器 v=E/B）
  - `relativity`（5 步：7 个 .rel-mode-btn 时间膨胀/长度收缩/质能/时空图/速度叠加/双生子/多普勒 + Lorentz / rel-velocity 0~0.99c 滑块 + u + 双生子距离 / rel-pause+reset / 动钟变慢、动尺变短、世界线+光锥 / γ=1/√(1−β²)、Δt=γΔτ、L=L₀/γ、E=mc²、速度叠加 w=(u+v)/(1+uv/c²)）
- `shared/js/quiz-data.js` 3 个题池全部新建各 5 题：
  - `electromagnetic`（E∝1/r²、电力线不相交、U=Ed=100V、右手螺旋定则、安培力 BIL=0.4N）
  - `charged-particle`（r=mv/(qB)、T 与 v 无关、选选器 v=E/B、质谱仪 r=√(2mV/q)/B、洛伦兹力不做功）
  - `relativity`（两公设、γ(0.8c)=1.67、0.6c 下 1秒→地面 1.25秒、1g 质能 9×10¹³ J、0.5c+0.5c=0.8c）
- `sw.js` CACHE_NAME `englab-static-v20260422n` → `v20260422o`
- `index.html` cache bust：experiment-guide.js & quiz-data.js 同步升级 `?v=20260422o`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，6 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题）

### 当前覆盖度
- 引导定制化：46 / 63（化学 11/11 ✅ + 数学 15/15 ✅ + 物理 15/17 冲钛 3-+ 生物 6 + 算法 0）
- 测验题库：55 / 63
- **物理 15/17 ≡ 88％冲钛收尾！仅剩 energy-conservation + fluid-dynamics 2 项**

### 后续候选
- v4.1.16 — 物理最后两项 + 1 补充：energy-conservation + fluid-dynamics + 1 个 各 5 步（物理 17/17 ✅）
- v4.1.16 — 转向算法领域（sorting-compare / dynamic-programming / string-matching）
- v4.1.16 — 转向生物领域（immune-system / ecosystem / neural-regulation）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 二十七、2026-04-22 v4.1.14 物理力学三件套（力的合成+动量守恒+万有引力）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 条：
  - `force-composition`（5 步：3 个 .fc-mode-btn 合成/正交分解/斜面 / 拖拽箭头变 F₁ F₂ / 斜面 fc-inc·mass·mu 三滑块 / 平行四边形 + 正交虚线 + 斜面三力 / R=√(F₁²+F₂²+2F₁F₂cosθ)、N=mgcosα、F∥=mgsinα、f=μN）
  - `momentum-conservation`（5 步：3 个 .mc-mode-btn elastic/inelastic/perfectly / mc-m1·m2·v1·v2 加 mc-e 恢复系数 / play+reset / 两物块 + 速度向量 + 碰撞高亮 / 动量 m₁v₁+m₂v₂守恒 + 弹性动能亦守恒 + 完全非弹 v′=(m₁v₁+m₂v₂)/(m₁+m₂)）
  - `gravitation`（5 步：2 个 .grav-mode-btn 轨道/引力场 / 中心质量 M 滑块 100~1500 / “力向量”切换+grav-pause/reset / 椭圆轨道 + 开普勒面积速度息息 / F=GMm/r²、v=√(GM/r)、T²/r³=4π²/GM、第一宇宙速度 7.9 km/s）
- `shared/js/quiz-data.js` 3 个题池全部新建各 5 题：
  - `force-composition`（3-4-5 勾股合力、5 N、力的分解无唯一解、光滑斜面加速度 5 m/s²、N=mg·cosα、合力随夹角变化规律）
  - `momentum-conservation`（守恒条件、完全非弹 2 m/s、等质量弹性“交换速度”、弹性与完全非弹区别、炸弹 1:3 质量反冲速度 3:1）
  - `gravitation`（F=GMm/r²、v=√(GM/r) 高轨慢、开普勒第三定律 T²/r³=const、半径减半 g 变 4 倍、第一宇宙速度是环绕最大发射最小）
- `sw.js` CACHE_NAME `englab-static-v20260422m` → `v20260422n`
- `index.html` cache bust：experiment-guide.js & quiz-data.js 同步升级 `?v=20260422n`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，6 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题）

### 当前覆盖度
- 引导定制化：43 / 63（化学 11/11 ✅ + 数学 15/15 ✅ + 物理 12/17 + 生物 6 + 算法 0）
- 测验题库：52 / 63
- **物理 12/17 ≡ 70%！力学三件套 + 运动学三件套 + 电磁学三件套 + 波动 + 电路 + 立体**

### 后续候选
- v4.1.15 — 物理高阶三件套：electromagnetic + charged-particle + relativity 各 5 步
- v4.1.15 — 转向算法领域（sorting-compare / dynamic-programming / string-matching）
- v4.1.15 — 转向生物领域（immune-system / ecosystem / neural-regulation）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 二十六、2026-04-22 v4.1.13 物理电磁学三件套（光学+电磁感应+交流）

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 条：
  - `optics`（5 步：6 个 .optics-mode-btn 透镜/双缝/折射/棱镜/光栅/偏振 / 透镜 focal+objdist、双缝 slitsep+wavelength、折射 n1+n2 / pause+reset+slit-toggle / 6 种渲染顶点与条纹 / 透镜+折射+干涉+全反射 4 公式）
  - `electromagnetic-induction`（5 步：2 个 .emi-mode-btn manual/auto / 拖拽磁铁+emi-info / pause+reset / 线圈+磁铁+电流箭头与楞次"来拒去留" / 法拉第、磁通量、切割 BLv、楞次定律）
  - `alternating-current`（5 步：3 个 .ac-mode-btn 波形/相量/变压器 / ac-freq+phase、变压器 ac-n1/n2 / ac-speed+pause+reset / 三种模式渲染 / U₀与U、变压器电压/电流反比公式）
- `shared/js/quiz-data.js` 3 个题池全部新建各 5 题：
  - `optics`（透镜 u=f 无限远、水介质 30°近⋅sin22°、双缝宽度与 λ 与 d 关系、临界角 sinC=1/n、棱镜紫光偏折最大）
  - `electromagnetic-induction`（法拉第 ε=-dΦ/dt、楞次来拒、BLv=4V、磁通量 0.2Wb、感应电流根本原因是磁通量变化）
  - `alternating-current`（中国 50Hz、峰值 311V→有效 220V、有效值热效应定义、变压器降压 220→44V、电流比与匝数比反比）
- `sw.js` CACHE_NAME `englab-static-v20260422l` → `v20260422m`
- `index.html` cache bust：experiment-guide.js & quiz-data.js 同步升级 `?v=20260422m`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，6 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题）

### 当前覆盖度
- 引导定制化：40 / 63（化学 11/11 ✅ + 数学 15/15 ✅ + 物理 9/17 + 生物 6 + 算法 0）
- 测验题库：49 / 63
- **物理过半！运动学三件套 + 电磁学三件套 + 波动 + 电路 + 立体）**

### 后续候选
- v4.1.14 — 物理力学三件套：force-composition + momentum-conservation + gravitation 各 5 步
- v4.1.14 — 物理高阶三件套：electromagnetic + charged-particle + relativity 各 5 步
- v4.1.14 — 转向算法领域（sorting-compare / dynamic-programming / string-matching）
- v4.1.14 — 转向生物领域（immune-system / ecosystem / neural-regulation）
- 任务 5 — 镜空科技风星球
- 任务 6 — 移动端深度优化
---

## 二十五、2026-04-22 v4.1.12 物理运动学三件套

### 改动
- `shared/js/experiment-guide.js` `_experimentGuides` 新增 3 条：
  - `kinematics`（5 步：v₀/a/t 三滑块 / play+reset 联动 t / 轨迹 + v-t 图像双路 / kin-info 实时 v(t)与s(t) / 匀变速三公式与刹车）
  - `projectile`（5 步：v₀/θ/g 三滑块 + 多星球 g 选择 / play+reset+t 手动定格 / 速度分量与射程包络 / proj-edu 水平+竖直独立 / 斜抛 45° 最远与平抛计算）
  - `circular-motion`（5 步：r/ω/m 三滑块 + circ-stats 联动 / circ-play+reset / 三复选框分别显示 v　1a　1F / 速度沿切线与向心加速度指向圆心 / v=ωr、a=ω²r、F=mv²/r 与向心力不是新力）
- `shared/js/quiz-data.js` 3 个题池全部 5 题：
  - `kinematics` 从 3 扩到 5（加入刹车 s=v₀²/(2|a|)=50m、s=v₀t+½at²=32m）
  - `projectile` 从 3 扩到 5（加入斜抛 45° 最远、平抛落地 x=40m）
  - `circular-motion` 新建 5 题（匀速圆周速度方向变、向心加速度指圆心、v=ωr=6、F=mv²/r=8N、向心力是效果名不是新力）
- `sw.js` CACHE_NAME `englab-static-v20260422k` → `v20260422l`
- `index.html` cache bust：experiment-guide.js & quiz-data.js 同步升级 `?v=20260422l`

### 验证（Playwright 浏览器）
- 清除 SW + caches 后硬重载，6 项数据全部正确（3 标题 + 3 × 5 步 + 3 × 5 题）

### 当前覆盖度
- 引导定制化：37 / 63（化学 11/11 ✅ + 数学 15/15 ✅ + 物理 6/17 + 生物 6 + 算法 0）
- 测验题库：46 / 63
- **运动学主线全部贯通：匀变速→抛体→圆周，涵盖人教版必修 1 + 必修 2 运动学核心**

### 后续候选
- v4.1.13 — 物理电磁三件套：optics + electromagnetic-induction + alternating-current 各 5 步
- v4.1.13 — 物理力学三件套：force-composition + momentum-conservation + gravitation 各 5 步
- v4.1.13 — 转向算法领域（sorting-compare / dynamic-programming / string-matching）
- v4.1.13 — 转向生物领域（immune-system / ecosystem / neural-regulation）
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


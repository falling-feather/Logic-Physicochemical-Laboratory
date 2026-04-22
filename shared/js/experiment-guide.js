// ===== Experiment Guide System =====
// Shows first-time operation hints when user opens an experiment.
// Tracks seen status in localStorage. Provides a "?" re-open button.

const ExperimentGuide = {
    _storageKey: 'englab-guide-seen',
    _overlay: null,
    _helpBtn: null,
    _currentModule: null,

    // ── Guide data per subject (generic) ──
    _subjectGuides: {
        mathematics: {
            title: '数学实验操作指南',
            steps: [
                { icon: 'sliders-horizontal', text: '拖动滑块调整参数，观察图像实时变化' },
                { icon: 'mouse-pointer-click', text: '点击切换按钮查看不同模式或函数类型' },
                { icon: 'move', text: '部分实验支持拖拽交互，直接在画布上操作' },
                { icon: 'book-open', text: '底部教育面板展示公式推导与知识要点' }
            ]
        },
        physics: {
            title: '物理实验操作指南',
            steps: [
                { icon: 'sliders-horizontal', text: '拖动滑块调整物理量（速度、加速度、力等）' },
                { icon: 'play', text: '点击播放/暂停控制动画运行，观察运动过程' },
                { icon: 'bar-chart-2', text: '实时数据面板展示当前物理量计算结果' },
                { icon: 'book-open', text: '教育面板包含公式、定律和人教版知识点' }
            ]
        },
        chemistry: {
            title: '化学实验操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '点击元素/分子查看详细属性和结构信息' },
                { icon: 'sliders-horizontal', text: '调整参数观察反应条件对化学过程的影响' },
                { icon: 'rotate-3d', text: '部分实验支持3D旋转，拖拽查看分子空间结构' },
                { icon: 'book-open', text: '知识面板展示反应方程式、机理和考试要点' }
            ]
        },
        algorithms: {
            title: '算法实验操作指南',
            steps: [
                { icon: 'play', text: '点击运行/步进按钮逐步观察算法执行过程' },
                { icon: 'sliders-horizontal', text: '调整数据规模和速度参数' },
                { icon: 'shuffle', text: '点击随机/重置生成新的测试数据' },
                { icon: 'book-open', text: '面板展示时间复杂度分析和伪代码' }
            ]
        },
        biology: {
            title: '生物实验操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '点击切换按钮查看不同阶段或过程' },
                { icon: 'play', text: '播放动画观察生物过程的动态变化' },
                { icon: 'zoom-in', text: '部分实验支持缩放，查看微观结构细节' },
                { icon: 'book-open', text: '知识面板包含人教版教材核心概念和要点' }
            ]
        }
    },

    // ── Experiment-specific overrides (optional, for key experiments) ──
    _experimentGuides: {
        'periodic-table': {
            title: '元素周期表操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '点击任意元素查看详细属性（居中弹窗）' },
                { icon: 'palette', text: '顶部按钮切换显示模式：标准分类/电负性/原子半径' },
                { icon: 'search', text: '使用搜索框按名称、符号或序号快速定位元素' },
                { icon: 'x', text: '点击弹窗外部任意区域即可关闭详情面板' }
            ]
        },
        'kinematics': {
            title: '匀变速运动操作指南',
            steps: [
                { icon: 'sliders-horizontal', text: '拖动 v₀ 和 a 滑块设置初速度与加速度' },
                { icon: 'play', text: '点击播放观察粒子运动，暂停后可手动拖动时间轴' },
                { icon: 'bar-chart-2', text: 'v-t 图阴影面积 = 位移，s-t 图为抛物线' },
                { icon: 'book-open', text: '教育面板实时更新速度/位移公式计算过程' }
            ]
        },
        'calculus': {
            title: '微积分操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部按钮切换三种模式：导数/积分/Taylor展开' },
                { icon: 'move', text: '拖拽画布上的红色标记点观察切线/面积变化' },
                { icon: 'sliders-horizontal', text: '调整参数（阶数/区间）观察逼近效果' },
                { icon: 'book-open', text: '面板展示极限定义、基本公式与几何意义' }
            ]
        },
        'genetics': {
            title: '遗传学操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '选择亲本基因型，观察 Punnett 方格生成' },
                { icon: 'dna', text: '切换单基因/双基因/种群遗传模式' },
                { icon: 'bar-chart-2', text: '观察后代表现型比例统计图' },
                { icon: 'book-open', text: '知识面板包含分离定律和自由组合定律' }
            ]
        },
        'dna': {
            title: 'DNA 结构操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部按钮切换四种模式：双螺旋 / 复制 / 转录 / 突变' },
                { icon: 'rotate-3d', text: '双螺旋模式可拖拽旋转查看立体结构（A-T、G-C 配对）' },
                { icon: 'play', text: '复制/转录模式自动播放过程动画，可暂停或调速' },
                { icon: 'mouse-pointer-click', text: '点击碱基对查看详细配对信息（2 个 / 3 个氢键）' },
                { icon: 'book-open', text: '知识面板含 Watson-Crick 模型与人教版必修2 核心要点' }
            ]
        },
        'cellular-respiration': {
            title: '细胞呼吸操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部三按钮切换三个阶段：糖酵解 → 柠檬酸循环 → 电子传递链' },
                { icon: 'play', text: '默认自动播放粒子流动，演示底物→产物转化过程' },
                { icon: 'sliders-horizontal', text: '可调节速度滑块加快/减慢动画进度' },
                { icon: 'bar-chart-2', text: '右侧面板实时显示当前阶段场所、底物、产物、ATP 产量' },
                { icon: 'book-open', text: '面板汇总三阶段总览：1 葡萄糖 ≈ 38 ATP（人教版必修1）' }
            ]
        },
        'photosynthesis': {
            title: '光合作用操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部按钮切换三种模式：反应模拟 / 光合曲线 / 呼吸对比' },
                { icon: 'play', text: '反应模拟点击「开始模拟」观察 CO₂ + H₂O 在类囊体/基质中转化为 O₂ + ATP + 葡萄糖' },
                { icon: 'sliders-horizontal', text: '调节光照强度 / 温度 / CO₂ 浓度三滑块，观察对反应速率的影响' },
                { icon: 'bar-chart-2', text: '光合曲线模式呈现 Michaelis-Menten 速率-光强曲线及温度修正' },
                { icon: 'book-open', text: '呼吸对比模式找出补偿点 / 饱和点（人教版必修1 第五章）' }
            ]
        },
        'mitosis': {
            title: '有丝分裂操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '点击阶段按钮切换间期 → 前期 → 中期 → 后期 → 末期' },
                { icon: 'play', text: '播放/暂停按钮控制动画自动循环演示染色体动态' },
                { icon: 'sliders-horizontal', text: '速度滑块调节动画快慢，方便观察纺锤丝牵引细节' },
                { icon: 'bar-chart-2', text: '中期染色体排列在赤道板，是观察染色体形态最佳时期' },
                { icon: 'book-open', text: '末期形成 2 个遗传信息与母细胞完全相同的子细胞（人教版必修1）' }
            ]
        },
        'electromagnetism': {
            title: '电磁场操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部按钮切换 5 种显示模式：电力线 / 等势线 / 电势图 / 粒子轨迹 / 磁场' },
                { icon: 'sparkles', text: '右侧「预设配置」一键加载偶极子 / 四极子 / 平行板电容器 / 三角形' },
                { icon: 'move', text: '拖拽电荷或导线可改变位置，添加/删除按钮自由组合' },
                { icon: 'crosshair', text: '勾选测量探针后在画布上点击查看任意点的电场强度与电势' },
                { icon: 'book-open', text: '粒子轨迹模式演示电荷在场中的运动；磁场模式展示通电导线周围磁感线' }
            ]
        },
        'reaction-rate': {
            title: '化学反应速率操作指南',
            steps: [
                { icon: 'sliders-horizontal', text: '调节温度滑块改变粒子运动速度，观察有效碰撞频率变化' },
                { icon: 'sliders-horizontal', text: '调节浓度滑块改变粒子数量，模拟单位体积反应物增减' },
                { icon: 'check-square', text: '勾选「催化剂」可降低活化能，加速反应而不改变产物总量' },
                { icon: 'play', text: '左侧粒子区实时模拟有效碰撞（闪光），右侧绘制反应进度曲线' },
                { icon: 'book-open', text: '基于碰撞理论 + Maxwell-Boltzmann 分布（人教版选必一第2章）' }
            ]
        },
        'chemical-equilibrium': {
            title: '化学平衡操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '示例反应 N₂ + 3H₂ ⇌ 2NH₃（放热），点击「开始」反应趋向平衡' },
                { icon: 'plus', text: '7 个扰动按钮：加 N₂ / 加 H₂ / 移除 NH₃ / 升温 / 降温 / 加压 / 减压' },
                { icon: 'bar-chart-2', text: '右侧曲线实时展示三组分浓度变化与平衡常数 K_c 演化' },
                { icon: 'thermometer', text: '升温→平衡向吸热方向（逆反应）移动；加压→平衡向气体分子数减少的方向移动' },
                { icon: 'book-open', text: '勒夏特列原理：平衡总是向减弱外界扰动的方向移动（人教版选必一第2章）' }
            ]
        },
        'electrochemistry': {
            title: '电化学操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部按钮切换两种模式：原电池（Zn-Cu，自发产电）/ 电解池（CuCl₂，外加电压）' },
                { icon: 'play', text: '播放/暂停按钮控制电子在外电路 + 离子在溶液中的迁移动画' },
                { icon: 'zap', text: '原电池：Zn 失电子（负极氧化），Cu²⁺ 得电子（正极还原），E°=1.10 V' },
                { icon: 'zap', text: '电解池：阳极氧化（2Cl⁻−2e⁻→Cl₂↑），阴极还原（Cu²⁺+2e⁻→Cu）' },
                { icon: 'book-open', text: '判断电极口诀「正得负失」（原电池）/「阴还阳氧」（电解池）— 人教版选必一第4章' }
            ]
        },
        'chemical-bond': {
            title: '化学键操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部按钮切换三种化学键：离子键 / 共价键 / 金属键' },
                { icon: 'circle', text: '离子键：阴阳离子静电引力（NaCl），无方向性、无饱和性' },
                { icon: 'link', text: '共价键：原子共用电子对（H₂O），有方向性、有饱和性' },
                { icon: 'sparkles', text: '金属键：金属阳离子 + 自由电子海，解释金属导电、延展性' },
                { icon: 'book-open', text: '右侧「化学键知识点」详解每种键的形成条件、特征与性质（人教版必修2）' }
            ]
        },
        'ionic-reaction': {
            title: '离子反应操作指南',
            steps: [
                { icon: 'list', text: '顶部下拉选择反应：NaOH+HCl / Na₂CO₃+HCl / BaCl₂+Na₂SO₄' },
                { icon: 'mouse-pointer-click', text: '三阶段按钮切换：化学方程式 → 全离子方程式 → 净离子方程式' },
                { icon: 'eye', text: '画布左右展示反应物/生成物粒子，标灰的是「旁观离子」（不参与净反应）' },
                { icon: 'arrow-right', text: '净离子方程式去掉旁观离子，揭示反应本质（如 OH⁻ + H⁺ → H₂O）' },
                { icon: 'book-open', text: '复分解反应发生条件：生成水、气体、沉淀（人教版必修1第2章）' }
            ]
        },
        'organic-chemistry': {
            title: '有机化学操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '左侧分子按钮切换 5 种典型有机物：甲烷 / 乙醇 / 乙酸 / 苯 / 丙烯' },
                { icon: 'move', text: '在 3D 视图上拖拽鼠标可任意角度旋转分子，观察空间构型' },
                { icon: 'pause', text: '暂停按钮停止自动旋转，便于专注观察特定角度' },
                { icon: 'tag', text: '右侧面板高亮官能团（—OH 羟基 / —COOH 羧基 / C=C 双键 / 苯环）' },
                { icon: 'book-open', text: '展示典型反应：取代、加成、消去、酯化等（人教版选必三第3章）' }
            ]
        },
        'atomic-structure': {
            title: '原子结构与电子排布操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部 3 模式：轨道形状（s/p/d 电子云）/ 电子排布（轨道方框图）/ 玻尔模型（壳层动画）' },
                { icon: 'list', text: '元素选择支持 Z=1~36（H 到 Kr），覆盖人教版必修一周期表前 4 周期' },
                { icon: 'circle', text: '轨道模式：电子云密度图直观展示电子出现概率（亮区概率高）' },
                { icon: 'arrow-up-down', text: '排布模式：方框 + ↑↓ 箭头展示泡利不相容、洪特规则填充顺序' },
                { icon: 'book-open', text: '玻尔模型展示分层 K-L-M-N 与跃迁吸/放光（人教版必修一第4章 / 选必二第1章）' }
            ]
        },
        'molecular-structure': {
            title: '分子结构操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '左侧选择经典分子：H₂O / CO₂ / CH₄ / NH₃ 等，含杂化与极性信息' },
                { icon: 'move', text: '画布上拖拽鼠标自由旋转 3D 球棍模型，观察分子立体构型' },
                { icon: 'crosshair', text: '测量模式：依次点选两/三个原子，自动显示键长 / 键角' },
                { icon: 'eye', text: '轨道模式：可视化孤对电子（lone pair）与杂化轨道方向' },
                { icon: 'book-open', text: 'VSEPR 价层电子对互斥理论：键角与构型由总电子对数决定（人教版选必二第2章）' }
            ]
        },
        'chemical-reactions': {
            title: '化学反应操作指南',
            steps: [
                { icon: 'play', text: '播放/暂停/重置按钮控制反应动画进度（progress 0→1）' },
                { icon: 'sliders-horizontal', text: '速度滑块调节动画快慢，便于观察断键-成键过程细节' },
                { icon: 'zap', text: '内置反应：甲烷燃烧 CH₄+2O₂→CO₂+2H₂O 等，展示原子重组' },
                { icon: 'bar-chart-2', text: '右侧能量条直观对比反应物 / 过渡态 / 生成物能量（含活化能 Eₐ）' },
                { icon: 'book-open', text: '化学反应本质：旧键断裂吸能 + 新键形成放能，二者代数和决定吸/放热（人教版必修2）' }
            ]
        },
        'solution-ionization': {
            title: '溶液与电离操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '6 种物质按钮：HCl / NaOH（强电解质）/ CH₃COOH / NH₃·H₂O（弱电解质）/ NaCl / NaHCO₃' },
                { icon: 'sliders-horizontal', text: '浓度滑块调节 c（mol/L），实时计算 pH 与电离度 α' },
                { icon: 'eye', text: '画布粒子可视化：强电解质完全电离（无原分子），弱电解质 ⇌ 平衡状态' },
                { icon: 'play', text: '速度 / 暂停按钮控制粒子动画；鼠标悬停显示离子标签' },
                { icon: 'book-open', text: '弱酸 Ka、弱碱 Kb 反映电离程度；NaHCO₃ 因 HCO₃⁻ 水解溶液呈碱性（人教版选必一第3章）' }
            ]
        },
        'trigonometry': {
            title: '三角函数操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部 3 个模式按钮：sin/cos 双线对照、tan 单线、全部叠加（含 sec/csc 等延伸）' },
                { icon: 'sliders-horizontal', text: '拖动 trig-angle 滑块（0°~360°）观察单位圆上的动点与右侧波形同步生成' },
                { icon: 'play', text: '点击「自动播放」按钮启用角度自动扫动，trig-speed 滑块控制每秒扫过角度' },
                { icon: 'corner-up-right', text: '快捷预设：30°/45°/60°/90°/180°/270° 一键定位特殊角，配合「特殊角」按钮显示精确值（如 sin30°=1/2）' },
                { icon: 'book-open', text: '掌握诱导公式与单位圆几何意义，理解 sinθ=y、cosθ=x、tanθ=y/x（人教版必修一第5章）' }
            ]
        },
        'probability': {
            title: '概率统计操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '模式切换：🪙抛硬币（伯努利分布）/ 🎲掷骰子（古典概型 6 面均匀）' },
                { icon: 'play', text: 'prob-play-btn 启动连续随机试验，prob-reset-btn 清空重新开始' },
                { icon: 'plus-circle', text: '+1 按钮单次试验便于观察个例；+1000 按钮快速积累大样本对比理论概率' },
                { icon: 'sliders-horizontal', text: 'prob-speed 滑块调节动画速率，画布柱状图实时显示频率分布' },
                { icon: 'book-open', text: '理解大数定律：试验次数 n→∞ 时，频率 f → 理论概率 P；硬币 P=0.5、骰子各点 P=1/6（人教版必修二第10章）' }
            ]
        },
        'vector-ops': {
            title: '向量运算操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '4 种运算按钮：A+B 平行四边形/三角形法则、A−B 反向相加、A·B 数量积、proj_B A 投影向量' },
                { icon: 'move', text: '直接在画布上拖拽 A、B 向量端点改变方向与模长，结果向量与公式实时更新' },
                { icon: 'bar-chart-2', text: 'vecops-result 区显示坐标分量、模 |V|、夹角 cosθ 等数值' },
                { icon: 'eye', text: '加减法看几何路径（首尾相连），数量积 A·B=|A||B|cosθ（标量），投影 = (A·B)/|B|' },
                { icon: 'book-open', text: '向量是高考解析几何与立体几何工具：垂直⇔A·B=0，共线⇔A=λB（人教版必修二第6章）' }
            ]
        },
        'sequences': {
            title: '数列可视化操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部「等差数列 / 等比数列」两个 .seq-mode-btn 切换数列类型' },
                { icon: 'sliders-horizontal', text: '调节首项 a₁、公差 d（或公比 q）、项数 n 滑块，画布柱状图实时绘出 aₙ' },
                { icon: 'mouse-pointer-2', text: '鼠标悬停柱条高亮显示对应 (n, aₙ) 数值，便于读取具体项' },
                { icon: 'eye', text: '观察等差数列线性增长 vs 等比数列指数变化（|q|>1 时爆炸式增长）' },
                { icon: 'book-open', text: '等差通项 aₙ=a₁+(n−1)d，等比通项 aₙ=a₁·qⁿ⁻¹；前 n 项和 Sₙ 公式见教育面板（人教版选必二第4章）' }
            ]
        },
        'inequality': {
            title: '不等式与线性规划操作指南',
            steps: [
                { icon: 'sliders-horizontal', text: '3 个约束滑块 ineq-c0/c1/c2 控制 ax+by≤c 中的常数项 c，可行域随之伸缩' },
                { icon: 'eye', text: '画布显示三条约束直线交叉围成的可行域（多边形），半平面阴影表示不等式方向' },
                { icon: 'sliders-horizontal', text: '勾选「显示目标函数」后，ineq-obj 滑块平移目标函数 z=ax+by 的等高线，找最大/最小值' },
                { icon: 'corner-up-right', text: '最优解通常出现在可行域的顶点（线性规划基本定理）' },
                { icon: 'book-open', text: '一元二次不等式：解集与抛物线开口/判别式有关；线性规划是高考重点应用题型（人教版必修一/选必二）' }
            ]
        },
        'conic-sections': {
            title: '圆锥曲线操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '3 个 .conic-type-btn：椭圆 / 双曲线 / 抛物线，切换不同标准方程与几何性质' },
                { icon: 'sliders-horizontal', text: '滑块 conic-a / conic-b 控制椭圆/双曲线半轴；conic-p 控制抛物线焦准距' },
                { icon: 'eye', text: '画布动态描绘曲线轨迹，红色焦点、橙色准线、蓝色离心率几何意义同步可视化' },
                { icon: 'bar-chart-2', text: '右侧 conic-info 实时显示标准方程、离心率 e=c/a、焦点坐标、渐近线（双曲线）等' },
                { icon: 'book-open', text: '椭圆 0<e<1、双曲线 e>1、抛物线 e=1；统一定义：到焦点距离/到准线距离=e（人教版选必一第3章）' }
            ]
        },
        'function-properties': {
            title: '函数性质探究操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部 3 个 .fp-mode-btn：📈单调性 / 🔄奇偶性 / 🔁周期性，切换分析角度' },
                { icon: 'mouse-pointer-click', text: '.fp-func-btn 切换不同函数（一次/二次/三次/绝对值/sin/exp/log 等）观察性质表现' },
                { icon: 'sliders-horizontal', text: '单调性模式下，调整 fp-int-a / fp-int-b 区间输入框（或拖拽画布上的菱形标记）框选研究区间' },
                { icon: 'eye', text: '画布以颜色高亮单调增/减区间、奇偶对称轴、周期 T；fp-info 给出严谨的数学判定' },
                { icon: 'book-open', text: '判定：单调性看 f(x₁)−f(x₂) 符号；奇函数 f(−x)=−f(x) 关于原点对称；偶函数 f(−x)=f(x) 关于 y 轴对称（人教版必修一第3章）' }
            ]
        },
        'set-operations': {
            title: '集合运算操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '6 个 .setops-op-btn：A∪B（并）/ A∩B（交）/ A−B（差）/ B−A / Aᶜ（补）/ A∆B（对称差）' },
                { icon: 'edit-3', text: 'setops-input-a / setops-input-b 输入集合 A、B 元素（如 1,2,3）；setops-input-u 设置全集 U' },
                { icon: 'eye', text: '画布维恩图 (Venn) 高亮当前运算结果区域，深色填充表示属于结果集' },
                { icon: 'bar-chart-2', text: 'setops-result 区显示运算结果集合 + 元素个数；setops-edu 给出公式与运算律' },
                { icon: 'book-open', text: '德摩根律：(A∪B)ᶜ=Aᶜ∩Bᶜ、(A∩B)ᶜ=Aᶜ∪Bᶜ；分配律 A∩(B∪C)=(A∩B)∪(A∩C)（人教版必修一第1章）' }
            ]
        },
        'permutation-combination': {
            title: '排列组合操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '3 个 .permcomb-mode-btn：排列 P(n,r) 有序 / 组合 C(n,r) 无序 / 杨辉三角（C(n,k) 二项展开系数）' },
                { icon: 'sliders-horizontal', text: 'permcomb-n 滑块设置元素总数 n，permcomb-r 滑块设置抽取数 r（杨辉三角自动生成行）' },
                { icon: 'eye', text: '画布枚举或图示所有排列/组合方案，pc-info 同步显示公式 P(n,r)=n!/(n−r)!、C(n,r)=n!/(r!(n−r)!) 与具体值' },
                { icon: 'grid', text: '杨辉三角模式：每个数等于上方两数之和，第 n 行就是 (a+b)ⁿ 的展开系数 C(n,0)…C(n,n)' },
                { icon: 'book-open', text: '关键区分：排列考虑顺序（如班长副班长）、组合不考虑顺序（如选 r 人代表）；二项式定理是高考重点（人教版选必三第6章）' }
            ]
        },
        'exp-log': {
            title: '指数与对数函数操作指南',
            steps: [
                { icon: 'sliders-horizontal', text: '#el-base 滑块（0.1~5）调整底数 a，#el-base-val 实时显示当前数值；4 个 .el-preset 一键切到 ½ / 2 / e / 10 等关键底数' },
                { icon: 'mouse-pointer-click', text: '3 个 .el-toggle 复选框分别开关 y=aˣ（指数）、y=logₐx（对数）、y=x（镜像参考线）' },
                { icon: 'eye', text: '画布同步绘制两条曲线，关于 y=x 严格对称即印证「指数与对数互为反函数」' },
                { icon: 'bar-chart-2', text: '滑动 a 越过 1：a>1 指数递增、对数递增；0<a<1 指数递减、对数递减；a=1 退化为常数函数（不构成函数）' },
                { icon: 'book-open', text: '关键性质：aˣ⋅aʸ=aˣ⁺ʸ；logₐ(MN)=logₐM+logₐN；换底公式 logₐb=lnb/lna（人教版必修一第4章）' }
            ]
        },
        'geometry': {
            title: '几何变换操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '顶部 2 个 .geo-mode-btn 切换：「仿射变换」演示平移/缩放/旋转/错切，「三角形几何」演示外心/内心/重心/垂心' },
                { icon: 'sliders-horizontal', text: '仿射模式：调整 geo-tx/ty 平移、geo-sx/sy 缩放、geo-rot 旋转角、geo-shear 错切，画布同步显示原始与变换后图形' },
                { icon: 'play', text: '#geo-animate-btn 自动播放变换过程，可观察连续变化下的轨迹（旋转 + 缩放 = 螺线）' },
                { icon: 'eye', text: '三角形模式：拖拽顶点调整三角形，画布动态绘制四心，geo-edu 同步显示坐标与几何意义' },
                { icon: 'book-open', text: '仿射变换矩阵 [[a,b],[c,d]]+(tx,ty) 可表达 2D 所有线性变换；四心是初等几何核心定理（人教版必修二第6章）' }
            ]
        },
        'complex-numbers': {
            title: '复数运算操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '4 个 .cx-mode-btn 切换模式：四则运算 ops / 单位根 roots / 函数变换 domain / 欧拉公式 euler' },
                { icon: 'edit-3', text: 'ops 模式：cx-z1-re/im、cx-z2-re/im 输入复数实/虚部；.cx-op-btn 选择 +、−、×、÷，画布显示复平面向量与平行四边形法则' },
                { icon: 'sliders-horizontal', text: 'roots：cx-root-n 滑块（n=2~12）设次数，画布动画演示 n 次单位根均匀分布在单位圆并构成正多边形；cx-roots-anim 一键播放' },
                { icon: 'play', text: 'euler 模式：cx-theta 滑块或 cx-euler-anim 演示 e^(iθ)=cosθ+isinθ；θ=π 时即著名公式 e^(iπ)+1=0' },
                { icon: 'book-open', text: '复数 z=a+bi 几何即向量；模 |z|=√(a²+b²)、辐角 arg(z)=arctan(b/a)；棣莫弗 (cosθ+isinθ)ⁿ=cos(nθ)+isin(nθ)（人教版必修二第7章）' }
            ]
        },
        'solid-geometry': {
            title: '立体几何操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '5 个 .sg-shape-btn 切换几何体：正方体 / 正四面体 / 正八面体 / 圆柱体 / 圆锥体' },
                { icon: 'sliders-horizontal', text: '#sg-cross 滑块控制水平截面位置，#sg-cross-val 显示当前 z 坐标；可观察截面形状随高度的变化（圆柱→圆，圆锥→圆缩小到点）' },
                { icon: 'play', text: '#sg-speed 调旋转速度，#sg-pause 暂停/继续 3D 旋转动画；鼠标拖拽画布也可手动旋转视角' },
                { icon: 'eye', text: '画布以 3D 透视投影显示几何体，正面线段实线、背面虚线，截面平面以半透明色高亮' },
                { icon: 'book-open', text: '欧拉公式 V−E+F=2（凸多面体顶点−棱+面=2）；正多面体仅有 5 种（柏拉图体）；旋转体侧面积 S=2πrl（人教版必修二第8章）' }
            ]
        },
        'circuit-analysis': {
            title: '电路分析操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '2 个 .circuit-mode-btn：串联（电流处处相等）/ 并联（电压处处相等），切换不同等效电阻公式' },
                { icon: 'sliders-horizontal', text: '#circuit-voltage 滑块（1~24V）调电源电压，#circuit-r1 / #circuit-r2 调两个电阻；右侧 -val 实时显示数值' },
                { icon: 'play', text: '#circuit-pause 暂停电流粒子动画；#circuit-reset 复位时间。电流粒子流速正比于电流大小 I=U/R' },
                { icon: 'eye', text: '画布渲染电路图与电流方向，circuit-info 教育面板列出欧姆定律、分压/分流规则、功率分配 P=UI=I²R' },
                { icon: 'book-open', text: '串联：R=R₁+R₂、U=U₁+U₂、I 不变；并联：1/R=1/R₁+1/R₂、I=I₁+I₂、U 不变（人教版必修三第11章）' }
            ]
        },
        'waves': {
            title: '波动叠加操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '3 个 .wave-mode-btn 切换：叠加 superposition / 驻波 standing / 多普勒 doppler' },
                { icon: 'sliders-horizontal', text: '叠加模式：wave-a1/f1/l1 调波 1 的振幅/频率/波长，wave-a2/f2/l2 调波 2；3 个复选框控制波 1、波 2、叠加波的显示' },
                { icon: 'play', text: '4 个 [data-wave-preset] 一键预设：加强（同相）/ 抵消（反相）/ 驻波（反向同频）/ 拍频（频率略差）' },
                { icon: 'eye', text: '画布同步绘制三条波形（红=波1、蓝=波2、紫=合成）；驻波模式额外显示波节/波腹与 wave-sw-n 谐波次数' },
                { icon: 'book-open', text: '波速 v=fλ；同相加强 A=A₁+A₂、反相抵消 A=|A₁−A₂|；驻波频率 fₙ=nv/(2L)；多普勒 f′=f·(v±v₀)/(v∓vₛ)（人教版选必一第3章）' }
            ]
        },
        'kinematics': {
            title: '匀变速直线运动操作指南',
            steps: [
                { icon: 'sliders-horizontal', text: '#kin-v0 滑块设初速度 v₀，#kin-a 设加速度（正/负代表加速/减速），#kin-t 设时间；右侧 -val 实时显示数值' },
                { icon: 'play', text: '#kin-play-btn 自动播放小球运动并联动 t 滑块；#kin-reset-btn 复位 t=0 重新开始' },
                { icon: 'eye', text: '画布顶端是运动轨迹（小球+残影），下方是 v-t 图像；图线斜率即 a，图线下面积即位移 s' },
                { icon: 'bar-chart-2', text: 'kin-info 实时计算 v(t)=v₀+at、s(t)=v₀t+½at²；kin-edu 给出加/减速判定与不含 t 的推导式 v²−v₀²=2as' },
                { icon: 'book-open', text: '设 a<0 演示刹车：v 减小到 0 即停止；常用刹车距离公式 s=v₀²/(2|a|)（人教版必修一第2章）' }
            ]
        },
        'projectile': {
            title: '抛体运动操作指南',
            steps: [
                { icon: 'sliders-horizontal', text: 'proj-v0 调初速度大小，proj-angle 调发射角 θ（0~90°），proj-g 调重力加速度（地球9.8/月球1.6/木星等）' },
                { icon: 'play', text: '#proj-play-btn 自动播放抛物线轨迹；#proj-reset-btn 复位；拖动 #proj-t 滑块手动定格任意时刻' },
                { icon: 'mouse-pointer-click', text: '#proj-vectors 复选框显示瞬时速度向量分量 (vₓ, vᵧ)；#proj-envelope 显示不同 θ 的射程包络曲线' },
                { icon: 'eye', text: '画布同步显示轨迹+顶点高度+落点；proj-info 给出 x/y/v 实时数值，proj-edu 解释水平匀速 + 竖直自由落体的独立叠加' },
                { icon: 'book-open', text: '射程 R=v₀²sin(2θ)/g，θ=45° 时最远；最大高度 H=v₀²sin²θ/(2g)；飞行时间 T=2v₀sinθ/g（人教版必修二第5章）' }
            ]
        },
        'circular-motion': {
            title: '圆周运动操作指南',
            steps: [
                { icon: 'sliders-horizontal', text: '#circ-radius 调半径 r，#circ-omega 调角速度 ω，#circ-mass 调质量 m；circ-stats 实时联动显示 v/a/F/T' },
                { icon: 'play', text: '#circ-play 暂停/继续小球绕圆心匀速圆周运动；#circ-reset 复位到起点角度 0' },
                { icon: 'mouse-pointer-click', text: '3 个复选框 #circ-show-v / circ-show-a / circ-show-f：分别显示速度向量（蓝色切线）、向心加速度（绿色径向）、向心力（红色径向）' },
                { icon: 'eye', text: '画布固定圆周轨道 + 小球；速度始终沿切线方向，向心加速度始终指向圆心，二者垂直恒定不变（匀速圆周）' },
                { icon: 'book-open', text: '关键公式：v=ωr，a=ω²r=v²/r，F=ma=mω²r=mv²/r；周期 T=2π/ω；ω 与 r 独立可调（人教版必修二第6章）' }
            ]
        },
        'optics': {
            title: '光学操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '6 个 .optics-mode-btn 切换模式：透镜成像 lens / 双缝干涉 doubleslit / 折射与全反射 refraction / 棱镜色散 prism / 衍射光栅 grating / 偏振 polarization' },
                { icon: 'sliders-horizontal', text: '透镜模式：optics-focal 调焦距 f、optics-objdist 调物距 u；折射模式：optics-n1/n2 调两介质折射率；双缝模式：optics-slitsep 缝距、optics-wavelength 波长' },
                { icon: 'play', text: 'optics-pause/reset 控制动画；双缝模式额外有 optics-slit-toggle 单独控制干涉条纹动画播放/暂停' },
                { icon: 'eye', text: '画布按当前模式渲染：透镜画三条特殊光线 + 像；双缝画明暗条纹；折射画入射/折射/反射光线 + 临界角；棱镜分光 7 色' },
                { icon: 'book-open', text: '透镜公式 1/u + 1/v = 1/f；折射定律 n₁sinθ₁ = n₂sinθ₂；干涉条纹间距 Δy = λL/d；全反射临界角 sinC = n₂/n₁（人教版选必一第4章）' }
            ]
        },
        'electromagnetic-induction': {
            title: '电磁感应操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '2 个 .emi-mode-btn 切换：手动 manual（鼠标/触屏拖拽磁铁）/ 自动 auto（磁铁匀速往复穿过线圈）' },
                { icon: 'hand', text: '手动模式：拖拽磁铁穿过线圈，速度越快感应电动势 ε 越大；emi-info 实时显示磁通量 Φ 与电动势 ε' },
                { icon: 'play', text: '#emi-pause 暂停/继续，#emi-reset 复位时间与磁铁位置（自动切回 manual）' },
                { icon: 'eye', text: '画布渲染线圈 + 磁铁 + 电流方向箭头 + 安培计读数；磁铁靠近线圈→Φ 增大、远离→Φ 减小，感应电流方向相反（楞次"来拒去留"）' },
                { icon: 'book-open', text: '法拉第 ε = −dΦ/dt；磁通量 Φ = BS·cosθ；导体切割 ε = BLv；楞次定律：感应电流的磁场总阻碍引起它的磁通量变化（人教版选必二第2章）' }
            ]
        },
        'alternating-current': {
            title: '交变电流操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '3 个 .ac-mode-btn 切换：波形（u-t 正弦曲线）/ 相量图（旋转矢量）/ 变压器（原副线圈匝数比）' },
                { icon: 'sliders-horizontal', text: 'ac-freq 调频率 f（中国 50 Hz、美国 60 Hz）、ac-phase 调初相位 φ；变压器模式：ac-n1 / ac-n2 分别调原/副线圈匝数 N₁/N₂' },
                { icon: 'play', text: 'ac-speed 调动画速度；ac-pause 暂停/继续；ac-reset 复位时间与所有参数（频率回 50、相位回 30°）' },
                { icon: 'eye', text: '波形模式：u = U₀sin(2πft+φ) 滚动绘制；相量模式：旋转矢量 + 投影；变压器模式：原副线圈电压条形图实时联动 N₂/N₁' },
                { icon: 'book-open', text: '正弦交流 u=U₀sin(ωt)；有效值 U=U₀/√2（≈0.707U₀）；变压器电压比 U₁/U₂=N₁/N₂、电流比反比 I₁/I₂=N₂/N₁；功率守恒 U₁I₁=U₂I₂（人教版选必二第3章）' }
            ]
        },
        'force-composition': {
            title: '力的合成与分解操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '3 个 .fc-mode-btn 切换：力的合成（平行四边形定则）/ 正交分解（Fx Fy）/ 斜面分析（重力沿/垂直斜面分解 + 摩擦）' },
                { icon: 'hand', text: '合成/分解模式：直接拖拽红蓝箭头端点改变力 F₁/F₂ 的大小和方向；fc-info 实时显示合力 R 和角度' },
                { icon: 'sliders-horizontal', text: '斜面模式专属：fc-inc-slider 调斜面角 α、fc-mass-slider 调质量 m、fc-mu-slider 调摩擦系数 μ；面板同步显示 mg/N/sin/cos 各分量' },
                { icon: 'eye', text: '画布同步绘制力的箭头 + 平行四边形/三角形（合成）、正交虚线投影（分解）、斜面 + 重力分解 + 摩擦力（斜面）' },
                { icon: 'book-open', text: '平行四边形定则：R = √(F₁²+F₂²+2F₁F₂cosθ)；正交分解 Fx=Fcosθ、Fy=Fsinθ；斜面分解 N=mgcosα、F∥=mgsinα、f=μN（人教版必修一第3章）' }
            ]
        },
        'momentum-conservation': {
            title: '动量守恒操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '3 个 .mc-mode-btn 切换：弹性碰撞 elastic（动量+动能都守恒）/ 非弹性 inelastic（动量守恒、e 可调）/ 完全非弹性 perfectly（碰后粘在一起）' },
                { icon: 'sliders-horizontal', text: '4 个滑块：mc-m1 / mc-m2 调两物块质量，mc-v1 / mc-v2 调初速度（正负代表方向）；非弹性模式额外有 mc-e 恢复系数（0~1）' },
                { icon: 'play', text: '#mc-play-btn 开始模拟，#mc-reset-btn 重置；mc-info 实时显示碰前碰后动量 p 与动能 Eₖ' },
                { icon: 'eye', text: '画布同步绘制 A、B 两物块的运动 + 速度向量 + 碰撞瞬间高亮；mc-edu 给出动量与能量守恒计算与等质量"交换速度"等典型结论' },
                { icon: 'book-open', text: '动量守恒（外力为 0 或可忽略）：m₁v₁+m₂v₂=m₁v₁′+m₂v₂′；弹性碰撞额外 ½m₁v₁²+½m₂v₂²=½m₁v₁′²+½m₂v₂′²；完全非弹性 v′=(m₁v₁+m₂v₂)/(m₁+m₂)（人教版选必一第1章）' }
            ]
        },
        'gravitation': {
            title: '万有引力操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '2 个 .grav-mode-btn 切换：轨道模拟（行星绕中心天体椭圆/圆轨道）/ 引力场（场线与等势面可视化）' },
                { icon: 'sliders-horizontal', text: '中心质量 M 滑块（100~1500）：M 越大引力越强、轨道周期越短、近距离弯曲越剧烈' },
                { icon: 'play', text: '"力向量"按钮切换是否显示行星受到的瞬时引力箭头；grav-pause 暂停/继续；grav-reset 复位轨道初值' },
                { icon: 'eye', text: '轨道模式：行星沿椭圆运动、近日点速度大、远日点速度小（开普勒第二定律面积速度恒定）；场模式：场线由质点中心向四周辐射' },
                { icon: 'book-open', text: 'F = GMm/r²（牛顿万有引力）；圆轨道 v=√(GM/r)、T=2π√(r³/GM)；开普勒三定律 T²/r³=4π²/GM；地表 g≈GM地/R地²≈9.8（人教版必修二第7章）' }
            ]
        },
        'electromagnetic': {
            title: '电磁场操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '5 个 .em-mode-btn 切换：电力线 / 等势线 / 电势图（热力图）/ 粒子轨迹 / 磁场（B 由电流产生）' },
                { icon: 'hand', text: '直接在画布上拖拽红/蓝点电荷（+/−）改变位置；4 个 .em-preset-btn 一键加载：偶极子 / 四极子 / 平行板 / 三角形' },
                { icon: 'sliders-horizontal', text: 'em-pause 暂停场动画、em-reset 复位电荷分布；em-toggle-probe 显示测量探针，em-toggle-lines / em-toggle-vectors 切换电力线与场矢量箭头' },
                { icon: 'eye', text: '电力线由 +Q 出发指向 −Q（不相交）；等势线垂直于电力线；磁场模式按右手定则给出环绕电流的磁感线' },
                { icon: 'book-open', text: '点电荷场强 E=kQ/r²、电势 φ=kQ/r、势能 W=qφ；安培环路 ∮B·dl=μ₀I；洛伦兹力 F=qv×B；右手定则 + 左手定则（人教版必修三 + 选必二）' }
            ]
        },
        'charged-particle': {
            title: '带电粒子运动操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '3 个 .cp-mode-btn 切换：洛伦兹力偏转（圆周运动）/ 质谱仪（V 加速 + B 偏转分离同位素）/ 速度选择器（电场磁场正交相消）' },
                { icon: 'sliders-horizontal', text: '洛伦兹模式：q / m / v₀ / B 四滑块；质谱模式：accV（加速电压）+ B；选择器：E + B；cp-info 实时显示 r=mv/(qB) 与周期 T=2πm/(qB)' },
                { icon: 'play', text: 'cp-play 开始模拟、cp-reset 复位粒子初始位置；可在三种模式之间随时切换观察不同物理图景' },
                { icon: 'eye', text: '洛伦兹模式：单粒子做圆周运动；质谱模式：H⁺/D⁺/He⁺ 三种粒子分离成不同半径圆弧；选择器：当 v=E/B 时直线通过、其他偏转' },
                { icon: 'book-open', text: '洛伦兹力 F=qvB（v⊥B）→ 圆周 r=mv/(qB)、T=2πm/(qB)（与 v 无关！）；质谱仪 r=√(2mV/q)/B；速度选择器 v=E/B（人教版选必二第1章）' }
            ]
        },
        'relativity': {
            title: '相对论操作指南',
            steps: [
                { icon: 'mouse-pointer-click', text: '7 个 .rel-mode-btn 切换：时间膨胀 / 长度收缩 / 质能等价 / 时空图 / 速度叠加 / 双生子 / 多普勒 / Lorentz 变换' },
                { icon: 'sliders-horizontal', text: 'rel-velocity 滑块调相对速度 β=v/c（0~0.99c）；γ=1/√(1−β²) 实时显示；某些模式额外有 u（叠加速度）和双生子距离滑块' },
                { icon: 'play', text: 'rel-pause 暂停/继续；rel-reset 复位时间 t、时空事件；时空图模式可在画布上双击添加事件、拖拽调整' },
                { icon: 'eye', text: '时间膨胀：动钟变慢 Δt=γΔτ；长度收缩：L=L₀/γ；时空图：世界线 + 光锥 + Lorentz 变换坐标系；多普勒：红/蓝移频率比' },
                { icon: 'book-open', text: 'γ=1/√(1−v²/c²)；时间膨胀 Δt=γΔτ；长度收缩 L=L₀/γ；质能 E=mc²、E²=(pc)²+(mc²)²；速度叠加 w=(u+v)/(1+uv/c²)（人教版选必三第5章）' }
            ]
        }
    },

    // ── Public API ──

    init() {
        this._createOverlay();
        this._createHelpButton();
    },

    // Called after experiment init — show guide if first time
    showIfFirstTime(page, moduleId) {
        const seen = this._getSeenSet();
        const key = `${page}:${moduleId}`;
        if (seen.has(key)) return;

        this._currentModule = { page, moduleId };
        this._show(page, moduleId);
        seen.add(key);
        this._saveSeenSet(seen);
    },

    // Force show (from "?" button)
    showForCurrent() {
        if (!this._currentModule) return;
        this._show(this._currentModule.page, this._currentModule.moduleId);
    },

    // Show help button when an experiment is open
    showHelpButton(page, moduleId) {
        this._currentModule = { page, moduleId };
        if (this._helpBtn) this._helpBtn.style.display = 'flex';
    },

    // Hide help button when returning to gallery
    hideHelpButton() {
        this._currentModule = null;
        if (this._helpBtn) this._helpBtn.style.display = 'none';
    },

    // ── Internal ──

    _show(page, moduleId) {
        const guide = this._experimentGuides[moduleId] || this._subjectGuides[page];
        if (!guide || !this._overlay) return;

        const card = this._overlay.querySelector('.guide-card');
        card.innerHTML = this._renderCard(guide);
        this._overlay.classList.add('active');

        // Render lucide icons in the guide card
        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [card] });

        // Focus dismiss button for keyboard accessibility
        const btn = card.querySelector('.guide-dismiss-btn');
        if (btn) setTimeout(() => btn.focus(), 100);
    },

    _dismiss() {
        if (this._overlay) this._overlay.classList.remove('active');
    },

    _renderCard(guide) {
        const stepsHTML = guide.steps.map((step, i) => `
            <div class="guide-step">
                <div class="guide-step__number">${i + 1}</div>
                <div class="guide-step__icon"><i data-lucide="${step.icon}"></i></div>
                <div class="guide-step__text">${step.text}</div>
            </div>
        `).join('');

        return `
            <div class="guide-card__header">
                <div class="guide-card__title">${guide.title}</div>
                <div class="guide-card__subtitle">首次进入实验时显示，可通过右下角 ? 按钮重新查看</div>
            </div>
            <div class="guide-card__steps">${stepsHTML}</div>
            <button class="btn btn--primary guide-dismiss-btn" tabindex="0">知道了，开始探索</button>
        `;
    },

    _createOverlay() {
        const overlay = document.createElement('div');
        overlay.className = 'experiment-guide-overlay';
        overlay.id = 'experiment-guide-overlay';
        overlay.innerHTML = '<div class="guide-card"></div>';

        // Click outside card to dismiss
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this._dismiss();
        });

        // Click dismiss button
        overlay.addEventListener('click', (e) => {
            if (e.target.closest('.guide-dismiss-btn')) this._dismiss();
        });

        // Esc to dismiss
        overlay.addEventListener('keydown', (e) => {
            if (e.key === 'Escape') this._dismiss();
        });

        document.body.appendChild(overlay);
        this._overlay = overlay;
    },

    _createHelpButton() {
        const btn = document.createElement('button');
        btn.className = 'experiment-guide-help-btn';
        btn.id = 'experiment-guide-help';
        btn.setAttribute('aria-label', '查看操作提示');
        btn.setAttribute('title', '操作提示');
        btn.textContent = '?';
        btn.style.display = 'none';

        btn.addEventListener('click', () => this.showForCurrent());
        document.body.appendChild(btn);
        this._helpBtn = btn;
    },

    _getSeenSet() {
        try {
            const raw = localStorage.getItem(this._storageKey);
            return raw ? new Set(JSON.parse(raw)) : new Set();
        } catch {
            return new Set();
        }
    },

    _saveSeenSet(set) {
        try {
            localStorage.setItem(this._storageKey, JSON.stringify([...set]));
        } catch { /* quota exceeded — degrade gracefully */ }
    }
};

window.ExperimentGuide = ExperimentGuide;

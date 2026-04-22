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

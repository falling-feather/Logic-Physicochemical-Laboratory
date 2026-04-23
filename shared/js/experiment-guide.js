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

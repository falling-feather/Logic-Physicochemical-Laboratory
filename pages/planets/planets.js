/* ===== Planets View — 沉浸式 3D 镂空星系导航大屏（v4.2.0-α4） =====
 * Vanilla Canvas 2D 模拟 3D 球面布局
 * 5 个学科星球围绕中心旋转，鼠标拖拽改变视角，hover 高亮 + 点击跳转
 */

window.PlanetsView = {
    canvas: null,
    ctx: null,
    info: null,
    W: 0, H: 0, dpr: 1,
    rafId: null,
    lastT: 0,

    yaw: 0,
    pitch: -0.15,
    targetYaw: 0,
    targetPitch: -0.15,
    autoRotate: true,
    autoYawSpeed: 0.0003, // rad/ms

    isDragging: false,
    dragStartX: 0, dragStartY: 0,
    dragStartYaw: 0, dragStartPitch: 0,
    moved: false,

    hovered: null,        // 当前 hover 的对象（galaxies: galaxy; galaxy: subject 或 '__center'; subject: satellite 或 '__center'）
    stars: [],

    // ── v5.0：多星系顶层 ──
    mode: 'galaxies',     // 'galaxies' | 'galaxy' | 'subject'
    galaxies: [],         // 从 CONFIG.galaxies 构造
    currentGalaxy: null,  // 进入某个星系后保存
    galTime: 0,           // galaxies 层动画累计时间
    // v5.0：星系顶层入场动画累计（0 → 1，1400ms 完成，错峰）
    enterStart: 0,
    tEnter: 0,
    tG: 0,                // 进入 galaxy 层过渡 0→1
    tGTarget: 0,
    // 以下为破碎动画状态
    shattering: false,
    shatterParticles: [],
    shatterX: 0, shatterY: 0,
    shatterColor: '#3aa9ff',
    shatterTime: 0,       // 0→1 推进

    // ── v4.4：星系作为目录 — 双层星系状态 ──
    currentSubject: null, // 进入子星系后保存当前 subject 对象
    satellites: [],       // 当前子星系的卫星列表
    tIn: 0,               // 进入 subject 的过渡进度 0→1
    tInTarget: 0,
    subjTime: 0,          // 卫星轨道独立时间累加（ms）
    launchingSat: null,   // v4.4-α5：正在 zoom 跳转的卫星
    tLaunch: 0,           // 0→1，控制跳转动画进度
    tLaunchTarget: 0,
    exiting: false,       // v4.4-α8：是否正在退出子星系（zoom-out）
    tOut: 0,              // 0→1 zoom-out 动画进度

    subjects: [],   // v5.0：动态 — 进入 galaxy 后根据 currentGalaxy.subjectIds 构造

    // v5.0：全部学科元数据（以前是硬编码的 5 个）
    _allSubjects: {
        mathematics: { id: 'mathematics', label: '数学', desc: '函数·几何·概率·向量·圆锥曲线 (15 实验)', color: '#5b8dce' },
        physics:     { id: 'physics',     label: '物理', desc: '力学·电磁·波动·相对论·万有引力 (17 实验)', color: '#a78bfa' },
        chemistry:   { id: 'chemistry',   label: '化学', desc: '周期表·反应·平衡·电化学·有机化学 (12 实验)', color: '#10b981' },
        algorithms:  { id: 'algorithms',  label: '算法', desc: '排序·搜索·图·动态规划·KMP (8 实验)', color: '#f59e0b' },
        biology:     { id: 'biology',     label: '生物', desc: '细胞·DNA·光合·遗传·神经免疫 (13 实验)', color: '#06b6d4' },
        codevis:     { id: 'codevis',     label: '代码可视化', desc: '代码执行追踪 Phase 1 (1 实验)', color: '#ec4899' },
        'codespace-viz': { id: 'codespace-viz', label: '可视化', desc: 'JS · Python · C/C++ 执行追踪与数据结构动画（跳转子站）', color: '#22ff88', externalUrl: 'codevis/index.html' }
    },

    init() {
        this.canvas = document.getElementById('planets-canvas');
        this.info = document.getElementById('planets-info');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');

        this._resize = this._resize.bind(this);
        this._loop = this._loop.bind(this);
        this._onDown = this._onDown.bind(this);
        this._onMove = this._onMove.bind(this);
        this._onUp = this._onUp.bind(this);
        this._onClick = this._onClick.bind(this);
        this._onTouchStart = this._onTouchStart.bind(this);
        this._onTouchMove = this._onTouchMove.bind(this);
        this._onTouchEnd = this._onTouchEnd.bind(this);
        this._onKeyDown = this._onKeyDown.bind(this);

        this._resize();
        window.addEventListener('resize', this._resize);
        this.canvas.addEventListener('mousedown', this._onDown);
        window.addEventListener('mousemove', this._onMove);
        window.addEventListener('mouseup', this._onUp);
        this.canvas.addEventListener('click', this._onClick);
        this.canvas.addEventListener('touchstart', this._onTouchStart, { passive: false });
        this.canvas.addEventListener('touchmove', this._onTouchMove, { passive: false });
        this.canvas.addEventListener('touchend', this._onTouchEnd);
        window.addEventListener('keydown', this._onKeyDown);

        this._initStars();
        this._buildGalaxies();
        this._updateChrome();
        this.enterStart = performance.now();
        // v5.0：prefers-reduced-motion 降级——用户设置减动动画时跳过入场动画
        const _reduce = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        this.tEnter = _reduce ? 1 : 0;
        // v5.0：触发 chrome（标题/HUD/返回键）错峰淡入动画（减动时跳过）
        const pageRoot = document.getElementById('page-planets');
        if (pageRoot && !_reduce) {
            pageRoot.classList.remove('planets-entering');
            // 强制 reflow 以便 CSS 动画从头播放
            void pageRoot.offsetWidth;
            pageRoot.classList.add('planets-entering');
        } else if (pageRoot) {
            pageRoot.classList.remove('planets-entering');
        }
        this.lastT = performance.now();
        this.rafId = requestAnimationFrame(this._loop);
    },

    destroy() {
        if (this.rafId) cancelAnimationFrame(this.rafId);
        this.rafId = null;
        if (!this.canvas) return;
        window.removeEventListener('resize', this._resize);
        this.canvas.removeEventListener('mousedown', this._onDown);
        window.removeEventListener('mousemove', this._onMove);
        window.removeEventListener('mouseup', this._onUp);
        this.canvas.removeEventListener('click', this._onClick);
        this.canvas.removeEventListener('touchstart', this._onTouchStart);
        this.canvas.removeEventListener('touchmove', this._onTouchMove);
        this.canvas.removeEventListener('touchend', this._onTouchEnd);
        window.removeEventListener('keydown', this._onKeyDown);
        // 离开页面时复位为 galaxies 模式，避免下次回来仍在其他状态
        this.mode = 'galaxies';
        this.currentGalaxy = null;
        this.currentSubject = null;
        this.subjects = [];
        this.satellites = [];
        this.tIn = 0; this.tInTarget = 0;
        this.tG = 0; this.tGTarget = 0;
        this.launchingSat = null;
        this.tLaunch = 0; this.tLaunchTarget = 0;
        this.exiting = false;
        this.tOut = 0;
        this.shattering = false;
        this.shatterParticles = [];
        clearTimeout(this._navTimer);
        this._updateChrome();
    },

    _resize() {
        const dpr = window.devicePixelRatio || 1;
        const w = window.innerWidth;
        const h = window.innerHeight;
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w; this.H = h;
        this.dpr = dpr;
    },

    _initStars() {
        this.stars = [];
        const N = 220;
        for (let i = 0; i < N; i++) {
            this.stars.push({
                x: (Math.random() - 0.5) * 2,
                y: (Math.random() - 0.5) * 2,
                z: (Math.random() - 0.5) * 2,
                a: 0.2 + Math.random() * 0.7
            });
        }
    },

    _onDown(e) {
        this.isDragging = true;
        this.moved = false;
        this.dragStartX = e.clientX; this.dragStartY = e.clientY;
        this.dragStartYaw = this.yaw; this.dragStartPitch = this.pitch;
        this.autoRotate = false;
    },

    _onMove(e) {
        if (this.isDragging) {
            const dx = e.clientX - this.dragStartX;
            const dy = e.clientY - this.dragStartY;
            if (Math.abs(dx) + Math.abs(dy) > 4) this.moved = true;
            this.targetYaw = this.dragStartYaw + dx * 0.005;
            this.targetPitch = Math.max(-1.2, Math.min(1.2, this.dragStartPitch - dy * 0.005));
        } else {
            // hover detection
            const rect = this.canvas.getBoundingClientRect();
            this._updateHover(e.clientX - rect.left, e.clientY - rect.top);
        }
    },

    _onUp() {
        this.isDragging = false;
        // resume auto rotate after 4s of no input
        clearTimeout(this._autoTimer);
        this._autoTimer = setTimeout(() => { this.autoRotate = true; }, 4000);
    },

    _onClick(e) {
        if (this.moved) return;
        this._handleTap();
    },

    _onTouchStart(e) {
        e.preventDefault();
        if (e.touches[0]) {
            this._onDown({ clientX: e.touches[0].clientX, clientY: e.touches[0].clientY });
            const rect = this.canvas.getBoundingClientRect();
            this._updateHover(e.touches[0].clientX - rect.left, e.touches[0].clientY - rect.top);
        }
    },

    _onTouchMove(e) {
        e.preventDefault();
        if (e.touches[0]) {
            this._onMove({ clientX: e.touches[0].clientX, clientY: e.touches[0].clientY });
        }
    },

    _onTouchEnd() {
        // tap (no drag) → click
        if (!this.moved) this._handleTap();
        this.isDragging = false;
        clearTimeout(this._autoTimer);
        this._autoTimer = setTimeout(() => { this.autoRotate = true; this.hovered = null; this._updateInfo(); }, 4000);
    },

    _onKeyDown(e) {
        if (e.key === 'Escape') {
            if (this.mode === 'subject') this._exitSubject();
            else if (this.mode === 'galaxy') this._exitGalaxy();
        }
    },

    _handleTap() {
        if (!this.hovered) return;
        if (this.mode === 'galaxies') {
            // 顶层多星系 → 点击某个星系进入
            this._enterGalaxy(this.hovered);
        } else if (this.mode === 'galaxy') {
            if (this.hovered === '__center') {
                this._exitGalaxy();
            } else {
                this._enterSubject(this.hovered);
            }
        } else {
            // subject 模式
            if (this.hovered === '__center') {
                this._exitSubject();
            } else {
                this._enterExperiment(this.hovered);
            }
        }
    },

    // ── v5.0：顶层多星系 ──
    _buildGalaxies() {
        const fromCfg = (typeof CONFIG !== 'undefined' && CONFIG.galaxies) ? CONFIG.galaxies : [];
        // 默认 fallback：只列出工科实验室
        const list = fromCfg.length ? fromCfg : [{
            id: 'englab', label: '工科实验室', tagline: 'ENGINEERING · LAB',
            desc: '五大学科 65 个可视化实验', color: '#3aa9ff',
            subjects: ['mathematics', 'physics', 'chemistry', 'algorithms', 'biology']
        }];
        const N = list.length;
        this.galaxies = list.map((g, i) => ({
            id: g.id, label: g.label, tagline: g.tagline || '', desc: g.desc || '',
            color: g.color || '#3aa9ff',
            subjectIds: g.subjects || [],
            externalUrl: g.externalUrl || null,
            // 均匀分布在水平平面上
            angle: N === 1 ? 0 : (i / N) * Math.PI * 2,
            phase: i * 1.13,
            // 这个星系的“资产”数量——实验总数（外链星系不计算）
            count: g.externalUrl ? 0 : (g.subjects || []).reduce((acc, sid) => {
                const exps = (typeof CONFIG !== 'undefined' && CONFIG.experiments && CONFIG.experiments[sid]) || [];
                return acc + exps.length;
            }, 0)
        }));
    },

    _galaxyPos(g) {
        // 多个星系水平平铺：半径 r，合适间距
        const r = this.galaxies.length === 1 ? 0 : 1.5;
        return {
            x: r * Math.cos(g.angle),
            y: 0,
            z: r * Math.sin(g.angle)
        };
    },

    _enterGalaxy(g) {
        if (!g) return;
        // 外链星系：直接跳转到子站，不进入 galaxy 展开模式
        if (g.externalUrl) {
            window.location.href = g.externalUrl;
            return;
        }
        this.currentGalaxy = g;
        // 将子学科映射为有角度的行星
        const ids = g.subjectIds || [];
        const N = ids.length || 1;
        this.subjects = ids.map((sid, i) => {
            const meta = this._allSubjects[sid] || { id: sid, label: sid, desc: '', color: '#3aa9ff' };
            return Object.assign({}, meta, {
                angle: N === 1 ? 0 : (i / N) * Math.PI * 2
            });
        });
        this.mode = 'galaxy';
        this.tGTarget = 1;
        this.tInTarget = 0;
        this.autoRotate = true;
        this.targetPitch = -0.15;
        this.hovered = null;
        this._updateChrome();
        this._updateInfo();
    },

    _exitGalaxy() {
        if (this.mode !== 'galaxy') return;
        this.mode = 'galaxies';
        this.currentGalaxy = null;
        this.subjects = [];
        this.tGTarget = 0;
        this.tG = 0;
        this.hovered = null;
        this._updateChrome();
        this._updateInfo();
    },

    // ── v4.4 子星系：进入学科 ──
    _enterSubject(subject) {
        if (!subject) return;
        // v5.1.1：行星带 externalUrl 时直跳子站，不进入子星系展开
        if (subject.externalUrl) {
            window.location.href = subject.externalUrl;
            return;
        }
        this.currentSubject = subject;
        this._buildSatellites(subject.id);
        this.mode = 'subject';
        this.tInTarget = 1;
        this.autoRotate = true;          // 缓慢自转保持沉浸
        this.targetPitch = -0.05;        // 略平视
        this.hovered = null;
        this.subjTime = 0;
        this._updateChrome();
        this._updateInfo();
    },

    _exitSubject() {
        if (this.mode !== 'subject') return;
        if (this.exiting) return;
        if (this.launchingSat) return; // 跳转中不允许退出
        // 启动 zoom-out 动画：中央恒星爆发手发散，卫星被推到边缘
        this.exiting = true;
        this.tOut = 0;
        this.hovered = null;
        this._updateInfo();
        // tIn 仍保持 1，让子星系层继续可见以呈现动画
    },

    _finalizeExitSubject() {
        // 动画结束：真正切回 galaxy 模式
        this.mode = 'galaxy';
        this.currentSubject = null;
        this.satellites = [];
        this.tInTarget = 0;
        this.tIn = 0;            // 仅这一屏直接跳到 galaxy（主星系从隐 →显 由 _draw 控制）
        this.exiting = false;
        this.tOut = 0;
        this.hovered = null;
        this._updateChrome();
        this._updateInfo();
    },

    _enterExperiment(sat) {
        if (!sat || !this.currentSubject) return;
        if (this.shattering) return; // 防重点
        const subjectId = this.currentSubject.id;
        const expId = sat.id;
        // v5.0：用“星球破碎扩散”替代原先的 zoom-into-satellite 动画
        const pos = this._satellitePos(sat);
        const proj = this._project(pos.x, pos.y, pos.z);
        this.shattering = true;
        this.shatterTime = 0;
        this.shatterX = proj.x;
        this.shatterY = proj.y;
        this.shatterColor = (this.currentSubject && this.currentSubject.color) || '#3aa9ff';
        const baseR = Math.max(18, 34 * proj.scale / 200);
        const N = 72;
        this.shatterParticles = [];
        for (let i = 0; i < N; i++) {
            const ang = Math.random() * Math.PI * 2;
            const spd = 220 + Math.random() * 520; // px/s
            this.shatterParticles.push({
                x: proj.x + (Math.random() - 0.5) * baseR * 0.4,
                y: proj.y + (Math.random() - 0.5) * baseR * 0.4,
                vx: Math.cos(ang) * spd,
                vy: Math.sin(ang) * spd,
                size: 1.6 + Math.random() * 4,
                life: 0.55 + Math.random() * 0.35, // 秒
                age: 0,
                rot: Math.random() * Math.PI,
                spin: (Math.random() - 0.5) * 6
            });
        }
        // 使原唵 launchingSat 不生效
        this.launchingSat = null;
        this.autoRotate = false;
        // 破碎 → 跳转：~620ms 后 hash 切，再等 router 转场后打开实验
        clearTimeout(this._navTimer);
        this._navTimer = setTimeout(() => {
            window.location.hash = '#' + subjectId;
            setTimeout(() => {
                if (typeof ModuleSelector !== 'undefined' && typeof ModuleSelector.openModule === 'function') {
                    try { ModuleSelector.openModule(subjectId, expId); } catch (err) { /* noop */ }
                }
                this.shattering = false;
                this.shatterParticles = [];
            }, 600);
        }, 620);
    },

    _buildSatellites(subjectId) {
        const exps = (typeof CONFIG !== 'undefined' && CONFIG.experiments && CONFIG.experiments[subjectId]) || [];
        const list = exps.filter(e => e.variant !== 'upcoming');
        const N = list.length || 1;
        // 双环分布：偶数索引内环，奇数索引外环，避免拥挤
        this.satellites = list.map((e, i) => {
            const ring = i % 2 === 0 ? 0 : 1;
            const radius = ring === 0 ? 1.10 : 1.65;   // v44c：外环远一点，拉开层次
            // 同一环内均匀分布
            const sameRingItems = list.filter((_, j) => (j % 2) === ring).length || 1;
            const idxInRing = Math.floor(i / 2);
            const angle = (idxInRing / sameRingItems) * Math.PI * 2 + (ring === 1 ? Math.PI / sameRingItems : 0);
            return {
                id: e.id,
                title: e.title || e.id,
                desc: e.description || '',
                icon: e.icon || 'box',
                radius,
                angle,
                yJitter: ((i % 5) - 2) * 0.04,           // v44c：垂直抖动变弱，轨道更平
                ring
            };
        });
    },

    _satellitePos(sat) {
        // 卫星按自身轨道时间缓慢公转；外环慢一些
        const speed = sat.ring === 0 ? 0.00018 : 0.00012;
        const a = sat.angle + this.subjTime * speed;
        return {
            x: sat.radius * Math.cos(a),
            y: sat.yJitter,
            z: sat.radius * Math.sin(a)
        };
    },

    _updateChrome() {
        // 切换 HUD 中的标题/提示文案
        const title = document.querySelector('#page-planets .planets-title');
        const hudBL = document.querySelector('#page-planets .planets-hud--bl');
        const hudTL = document.querySelector('#page-planets .planets-hud--tl');
        if (this.mode === 'subject' && this.currentSubject) {
            const s = this.currentSubject;
            const gLabel = (this.currentGalaxy && this.currentGalaxy.label) || '主星系';
            if (title) {
                title.innerHTML = `
                    <div class="planets-crumb-row">
                        <button type="button" class="planets-crumb planets-crumb--root" data-action="back-to-galaxies" aria-label="返回多星系">多星系</button>
                        <span class="planets-crumb-sep">›</span>
                        <button type="button" class="planets-crumb planets-crumb--galaxy" data-action="back-to-galaxy" aria-label="返回 ${gLabel}">${gLabel}</button>
                        <span class="planets-crumb-sep">›</span>
                        <span class="planets-crumb planets-crumb--subject">${s.label}</span>
                        <span class="planets-crumb-sep planets-crumb-sep--exp" data-exp-sep>·</span>
                        <span class="planets-crumb planets-crumb--exp" data-exp-name></span>
                    </div>
                    <div class="planets-subtitle">TAP SATELLITE TO ENTER · ESC RETURN</div>
                `;
                title.querySelectorAll('[data-action="back-to-galaxy"]').forEach(b => b.addEventListener('click', () => this._exitSubject()));
                title.querySelectorAll('[data-action="back-to-galaxies"]').forEach(b => b.addEventListener('click', () => { this._exitSubject(); setTimeout(() => this._exitGalaxy(), 420); }));
            }
            if (hudBL) hudBL.innerHTML = '<div>← DRAG TO ROTATE</div><div>TAP SATELLITE / ESC RETURN</div>';
            if (hudTL) hudTL.innerHTML = `<div><span class="blink">●</span> ${s.id.toUpperCase()}.SCAN</div><div>MODE: SUB-ORBIT</div><div>NODES: ${this.satellites.length}</div>`;
        } else if (this.mode === 'galaxy' && this.currentGalaxy) {
            const g = this.currentGalaxy;
            if (title) {
                title.innerHTML = `
                    <div class="planets-crumb-row">
                        <button type="button" class="planets-crumb planets-crumb--root" data-action="back-to-galaxies" aria-label="返回多星系">多星系</button>
                        <span class="planets-crumb-sep">›</span>
                        <span class="planets-crumb planets-crumb--galaxy">${g.label}</span>
                    </div>
                    <div class="planets-subtitle">TAP PLANET TO ENTER · ESC RETURN</div>
                `;
                title.querySelectorAll('[data-action="back-to-galaxies"]').forEach(b => b.addEventListener('click', () => this._exitGalaxy()));
            }
            if (hudBL) hudBL.innerHTML = '<div>← DRAG TO ROTATE</div><div>TAP PLANET / ESC RETURN</div>';
            if (hudTL) hudTL.innerHTML = `<div><span class="blink">●</span> ${g.id.toUpperCase()}.GALAXY</div><div>MODE: ORBIT</div><div>NODES: ${this.subjects.length}</div>`;
        } else {
            // galaxies
            if (title) {
                title.innerHTML = `多 星 系 导 航<div class="planets-subtitle">GALAXY · CLUSTER · MAP</div>`;
            }
            if (hudBL) hudBL.innerHTML = '<div>← DRAG TO ROTATE</div><div>TAP GALAXY TO ENTER</div>';
            if (hudTL) hudTL.innerHTML = `<div><span class="blink">●</span> SYS.SCAN</div><div>MODE: CLUSTER</div><div>GALAXIES: ${this.galaxies.length}</div>`;
        }
    },

    _updateBreadcrumbExp(text) {
        const expEl = document.querySelector('#page-planets .planets-crumb--exp');
        const sepEl = document.querySelector('#page-planets [data-exp-sep]');
        if (expEl) expEl.textContent = text || '';
        if (sepEl) sepEl.style.opacity = text ? '0.55' : '0';
    },

    _project(x, y, z) {
        // rotate around Y (yaw) then X (pitch)
        const cy = Math.cos(this.yaw), sy = Math.sin(this.yaw);
        const cp = Math.cos(this.pitch), sp = Math.sin(this.pitch);
        let x1 = x * cy - z * sy;
        let z1 = x * sy + z * cy;
        let y1 = y * cp - z1 * sp;
        let z2 = y * sp + z1 * cp;
        // perspective
        const fov = Math.min(this.W, this.H) * 0.45;
        const camZ = 3;
        const scale = fov / (camZ - z2);
        return {
            x: this.W / 2 + x1 * scale,
            y: this.H / 2 + y1 * scale,
            z: z2,
            scale: scale
        };
    },

    _planetPos(subject) {
        const r = 1.4;
        return {
            x: r * Math.cos(subject.angle),
            y: 0,
            z: r * Math.sin(subject.angle)
        };
    },

    _updateHover(mx, my) {
        this.hovered = null;
        if (this.mode === 'galaxies') {
            // 顶层：测试多个星系
            const projected = this.galaxies.map(g => {
                const p = this._galaxyPos(g);
                const proj = this._project(p.x, p.y, p.z);
                return { g, proj };
            }).sort((a, b) => b.proj.z - a.proj.z);
            for (const { g, proj } of projected) {
                const radius = Math.max(60, 120 * proj.scale / 200);
                const dx = mx - proj.x, dy = my - proj.y;
                if (dx * dx + dy * dy <= radius * radius) { this.hovered = g; break; }
            }
        } else if (this.mode === 'galaxy' || this.tIn < 0.5) {
            // 主星系：先测中心返回区，再测试学科行星
            const cx = this.W / 2, cy = this.H / 2;
            const centerR = Math.min(this.W, this.H) * 0.055;
            const dxc = mx - cx, dyc = my - cy;
            if (this.mode === 'galaxy' && dxc * dxc + dyc * dyc <= centerR * centerR) {
                this.hovered = '__center';
            } else {
                const projected = this.subjects.map(s => {
                    const p = this._planetPos(s);
                    const proj = this._project(p.x, p.y, p.z);
                    return { s, proj };
                }).sort((a, b) => b.proj.z - a.proj.z);
                for (const { s, proj } of projected) {
                    const radius = Math.max(28, 60 * proj.scale / 200);
                    const dx = mx - proj.x, dy = my - proj.y;
                    if (dx * dx + dy * dy <= radius * radius) { this.hovered = s; break; }
                }
            }
        } else {
            // 子星系：先测试中央返回区，再测试卫星
            const cx = this.W / 2, cy = this.H / 2;
            const centerR = Math.min(this.W, this.H) * 0.085;
            const dxc = mx - cx, dyc = my - cy;
            if (dxc * dxc + dyc * dyc <= centerR * centerR) {
                this.hovered = '__center';
            } else {
                const projected = this.satellites.map(sat => {
                    const p = this._satellitePos(sat);
                    const proj = this._project(p.x, p.y, p.z);
                    return { sat, proj };
                }).sort((a, b) => b.proj.z - a.proj.z);
                for (const { sat, proj } of projected) {
                    const radius = Math.max(22, 40 * proj.scale / 200);
                    const dx = mx - proj.x, dy = my - proj.y;
                    if (dx * dx + dy * dy <= radius * radius) { this.hovered = sat; break; }
                }
            }
        }
        this.canvas.style.cursor = this.hovered ? 'pointer' : (this.isDragging ? 'grabbing' : 'grab');
        this._updateInfo();
    },

    _updateInfo() {
        if (!this.info) return;
        const labelEl = this.info.querySelector('.planets-info__label');
        const nameEl = this.info.querySelector('.planets-info__name');
        const descEl = this.info.querySelector('.planets-info__desc');
        const hintEl = this.info.querySelector('.planets-info__hint');
        if (!this.hovered) {
            this.info.classList.remove('planets-info--visible');
            if (this.mode === 'subject') this._updateBreadcrumbExp('');
            return;
        }
        this.info.classList.add('planets-info--visible');
        if (this.mode === 'galaxies' && this.hovered && this.hovered.subjectIds) {
            // 多星系级：hover 某个星系
            if (labelEl) labelEl.textContent = 'GALAXY';
            if (nameEl) nameEl.textContent = this.hovered.label;
            if (descEl) descEl.textContent = `${this.hovered.tagline || ''}　${this.hovered.desc || ''}`.trim();
            if (hintEl) {
                hintEl.textContent = this.hovered.externalUrl
                    ? 'OPEN SUBSITE →'
                    : `CLICK TO ENTER →  (${this.hovered.count || 0} EXP)`;
            }
            this.info.style.borderLeftColor = this.hovered.color;
        } else if (this.mode === 'galaxy' && this.hovered === '__center') {
            // 子星系主星 → 返回多星系
            if (labelEl) labelEl.textContent = 'NAVIGATION';
            if (nameEl) nameEl.textContent = '返回多星系';
            if (descEl) descEl.textContent = '点击中央或 ESC 返回顶层多星系';
            if (hintEl) hintEl.textContent = '← BACK TO GALAXIES';
            this.info.style.borderLeftColor = (this.currentGalaxy && this.currentGalaxy.color) || '#3aa9ff';
        } else if (this.mode === 'galaxy' && this.hovered && this.hovered.id) {
            // 学科
            if (labelEl) labelEl.textContent = 'SUBJECT';
            if (nameEl) nameEl.textContent = this.hovered.label;
            if (descEl) descEl.textContent = this.hovered.desc;
            if (hintEl) hintEl.textContent = 'CLICK TO ENTER →';
            this.info.style.borderLeftColor = this.hovered.color;
        } else if (this.mode === 'subject' && this.hovered === '__center') {
            // 中央返回区
            if (labelEl) labelEl.textContent = 'NAVIGATION';
            if (nameEl) nameEl.textContent = '返回星系';
            if (descEl) descEl.textContent = '点击中央或 ESC 返回主星系';
            if (hintEl) hintEl.textContent = '← BACK TO GALAXY';
            this.info.style.borderLeftColor = (this.currentSubject && this.currentSubject.color) || '#3aa9ff';
            this._updateBreadcrumbExp('');
        } else if (this.mode === 'subject' && this.hovered && this.hovered.id) {
            // 卫星实验
            if (labelEl) labelEl.textContent = 'EXPERIMENT';
            if (nameEl) nameEl.textContent = this.hovered.title;
            if (descEl) descEl.textContent = this.hovered.desc || '';
            if (hintEl) hintEl.textContent = 'CLICK TO LAUNCH →';
            this.info.style.borderLeftColor = (this.currentSubject && this.currentSubject.color) || '#3aa9ff';
            this._updateBreadcrumbExp(this.hovered.title);
        }
    },

    _loop(t) {
        const dt = Math.min(50, t - this.lastT);
        this.lastT = t;

        if (this.autoRotate) {
            this.targetYaw += this.autoYawSpeed * dt;
        }

        // ease yaw/pitch toward target
        this.yaw += (this.targetYaw - this.yaw) * 0.12;
        this.pitch += (this.targetPitch - this.pitch) * 0.12;

        // 过渡动画：tIn 以缓动靠近 tInTarget（v44c：节奏略快）
        this.tIn += (this.tInTarget - this.tIn) * 0.15;
        if (Math.abs(this.tIn - this.tInTarget) < 0.001) this.tIn = this.tInTarget;
        // v5.0：galaxies ↔ galaxy 过渡
        this.tG += (this.tGTarget - this.tG) * 0.15;
        if (Math.abs(this.tG - this.tGTarget) < 0.001) this.tG = this.tGTarget;
        // v5.0：破碎动画推进与粒子更新
        if (this.shattering) {
            this.shatterTime += dt;
            const sec = dt / 1000;
            for (const p of this.shatterParticles) {
                p.age += sec;
                p.x += p.vx * sec;
                p.y += p.vy * sec;
                p.vx *= 0.96;
                p.vy *= 0.96;
                p.rot += p.spin * sec;
            }
        }
        // 全局时间计数
        this.galTime += dt;
        // v5.0：顶层星系入场进度
        if (this.tEnter < 1) {
            this.tEnter = Math.min(1, (t - this.enterStart) / 1400);
        }
        // v4.4-α5：zoom-into-satellite 动画推进（线性以保证可预测的 480ms）
        if (this.launchingSat) {
            this.tLaunch = Math.min(1, this.tLaunch + dt / 480);
        }
        // v4.4-α8：zoom-out 退出子星系动画（380ms）
        if (this.exiting) {
            this.tOut = Math.min(1, this.tOut + dt / 380);
            if (this.tOut >= 1) this._finalizeExitSubject();
        }
        // 子星系时间坑（仅 subject 状态下推进）
        if (this.mode === 'subject' || this.tIn > 0) this.subjTime += dt;

        this._draw();
        this.rafId = requestAnimationFrame(this._loop);
    },

    _draw() {
        const ctx = this.ctx;
        // backdrop (拖尾叠加)
        ctx.fillStyle = 'rgba(0,5,8,0.4)';
        ctx.fillRect(0, 0, this.W, this.H);

        // background stars
        for (const star of this.stars) {
            const p = this._project(star.x * 4, star.y * 4, star.z * 4 - 1);
            const sz = Math.max(0.3, 1.4 * p.scale / 200);
            ctx.globalAlpha = star.a * Math.min(1, p.scale / 200);
            ctx.fillStyle = '#7ce7d5';
            ctx.fillRect(p.x, p.y, sz, sz);
        }
        ctx.globalAlpha = 1;

        const cx = this.W / 2, cy = this.H / 2;
        const aGalaxies = 1 - this.tG;              // v5.0 顶层多星系
        const aGalaxy = this.tG * (1 - this.tIn);   // 中层 单星系主视图
        const aSubject = this.tIn;                  // 子星系层

        // ── v5.0：多星系顶层 ──────────────────────
        if (aGalaxies > 0.02 && this.galaxies.length) {
            ctx.save();
            // v5.0：错峰入场——每个星系有独立的延迟 + ease-out
            const N = this.galaxies.length;
            const items = this.galaxies.map((g, i) => {
                const pos = this._galaxyPos(g);
                const proj = this._project(pos.x, pos.y, pos.z);
                const delay = (N <= 1) ? 0 : (i * 0.18);
                const span = Math.max(0.45, 1 - delay);
                const local = Math.max(0, Math.min(1, (this.tEnter - delay) / span));
                const ease = 1 - Math.pow(1 - local, 3); // ease-out cubic
                return { g, proj, enter: ease };
            }).sort((a, b) => a.proj.z - b.proj.z);
            // 第一趟：按 z 由远及近画星系本体（互相遮挡正常）
            for (const { g, proj, enter } of items) {
                ctx.globalAlpha = aGalaxies * enter;
                this._drawSpiralGalaxyBody(ctx, g, proj, this.mode === 'galaxies' && this.hovered === g, enter);
            }
            // 第二趟：统一画标签于最上层，避免被前景星系遮挡
            for (const { g, proj, enter } of items) {
                ctx.globalAlpha = aGalaxies * enter;
                this._drawSpiralGalaxyLabel(ctx, g, proj, this.mode === 'galaxies' && this.hovered === g);
            }
            ctx.globalAlpha = aGalaxies;
            ctx.restore();
        }

        // ── 主星系层（galaxy）────────────────────────
        if (aGalaxy > 0.02) {
            ctx.save();
            ctx.globalAlpha = aGalaxy;

            const isCenterHover = this.mode === 'galaxy' && this.hovered === '__center';
            const galaxyAccent = (this.currentGalaxy && this.currentGalaxy.color) || '#3aa9ff';
            // central core
            const coreR = Math.min(this.W, this.H) * 0.06;
            const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 2);
            grad.addColorStop(0, this._hexA(galaxyAccent, isCenterHover ? 0.55 : 0.40));
            grad.addColorStop(0.5, this._hexA(galaxyAccent, 0.10));
            grad.addColorStop(1, this._hexA(galaxyAccent, 0));
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(cx, cy, coreR * 2, 0, Math.PI * 2);
            ctx.fill();

            ctx.strokeStyle = isCenterHover ? '#3aa9ff' : this._hexA(galaxyAccent, 0.65);
            ctx.lineWidth = isCenterHover ? 2.2 : 1.5;
            ctx.beginPath();
            ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
            ctx.stroke();
            if (this.mode === 'galaxy') {
                ctx.fillStyle = isCenterHover ? '#3aa9ff' : this._hexA(galaxyAccent, 0.85);
                ctx.font = `${Math.max(9, coreR * 0.26)}px var(--font-mono, monospace)`;
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('« BACK', cx, cy);
            }

            // 主轨道环
            ctx.strokeStyle = this._hexA(galaxyAccent, 0.18);
            ctx.lineWidth = 1;
            ctx.setLineDash([4, 6]);
            ctx.beginPath();
            const r = 1.4;
            const seg = 80;
            for (let i = 0; i <= seg; i++) {
                const a = (i / seg) * Math.PI * 2;
                const p = this._project(r * Math.cos(a), 0, r * Math.sin(a));
                if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
            }
            ctx.stroke();
            ctx.setLineDash([]);

            // planets
            const items = this.subjects.map(s => {
                const pos = this._planetPos(s);
                const proj = this._project(pos.x, pos.y, pos.z);
                return { s, proj };
            }).sort((a, b) => a.proj.z - b.proj.z);

            for (const { s, proj } of items) {
                this._drawPlanet(ctx, s, proj, this.mode === 'galaxy' && this.hovered === s);
            }

            ctx.restore();
        }

        // ── 子星系层（subject）──────────────────────
        if (aSubject > 0.02 && this.currentSubject) {
            ctx.save();
            // launch 时其他元素逐渐淡出；zoom-out 退出时同样逐渐透明
            const subAlpha = aSubject * (1 - this.tLaunch * 0.85) * (1 - this.tOut * 0.65);
            ctx.globalAlpha = subAlpha;

            const s = this.currentSubject;
            // 中央放大的"恒星"——当前学科
            const sunR = Math.min(this.W, this.H) * 0.085;
            const sunGlow = ctx.createRadialGradient(cx, cy, 0, cx, cy, sunR * 2.4);
            const isCenterHover = this.hovered === '__center';
            sunGlow.addColorStop(0, this._hexA(s.color, isCenterHover ? 0.55 : 0.40));
            sunGlow.addColorStop(0.5, this._hexA(s.color, 0.15));
            sunGlow.addColorStop(1, this._hexA(s.color, 0));
            ctx.fillStyle = sunGlow;
            ctx.beginPath();
            ctx.arc(cx, cy, sunR * 2.4, 0, Math.PI * 2);
            ctx.fill();

            ctx.fillStyle = 'rgba(0,18,40,0.85)';
            ctx.beginPath();
            ctx.arc(cx, cy, sunR, 0, Math.PI * 2);
            ctx.fill();

            ctx.strokeStyle = isCenterHover ? '#3aa9ff' : this._hexA(s.color, 0.85);
            ctx.lineWidth = isCenterHover ? 2.4 : 1.8;
            ctx.beginPath();
            ctx.arc(cx, cy, sunR, 0, Math.PI * 2);
            ctx.stroke();

            // 中央学科名字
            ctx.fillStyle = isCenterHover ? '#3aa9ff' : 'rgba(212,232,255,0.95)';
            ctx.font = `bold ${Math.max(14, sunR * 0.32)}px var(--font-display, system-ui)`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(s.label, cx, cy - 2);
            ctx.font = `${Math.max(9, sunR * 0.16)}px var(--font-mono, monospace)`;
            ctx.fillStyle = 'rgba(58,169,255,0.7)';
            ctx.fillText('BACK · ESC', cx, cy + sunR * 0.42);

            // 卫星轨道环（双环，与 _buildSatellites 半径保持一致）
            for (const ringR of [1.10, 1.65]) {
                ctx.strokeStyle = 'rgba(58,169,255,0.12)';
                ctx.lineWidth = 1;
                ctx.setLineDash([3, 6]);
                ctx.beginPath();
                const seg = 72;
                for (let i = 0; i <= seg; i++) {
                    const a = (i / seg) * Math.PI * 2;
                    const p = this._project(ringR * Math.cos(a), 0, ringR * Math.sin(a));
                    if (i === 0) ctx.moveTo(p.x, p.y); else ctx.lineTo(p.x, p.y);
                }
                ctx.stroke();
                ctx.setLineDash([]);
            }

            // 卫星 — 按深度排序
            const satItems = this.satellites.map(sat => {
                const pos = this._satellitePos(sat);
                const proj = this._project(pos.x, pos.y, pos.z);
                return { sat, proj };
            }).sort((a, b) => a.proj.z - b.proj.z);

            for (const { sat, proj } of satItems) {
                if (sat === this.launchingSat) continue;   // launch 中的卫星单独绘制
                let p = proj;
                if (this.exiting) {
                    const ease = 1 - Math.pow(1 - this.tOut, 3); // ease-out cubic
                    const dx = proj.x - cx, dy = proj.y - cy;
                    const k = 1 + ease * 2.6;
                    p = { x: cx + dx * k, y: cy + dy * k, z: proj.z, scale: proj.scale * (1 - ease * 0.4) };
                }
                this._drawSatellite(ctx, sat, p, this.hovered === sat, s.color);
            }

            ctx.restore();

            // ── v4.4-α5：launch 卫星单独画在最上层，不受 subAlpha 影响 ──
            if (this.launchingSat && this.satellites.includes(this.launchingSat)) {
                const sat = this.launchingSat;
                const t = this.tLaunch;            // 0~1
                const ease = 1 - Math.pow(1 - t, 3); // ease-out cubic
                // 起点：原投影位置；终点：屏幕中心、放大 ~10x
                const pos = this._satellitePos(sat);
                const projStart = this._project(pos.x, pos.y, pos.z);
                const startX = projStart.x, startY = projStart.y;
                const endX = cx, endY = cy;
                const px = startX + (endX - startX) * ease;
                const py = startY + (endY - startY) * ease;
                const baseR = Math.max(18, 34 * projStart.scale / 200);
                const radius = baseR * (1 + ease * 9);

                // 强光晕扩散
                const flashR = radius * (1.4 + ease * 1.5);
                const flash = ctx.createRadialGradient(px, py, 0, px, py, flashR);
                flash.addColorStop(0, this._hexA(s.color, 0.85 * (1 - ease * 0.3)));
                flash.addColorStop(0.4, this._hexA(s.color, 0.3));
                flash.addColorStop(1, this._hexA(s.color, 0));
                ctx.fillStyle = flash;
                ctx.beginPath();
                ctx.arc(px, py, flashR, 0, Math.PI * 2);
                ctx.fill();

                // 本体（淡出到接近全白）
                const bodyAlpha = 0.85 - ease * 0.4;
                ctx.fillStyle = `rgba(0,12,28,${bodyAlpha})`;
                ctx.beginPath();
                ctx.arc(px, py, radius, 0, Math.PI * 2);
                ctx.fill();

                ctx.strokeStyle = '#3aa9ff';
                ctx.lineWidth = 2 + ease * 2;
                ctx.beginPath();
                ctx.arc(px, py, radius, 0, Math.PI * 2);
                ctx.stroke();

                // 中心高亮点（几乎填满屏幕的暖色光环）
                if (ease > 0.5) {
                    const overlay = ctx.createRadialGradient(cx, cy, 0, cx, cy, Math.hypot(this.W, this.H));
                    const a2 = (ease - 0.5) * 2;          // 0.5→1 映射 0→1
                    overlay.addColorStop(0, this._hexA(s.color, 0.35 * a2));
                    overlay.addColorStop(0.6, 'rgba(0,5,8,0)');
                    overlay.addColorStop(1, 'rgba(0,5,8,0)');
                    ctx.fillStyle = overlay;
                    ctx.fillRect(0, 0, this.W, this.H);
                }
            }

            // ── v4.4-α8：zoom-out 中央外扩闪光（退出子星系动画）──
            if (this.exiting && this.currentSubject) {
                const e = this.tOut;
                const eEase = 1 - Math.pow(1 - e, 2); // ease-out quadratic
                const sunR = Math.min(this.W, this.H) * 0.085;
                // 中央实心爆发：越来越大、但 alpha 逐渐衰减
                const burstR = sunR * (1 + eEase * 6);
                const burstA = (1 - e) * 0.6;
                ctx.fillStyle = this._hexA(s.color, burstA);
                ctx.beginPath();
                ctx.arc(cx, cy, burstR, 0, Math.PI * 2);
                ctx.fill();
                // 环状冲击波：从中央向外扩散的光环
                const ringR = sunR + (Math.hypot(this.W, this.H) * 0.55) * eEase;
                const ringW = Math.max(2, 30 * (1 - e));
                ctx.strokeStyle = this._hexA(s.color, 0.55 * (1 - e));
                ctx.lineWidth = ringW;
                ctx.beginPath();
                ctx.arc(cx, cy, ringR, 0, Math.PI * 2);
                ctx.stroke();
                // 软光蒃染：填充整个屏幕的弱彩调
                const veil = ctx.createRadialGradient(cx, cy, sunR * 0.3, cx, cy, Math.hypot(this.W, this.H));
                veil.addColorStop(0, this._hexA(s.color, 0.18 * (1 - e)));
                veil.addColorStop(0.6, this._hexA(s.color, 0.05 * (1 - e)));
                veil.addColorStop(1, 'rgba(0,5,8,0)');
                ctx.fillStyle = veil;
                ctx.fillRect(0, 0, this.W, this.H);
            }
        }

        // ── v5.0：星球破碎粒子（最顶层）──────────
        if (this.shattering && this.shatterParticles.length) {
            ctx.save();
            // 中心闪光
            const flashLife = 280;
            if (this.shatterTime < flashLife) {
                const fE = this.shatterTime / flashLife;
                const fR = Math.min(this.W, this.H) * (0.06 + fE * 0.5);
                const fGrad = ctx.createRadialGradient(this.shatterX, this.shatterY, 0, this.shatterX, this.shatterY, fR);
                fGrad.addColorStop(0, this._hexA(this.shatterColor, 0.85 * (1 - fE)));
                fGrad.addColorStop(0.5, this._hexA(this.shatterColor, 0.3 * (1 - fE)));
                fGrad.addColorStop(1, this._hexA(this.shatterColor, 0));
                ctx.fillStyle = fGrad;
                ctx.fillRect(0, 0, this.W, this.H);
            }
            for (const p of this.shatterParticles) {
                const t = p.age / p.life;
                if (t >= 1) continue;
                const a = (1 - t) * (1 - t);
                ctx.globalAlpha = a;
                ctx.fillStyle = p.color || this.shatterColor;
                ctx.save();
                ctx.translate(p.x, p.y);
                ctx.rotate(p.rot);
                const sz = p.size * (1 - t * 0.3);
                ctx.fillRect(-sz / 2, -sz / 2, sz, sz);
                ctx.restore();
            }
            ctx.restore();
        }
    },

    _drawSpiralGalaxy(ctx, g, proj, isHover) {
        // v5.0：保留入口以兼容；_draw 主路径已拆分为 body + label 两阶段
        this._drawSpiralGalaxyBody(ctx, g, proj, isHover);
        this._drawSpiralGalaxyLabel(ctx, g, proj, isHover);
    },

    _drawSpiralGalaxyBody(ctx, g, proj, isHover, enter) {
        const cx = proj.x, cy = proj.y;
        // v5.0：入场阶段从 0.55× 缩放到 1.0×（默认 enter=1，不影响其他调用者）
        const e = (typeof enter === 'number') ? enter : 1;
        const scaleK = 0.55 + 0.45 * e;
        const baseR = Math.max(70, 130 * proj.scale / 200) * scaleK;
        const color = g.color || '#3aa9ff';

        // halo
        const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseR * 1.6);
        halo.addColorStop(0, this._hexA(color, isHover ? 0.42 : 0.28));
        halo.addColorStop(0.5, this._hexA(color, 0.10));
        halo.addColorStop(1, this._hexA(color, 0));
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(cx, cy, baseR * 1.6, 0, Math.PI * 2);
        ctx.fill();

        // spiral arms (logarithmic)
        const arms = 4;
        const twist = this.galTime * 0.00018 + (g.phase || 0);
        const b = 0.32;
        const pointsPerArm = 70;
        for (let k = 0; k < arms; k++) {
            const offset = (k / arms) * Math.PI * 2;
            for (let i = 1; i <= pointsPerArm; i++) {
                const t = i / pointsPerArm;
                const theta = t * Math.PI * 3 + offset + twist;
                const rr = baseR * 0.18 * Math.exp(b * t * Math.PI * 3);
                if (rr > baseR * 1.4) break;
                const px = cx + rr * Math.cos(theta);
                const py = cy + rr * Math.sin(theta) * 0.45; // 椭扁压缩
                const a = (1 - t) * (isHover ? 0.85 : 0.55);
                const r = 1.5 + (1 - t) * 1.6;
                ctx.fillStyle = this._hexA(color, a);
                ctx.beginPath();
                ctx.arc(px, py, r, 0, Math.PI * 2);
                ctx.fill();
            }
        }

        // core
        const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, baseR * 0.32);
        core.addColorStop(0, this._hexA('#ffffff', 0.9));
        core.addColorStop(0.4, this._hexA(color, 0.85));
        core.addColorStop(1, this._hexA(color, 0));
        ctx.fillStyle = core;
        ctx.beginPath();
        ctx.arc(cx, cy, baseR * 0.32, 0, Math.PI * 2);
        ctx.fill();

        // hover ring
        if (isHover) {
            ctx.strokeStyle = '#3aa9ff';
            ctx.lineWidth = 2;
            ctx.setLineDash([4, 4]);
            ctx.beginPath();
            ctx.arc(cx, cy, baseR * 1.05, 0, Math.PI * 2);
            ctx.stroke();
            ctx.setLineDash([]);
        }
    },

    _drawSpiralGalaxyLabel(ctx, g, proj, isHover) {
        const cx = proj.x, cy = proj.y;
        const baseR = Math.max(70, 130 * proj.scale / 200);
        const color = g.color || '#3aa9ff';

        // label
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const mainFontSize = Math.max(13, baseR * 0.16);
        ctx.font = `${mainFontSize}px var(--font-mono, monospace)`;
        // 描边 + 阴影，保证在任何跟底上都可辨认
        ctx.shadowColor = 'rgba(0,0,0,0.85)';
        ctx.shadowBlur = 6;
        ctx.lineWidth = 3;
        ctx.strokeStyle = 'rgba(0,5,12,0.85)';
        ctx.strokeText(g.label || '', cx, cy + baseR * 0.7);
        ctx.shadowBlur = 0;
        ctx.fillStyle = isHover ? '#ffffff' : this._hexA(color, 0.95);
        ctx.fillText(g.label || '', cx, cy + baseR * 0.7);
        if (g.tagline) {
            const tagFontSize = Math.max(10, baseR * 0.1);
            ctx.font = `${tagFontSize}px var(--font-mono, monospace)`;
            ctx.shadowColor = 'rgba(0,0,0,0.85)';
            ctx.shadowBlur = 5;
            ctx.lineWidth = 2.5;
            ctx.strokeStyle = 'rgba(0,5,12,0.85)';
            ctx.strokeText(g.tagline, cx, cy + baseR * 0.7 + Math.max(16, baseR * 0.22));
            ctx.shadowBlur = 0;
            ctx.fillStyle = this._hexA(color, 0.6);
            ctx.fillText(g.tagline, cx, cy + baseR * 0.7 + Math.max(16, baseR * 0.22));
        }
        ctx.textBaseline = 'alphabetic';
    },

    _drawPlanet(ctx, s, proj, isHover) {
        const planetR = Math.max(20, 42 * proj.scale / 200);
        const depthFactor = (proj.z + 2) / 4;
        const alpha = 0.5 + 0.5 * Math.max(0.2, depthFactor);

        const glow = ctx.createRadialGradient(proj.x, proj.y, 0, proj.x, proj.y, planetR * 2.6);
        glow.addColorStop(0, this._hexA(s.color, isHover ? 0.45 : 0.22 * alpha));
        glow.addColorStop(1, this._hexA(s.color, 0));
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, planetR * 2.6, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = `rgba(0,18,40,${0.65 * alpha})`;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, planetR, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = isHover ? '#3aa9ff' : `rgba(58,169,255,${0.55 * alpha})`;
        ctx.lineWidth = isHover ? 2 : 1.2;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, planetR, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = `rgba(58,169,255,${0.35 * alpha})`;
        ctx.lineWidth = 0.8;
        ctx.beginPath();
        ctx.ellipse(proj.x, proj.y, planetR * 0.85, planetR * 0.25, 0, 0, Math.PI * 2);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(proj.x - planetR * 0.85, proj.y);
        ctx.lineTo(proj.x + planetR * 0.85, proj.y);
        ctx.moveTo(proj.x, proj.y - planetR * 0.85);
        ctx.lineTo(proj.x, proj.y + planetR * 0.85);
        ctx.stroke();

        ctx.fillStyle = this._hexA(s.color, alpha);
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, planetR * 0.18, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = isHover ? '#3aa9ff' : `rgba(212,232,255,${0.85 * alpha})`;
        ctx.font = `${isHover ? 'bold ' : ''}${Math.max(11, 14 * proj.scale / 200)}px var(--font-display, system-ui)`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(s.label, proj.x, proj.y + planetR + 10);
    },

    _drawSatellite(ctx, sat, proj, isHover, accent) {
        const satR = Math.max(18, 34 * proj.scale / 200);   // v44c：本体加大，点击热区更宽松
        const depthFactor = (proj.z + 2) / 4;
        const alpha = 0.5 + 0.5 * Math.max(0.25, depthFactor);

        // 微弱光晕
        const glow = ctx.createRadialGradient(proj.x, proj.y, 0, proj.x, proj.y, satR * 2.4);
        glow.addColorStop(0, this._hexA(accent, isHover ? 0.4 : 0.18 * alpha));
        glow.addColorStop(1, this._hexA(accent, 0));
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, satR * 2.4, 0, Math.PI * 2);
        ctx.fill();

        // 卫星本体
        ctx.fillStyle = `rgba(0,12,28,${0.78 * alpha})`;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, satR, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = isHover ? '#3aa9ff' : `rgba(58,169,255,${0.6 * alpha})`;
        ctx.lineWidth = isHover ? 2 : 1.1;
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, satR, 0, Math.PI * 2);
        ctx.stroke();

        // 中心点
        ctx.fillStyle = this._hexA(accent, alpha * 0.95);
        ctx.beginPath();
        ctx.arc(proj.x, proj.y, satR * 0.22, 0, Math.PI * 2);
        ctx.fill();

        // v44c：所有卫星都显示标签，背面以低透明度避免丢失信息
        const labelAlpha = isHover ? 1 : (depthFactor > 0.5 ? 0.85 * alpha : 0.45 * alpha);
        ctx.fillStyle = isHover ? '#3aa9ff' : `rgba(212,232,255,${labelAlpha})`;
        ctx.font = `${isHover ? 'bold ' : ''}${Math.max(11, 14 * proj.scale / 200)}px var(--font-display, system-ui)`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(sat.title, proj.x, proj.y + satR + 6);
    },

    _hexA(hex, a) {
        const h = hex.replace('#', '');
        const r = parseInt(h.substr(0, 2), 16);
        const g = parseInt(h.substr(2, 2), 16);
        const b = parseInt(h.substr(4, 2), 16);
        return `rgba(${r},${g},${b},${a})`;
    }
};

// initPlanets / destroyPlanets exposed for router
function initPlanets() { window.PlanetsView.init(); }
function destroyPlanets() { window.PlanetsView.destroy(); }

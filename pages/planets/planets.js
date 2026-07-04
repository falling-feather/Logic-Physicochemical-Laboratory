/* ═══════════════════════════════════════════════════════════════
   星序 Astra · 总览星图  v7.2 (qianduan · 环形拨盘)
   - 环形拓扑：三颗行星按 120° 均布在逻辑环上，走到尽头绕回第一颗
   - 待机自转：无操作时轮盘缓速自转（行星巡游 + 球面自旋）
   - 选中动画：行星放大飞至左侧定位点 → 介绍面板滑入
   - 性能：几何缓存 / visibilitychange 暂停 / 低端设备降级 / DPR 封顶
   契约: window.initPlanets / window.destroyPlanets 必须存在
   ═══════════════════════════════════════════════════════════════ */

(function () {
    'use strict';

    const TAU = Math.PI * 2;
    const DEG = Math.PI / 180;
    const RING = TAU / 3;          // 相邻行星在逻辑环上的间距 (120°)
    const VIS_K = 0.46;            // 逻辑角 → 视觉角压缩系数（±180° → ±83°扇区）
    const IDLE_SPEED = 0.000055;   // 待机自转角速度 (rad/ms)
    const LOW_END = (navigator.hardwareConcurrency || 8) <= 4 ||
                    (navigator.deviceMemory && navigator.deviceMemory <= 4);

    const lerp = (a, b, t) => a + (b - a) * t;
    const wrapPi = (a) => {
        while (a > Math.PI) a -= TAU;
        while (a < -Math.PI) a += TAU;
        return a;
    };

    const GALAXY_ORDER = ['codespace', 'englab', 'frontier'];

    const GALAXIES = {
        englab: {
            no: '02',
            title: '工科试验室',
            en: 'Engineering Lab',
            copy: '进入工科试验室后，再选择数学、物理、化学、算法或生物。',
            modules: [
                ['总览', '#home'],
                ['数学', '#mathematics'],
                ['物理', '#physics'],
                ['化学', '#chemistry'],
                ['算法', '#algorithms'],
                ['生物', '#biology']
            ]
        },
        codespace: {
            no: '01',
            title: '代码空间',
            en: 'Code Space',
            copy: '进入代码空间后，再选择代码追踪或语言运行方向。',
            modules: [
                ['首页', 'codevis/index.html#home'],
                ['代码追踪', 'codevis/index.html#trace'],
                ['JavaScript', 'codevis/index.html#trace'],
                ['Python', 'codevis/index.html#trace'],
                ['C / C++', 'codevis/index.html#trace']
            ]
        },
        frontier: {
            no: '03',
            title: '未来星系',
            en: 'Frontier',
            state: '学习方向',
            copy: '跨学科入口由未来星系独立承载：先看学习主线，再进入材料样板路线和其他学科总览。',
            modules: [
                { label: '学习主线', href: '#frontier-frontier-route', meta: '星序 → 未来星系 → 材料微观' },
                { label: '材料样板路线', href: '#frontier-materials-route', meta: '尺度桥 · 实验台 · 状态回查' },
                { label: '未来星系总览', href: '#frontier', meta: '星系坐标 · 二级目录' },
                { label: '地球与宇宙科学', href: '#cosmos', meta: '季节变化 · 太阳高度' },
                { label: '工程应用', href: '#engineering', meta: '桥梁受力 · 入门实验' },
                { label: '数据科学与 AI', href: '#datascience', meta: '线性回归 · 模型训练' },
                { label: '信息技术基础', href: '#infotech', meta: '网络分层 · 数据包旅程' },
                { label: '材料与微观结构', href: '#materials', meta: '晶体结构 · 晶粒边界' },
                { label: '语言/人文可视化', href: '#humanities', meta: '文本结构 · 史料脉络' }
            ]
        }
    };

    /* ───────────────────── 星场引擎（Canvas 背景层） ───────────────────── */
    const StarfieldEngine = {
        canvas: null, ctx: null,
        W: 0, H: 0, dpr: 1,
        stars: [],
        meteors: [],
        nebulae: [],
        mouse: { x: -9999, y: -9999, tx: -9999, ty: -9999 },
        reduceMotion: false,
        _meteorTimer: 0,

        setup(canvas, reduceMotion) {
            this.canvas = canvas;
            this.ctx = canvas && typeof canvas.getContext === 'function' ? canvas.getContext('2d') : null;
            this.reduceMotion = reduceMotion;
            this.meteors = [];
            this._meteorTimer = 900;
            return !!this.ctx;
        },

        resize(w, h) {
            if (!this.canvas || !this.ctx) return;
            this.dpr = Math.min(window.devicePixelRatio || 1, LOW_END ? 1.25 : 2);
            this.W = w; this.H = h;
            this.canvas.width = Math.round(w * this.dpr);
            this.canvas.height = Math.round(h * this.dpr);
            this.canvas.style.width = w + 'px';
            this.canvas.style.height = h + 'px';
            this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);

            const count = LOW_END ? 90 : (w < 720 ? 130 : 220);
            this.stars = Array.from({ length: count }, () => {
                const depth = Math.random();
                return {
                    x: Math.random() * w,
                    y: Math.random() * h,
                    depth,
                    r: 0.35 + depth * 1.5 + Math.random() * 0.45,
                    baseA: 0.14 + depth * 0.5 + Math.random() * 0.3,
                    tw: Math.random() * TAU,
                    twSpeed: 0.4 + Math.random() * 1.4
                };
            });

            this.nebulae = [
                { x: w * 0.20, y: h * 0.28, r: Math.max(w, h) * 0.32, c: '96, 148, 255', a: 0.040 },
                { x: w * 0.62, y: h * 0.80, r: Math.max(w, h) * 0.26, c: '150, 120, 255', a: 0.028 }
            ];
        },

        onMouse(x, y) {
            this.mouse.tx = x;
            this.mouse.ty = y;
        },

        _spawnMeteor() {
            const fromLeft = Math.random() > 0.5;
            this.meteors.push({
                x: fromLeft ? -40 : Math.random() * this.W,
                y: fromLeft ? Math.random() * this.H * 0.4 : -40,
                vx: 4.6 + Math.random() * 3.4,
                vy: 2.4 + Math.random() * 2.0,
                len: 90 + Math.random() * 110,
                life: 1
            });
        },

        draw(time, dt) {
            const ctx = this.ctx;
            if (!ctx) return;
            const { W, H, mouse } = this;

            if (mouse.tx > -9000) {
                mouse.x = mouse.x < -9000 ? mouse.tx : lerp(mouse.x, mouse.tx, 0.08);
                mouse.y = mouse.y < -9000 ? mouse.ty : lerp(mouse.y, mouse.ty, 0.08);
            }

            // ── 深空底色 ──
            ctx.clearRect(0, 0, W, H);
            const bg = ctx.createLinearGradient(0, 0, W * 0.4, H);
            bg.addColorStop(0, '#040610');
            bg.addColorStop(0.55, '#070d1c');
            bg.addColorStop(1, '#04070f');
            ctx.fillStyle = bg;
            ctx.fillRect(0, 0, W, H);

            // ── 星云 ──
            for (const n of this.nebulae) {
                const pulse = this.reduceMotion ? 1 : 0.82 + Math.sin(time * 0.00012 + n.x) * 0.18;
                const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r);
                g.addColorStop(0, `rgba(${n.c}, ${n.a * pulse})`);
                g.addColorStop(1, `rgba(${n.c}, 0)`);
                ctx.fillStyle = g;
                ctx.fillRect(n.x - n.r, n.y - n.r, n.r * 2, n.r * 2);
            }

            // ── 视差星 ──
            const px = mouse.x > -9000 ? (mouse.x / W - 0.5) : 0;
            const py = mouse.y > -9000 ? (mouse.y / H - 0.5) : 0;

            ctx.save();
            ctx.globalCompositeOperation = 'lighter';
            for (const s of this.stars) {
                if (!this.reduceMotion) s.tw += s.twSpeed * dt * 0.001;
                const twinkle = 0.72 + Math.sin(s.tw) * 0.28;
                const ox = -px * s.depth * 26;
                const oy = -py * s.depth * 18;
                const sx = s.x + ox;
                const sy = s.y + oy;

                ctx.globalAlpha = s.baseA * twinkle;
                ctx.fillStyle = s.depth > 0.75 ? '#e8f4ff' : s.depth > 0.4 ? '#a9c8ee' : '#6f8fbd';
                ctx.beginPath();
                ctx.arc(sx, sy, s.r, 0, TAU);
                ctx.fill();

                if (s.depth > 0.9 && s.r > 1.5) {
                    ctx.globalAlpha = s.baseA * twinkle * 0.35;
                    ctx.strokeStyle = '#dcecff';
                    ctx.lineWidth = 0.6;
                    ctx.beginPath();
                    ctx.moveTo(sx - s.r * 3.4, sy); ctx.lineTo(sx + s.r * 3.4, sy);
                    ctx.moveTo(sx, sy - s.r * 3.4); ctx.lineTo(sx, sy + s.r * 3.4);
                    ctx.stroke();
                }
            }
            ctx.restore();

            // ── 鼠标星座连线（低端设备省略） ──
            if (!LOW_END && mouse.x > -9000) {
                const R = 150, R2 = R * R;
                const near = [];
                for (const s of this.stars) {
                    if (s.depth < 0.35) continue;
                    const dx = s.x - mouse.x, dy = s.y - mouse.y;
                    const d2 = dx * dx + dy * dy;
                    if (d2 < R2) near.push({ s, d2 });
                }
                near.sort((a, b) => a.d2 - b.d2);
                const picked = near.slice(0, 7);

                ctx.save();
                ctx.lineWidth = 0.7;
                for (let i = 0; i < picked.length; i++) {
                    const a = picked[i].s;
                    const fade = 1 - Math.sqrt(picked[i].d2) / R;
                    ctx.globalAlpha = fade * 0.34;
                    ctx.strokeStyle = '#8fc4ff';
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(mouse.x, mouse.y);
                    ctx.stroke();
                    for (let j = i + 1; j < picked.length; j++) {
                        const b = picked[j].s;
                        const dx = a.x - b.x, dy = a.y - b.y;
                        if (dx * dx + dy * dy < 110 * 110) {
                            ctx.globalAlpha = fade * 0.16;
                            ctx.beginPath();
                            ctx.moveTo(a.x, a.y);
                            ctx.lineTo(b.x, b.y);
                            ctx.stroke();
                        }
                    }
                    ctx.globalAlpha = fade * 0.5;
                    ctx.fillStyle = '#dcecff';
                    ctx.beginPath();
                    ctx.arc(a.x, a.y, a.r + 0.6, 0, TAU);
                    ctx.fill();
                }
                ctx.restore();
            }

            // ── 流星（低端设备省略） ──
            if (!this.reduceMotion && !LOW_END) {
                this._meteorTimer -= dt;
                if (this._meteorTimer <= 0 && this.meteors.length < 3) {
                    this._spawnMeteor();
                    this._meteorTimer = 4200 + Math.random() * 5600;
                }
                ctx.save();
                ctx.globalCompositeOperation = 'lighter';
                for (let i = this.meteors.length - 1; i >= 0; i--) {
                    const m = this.meteors[i];
                    m.x += m.vx * dt * 0.06;
                    m.y += m.vy * dt * 0.06;
                    m.life -= dt * 0.0005;
                    if (m.x > this.W + m.len || m.y > this.H + m.len || m.life <= 0) {
                        this.meteors.splice(i, 1);
                        continue;
                    }
                    const norm = Math.hypot(m.vx, m.vy);
                    const ux = m.vx / norm, uy = m.vy / norm;
                    const tail = ctx.createLinearGradient(m.x, m.y, m.x - ux * m.len, m.y - uy * m.len);
                    tail.addColorStop(0, `rgba(235, 245, 255, ${0.85 * m.life})`);
                    tail.addColorStop(1, 'rgba(140, 180, 255, 0)');
                    ctx.strokeStyle = tail;
                    ctx.lineWidth = 1.6;
                    ctx.beginPath();
                    ctx.moveTo(m.x, m.y);
                    ctx.lineTo(m.x - ux * m.len, m.y - uy * m.len);
                    ctx.stroke();
                }
                ctx.restore();
            }
        }
    };

    /* ───────────────────── 页面控制器（环形拨盘） ───────────────────── */
    window.PlanetsView = {
        root: null,
        stage: null,
        canvas: null,
        halo: null,
        menu: null,
        menuState: null,
        menuTitle: null,
        menuCopy: null,
        moduleMenu: null,
        galaxyButtons: [],
        activeGalaxy: null,
        reduceMotion: false,
        rafId: 0,

        /* 拨盘状态机: idle(待机自转) → settling(磁吸对位) → focus(放大展示) */
        mode: 'idle',
        focusKey: null,
        bases: [0, RING, RING * 2],       // codespace / englab / frontier 逻辑环位
        offset: 0,
        targetOffset: 0,
        selectedIndex: 1,
        dragging: false,
        velocity: 0,
        geom: null,
        _geomTick: 0,
        _nodeState: null,                 // 每行星 {x,y,scale,op,blend,prox}
        _focusMax: 0,
        _dragMoved: false,
        _dragAcc: 0,
        _lastA: 0,
        _lastT: 0,
        _lastWheel: 0,
        _enterT: 0,
        _lastTime: 0,
        _bound: false,
        _handlers: null,

        init() {
            if (this._bound) this.destroy();

            this.root = document.getElementById('page-planets');
            this.stage = this.root && this.root.querySelector('.planets-stage');
            this.canvas = document.getElementById('planets-starfield');
            this.halo = this.root && this.root.querySelector('.planets-cursor-halo');
            this.menu = document.getElementById('planets-menu');
            this.menuState = document.getElementById('planets-menu-state');
            this.menuTitle = document.getElementById('planets-menu-title');
            this.menuCopy = document.getElementById('planets-menu-copy');
            this.moduleMenu = document.getElementById('planets-module-menu');
            this.galaxyButtons = Array.from(document.querySelectorAll('#page-planets [data-galaxy]'));
            if (!this.root || !this.stage) return;

            this.reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
            window.scrollTo(0, 0);
            document.body.classList.add('planets-scroll-locked');

            // 初始：待机巡游，工科试验室即将转入准星
            this.mode = 'idle';
            this.focusKey = null;
            this.selectedIndex = 1;
            this.offset = -this.bases[1] - 0.5;
            this.targetOffset = this.offset;
            this.velocity = 0;
            this.dragging = false;
            this._enterT = performance.now();
            this._nodeState = {};
            GALAXY_ORDER.forEach(key => {
                this._nodeState[key] = { x: 0, y: 0, scale: 0.6, op: 0, blend: 0, prox: 0 };
            });

            this._handlers = {
                resize: this._onResize.bind(this),
                mouse: this._onMouseMove.bind(this),
                leave: this._onMouseLeave.bind(this),
                pDown: this._onPointerDown.bind(this),
                pMove: this._onPointerMove.bind(this),
                pUp: this._onPointerUp.bind(this),
                wheel: this._onWheel.bind(this),
                galaxyClick: this._onGalaxyClick.bind(this),
                close: () => this.resetGalaxyView(),
                mark: (e) => { e.preventDefault(); this.resetGalaxyView(); },
                moduleLink: this._onModuleLinkClick.bind(this),
                key: this._onKey.bind(this),
                vis: this._onVisibility.bind(this),
                loop: this._loop.bind(this)
            };

            StarfieldEngine.setup(this.canvas, this.reduceMotion);
            this._onResize();

            window.addEventListener('resize', this._handlers.resize);
            document.addEventListener('mousemove', this._handlers.mouse);
            document.addEventListener('mouseleave', this._handlers.leave);
            document.addEventListener('keydown', this._handlers.key);
            document.addEventListener('visibilitychange', this._handlers.vis);
            this.stage.addEventListener('pointerdown', this._handlers.pDown);
            window.addEventListener('pointermove', this._handlers.pMove);
            window.addEventListener('pointerup', this._handlers.pUp);
            window.addEventListener('pointercancel', this._handlers.pUp);
            this.stage.addEventListener('wheel', this._handlers.wheel, { passive: false });
            this.galaxyButtons.forEach(b => b.addEventListener('click', this._handlers.galaxyClick));
            const close = this.root.querySelector('[data-close-menu]');
            if (close) close.addEventListener('click', this._handlers.close);
            const mark = this.root.querySelector('.planets-mark');
            if (mark) mark.addEventListener('click', this._handlers.mark);
            if (this.moduleMenu) this.moduleMenu.addEventListener('click', this._handlers.moduleLink);
            this._bound = true;

            this.root.classList.remove('is-entered');
            requestAnimationFrame(() => requestAnimationFrame(() => this.root.classList.add('is-entered')));

            this._lastTime = 0;
            this._loop(performance.now());
        },

        destroy() {
            if (this.rafId) cancelAnimationFrame(this.rafId);
            this.rafId = 0;
            if (this._bound && this._handlers) {
                window.removeEventListener('resize', this._handlers.resize);
                document.removeEventListener('mousemove', this._handlers.mouse);
                document.removeEventListener('mouseleave', this._handlers.leave);
                document.removeEventListener('keydown', this._handlers.key);
                document.removeEventListener('visibilitychange', this._handlers.vis);
                if (this.stage) {
                    this.stage.removeEventListener('pointerdown', this._handlers.pDown);
                    this.stage.removeEventListener('wheel', this._handlers.wheel);
                }
                window.removeEventListener('pointermove', this._handlers.pMove);
                window.removeEventListener('pointerup', this._handlers.pUp);
                window.removeEventListener('pointercancel', this._handlers.pUp);
                this.galaxyButtons.forEach(b => b.removeEventListener('click', this._handlers.galaxyClick));
                const close = this.root && this.root.querySelector('[data-close-menu]');
                if (close) close.removeEventListener('click', this._handlers.close);
                const mark = this.root && this.root.querySelector('.planets-mark');
                if (mark) mark.removeEventListener('click', this._handlers.mark);
                if (this.moduleMenu) this.moduleMenu.removeEventListener('click', this._handlers.moduleLink);
            }
            this._bound = false;
            this.activeGalaxy = null;
            if (this.root) this.root.classList.remove('has-menu');
            document.body.classList.remove('planets-scroll-locked');
        },

        /* ── 几何缓存（仅 resize / 周期兜底时重算，避免每帧 reflow） ── */
        _computeGeometry() {
            const rect = this.stage.getBoundingClientRect();
            if (rect.width < 10) { this.geom = null; return; }
            const compact = rect.width < 680;
            let g;
            if (!compact) {
                g = {
                    sx: rect.left + rect.width * 1.10,
                    sy: rect.top + rect.height * 0.5,
                    rx: rect.width * 0.62,
                    ry: rect.height * 0.36,
                    sunR: Math.min(rect.height * 0.44, rect.width * 0.28),
                    marker: Math.PI,
                    fx: rect.width * 0.24,
                    fy: rect.height * 0.46,
                    fScale: 1.6
                };
            } else {
                g = {
                    sx: rect.left + rect.width * 0.5,
                    sy: rect.top + rect.height * 1.22,
                    rx: rect.width * 0.46,
                    ry: rect.height * 0.78,
                    sunR: rect.width * 0.44,
                    marker: -Math.PI / 2,
                    fx: rect.width * 0.5,
                    fy: rect.height * 0.27,
                    fScale: 1.25
                };
            }
            g.compact = compact;
            g.rect = rect;
            g.localX = g.sx - rect.left;
            g.localY = g.sy - rect.top;
            this.geom = g;
        },

        /* ── 输入 ── */
        _onVisibility() {
            if (document.hidden) {
                if (this.rafId) cancelAnimationFrame(this.rafId);
                this.rafId = 0;
            } else if (this._bound && !this.rafId) {
                this._lastTime = 0;
                this._loop(performance.now());
            }
        },

        _onMouseMove(e) {
            StarfieldEngine.onMouse(e.clientX, e.clientY);
            if (this.halo) {
                this.halo.style.setProperty('--hx', e.clientX + 'px');
                this.halo.style.setProperty('--hy', e.clientY + 'px');
                this.halo.classList.add('is-on');
            }
            if (this.root) {
                const rx = (e.clientX / window.innerWidth - 0.5);
                const ry = (e.clientY / window.innerHeight - 0.5);
                this.root.style.setProperty('--par-x', (rx * -12).toFixed(2) + 'px');
                this.root.style.setProperty('--par-y', (ry * -8).toFixed(2) + 'px');
            }
        },

        _onMouseLeave() {
            if (this.halo) this.halo.classList.remove('is-on');
        },

        _pointerAngle(e) {
            const g = this.geom;
            if (!g) return 0;
            return Math.atan2((e.clientY - g.sy) / g.ry, (e.clientX - g.sx) / g.rx);
        },

        _onPointerDown(e) {
            if (!this.geom) return;
            if (e.pointerType === 'mouse' && e.button !== 0) return;
            this.dragging = true;
            this._dragMoved = false;
            this._dragAcc = 0;
            this._lastA = this._pointerAngle(e);
            this._lastT = performance.now();
            this.velocity = 0;
            this.stage.classList.add('is-grabbing');
        },

        _onPointerMove(e) {
            if (!this.dragging || !this.geom) return;
            const a = this._pointerAngle(e);
            const dVis = wrapPi(a - this._lastA);
            this._lastA = a;
            const now = performance.now();
            const dt = Math.max(8, now - this._lastT);
            this._lastT = now;

            const dRel = dVis / VIS_K;                 // 视觉角 → 逻辑角
            this._dragAcc += Math.abs(dRel);
            if (this._dragAcc > 0.05 && !this._dragMoved) {
                this._dragMoved = true;
                if (this.activeGalaxy || this.mode === 'focus') this.resetGalaxyView();
            }

            this.offset += dRel;                       // 环形：无限旋转，无端点
            this.velocity = 0.8 * this.velocity + 0.2 * (dRel / dt);
        },

        _onPointerUp() {
            if (!this.dragging) return;
            this.dragging = false;
            this.stage.classList.remove('is-grabbing');
            if (!this._dragMoved) return;              // 纯点击交给 click 处理
            // 惯性预测落点 → 磁吸到最近行星（环形最短路径）
            const predicted = this.offset + this.velocity * 220;
            let best = 0, bestAbs = Infinity;
            for (let i = 0; i < this.bases.length; i++) {
                const d = Math.abs(wrapPi(this.bases[i] + predicted));
                if (d < bestAbs) { bestAbs = d; best = i; }
            }
            this.selectedIndex = best;
            this.targetOffset = this.offset - wrapPi(this.bases[best] + this.offset);
            this.velocity = 0;
            this.mode = 'settling';
        },

        _onWheel(e) {
            e.preventDefault();
            const now = performance.now();
            if (now - this._lastWheel < 260) return;
            this._lastWheel = now;
            this._step(e.deltaY > 0 ? 1 : -1);
        },

        _onKey(e) {
            if (e.key === 'Escape' && (this.activeGalaxy || this.mode === 'focus')) {
                this.resetGalaxyView();
            } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
                this._step(-1);
            } else if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
                this._step(1);
            }
        },

        /* 环形换挡：越过尽头自动绕回（modulo）；从当前最近档位起步 */
        _step(dir) {
            this._closePanelOnly();
            const cur = this.mode === 'settling' ? this.targetOffset : this.offset;
            let nearest = 0, bestAbs = Infinity;
            for (let i = 0; i < this.bases.length; i++) {
                const d = Math.abs(wrapPi(this.bases[i] + cur));
                if (d < bestAbs) { bestAbs = d; nearest = i; }
            }
            this.selectedIndex = (nearest + dir + GALAXY_ORDER.length) % GALAXY_ORDER.length;
            let rel = wrapPi(this.bases[this.selectedIndex] + cur);
            if (dir > 0 && rel < 0) rel += TAU;      // 保证旋转方向与换挡方向一致
            if (dir < 0 && rel > 0) rel -= TAU;
            this.targetOffset = cur - rel;
            this.mode = 'settling';
        },

        _onGalaxyClick(e) {
            if (this._dragMoved) return;
            const key = e.currentTarget.dataset.galaxy;
            const idx = GALAXY_ORDER.indexOf(key);
            if (idx < 0) return;
            if (this.mode === 'focus' && this.focusKey === key) {
                this.resetGalaxyView();                // 再点一次已聚焦行星 → 收起
                return;
            }
            this._closePanelOnly();
            this.selectedIndex = idx;
            this.targetOffset = this.offset - wrapPi(this.bases[idx] + this.offset);
            this.mode = 'settling';
        },

        /* ── 菜单 ── */
        openGalaxy(key) {
            const source = GALAXIES[key];
            if (!source || !this.menu || !this.moduleMenu) return;
            this.activeGalaxy = key;
            if (this.menuState) this.menuState.textContent = source.state || 'SECTOR ' + source.no + ' · 已对准';
            this.menuTitle.textContent = source.title;
            this.menuCopy.textContent = source.copy;
            this.moduleMenu.innerHTML = source.modules.map((item, i) => this._renderModuleLink(item, i)).join('');
            this.galaxyButtons.forEach(btn => btn.classList.toggle('is-selected', btn.dataset.galaxy === key));
            this.stage.classList.add('has-open-menu');
            this.menu.classList.add('is-open');
            if (this.root) this.root.classList.add('has-menu');
        },

        /* 只收面板，不改变拨盘模式（供换挡时用） */
        _closePanelOnly() {
            this.activeGalaxy = null;
            this.focusKey = null;
            this.galaxyButtons.forEach(btn => btn.classList.remove('is-selected'));
            if (this.stage) this.stage.classList.remove('has-open-menu');
            if (this.menu) this.menu.classList.remove('is-open');
            if (this.root) this.root.classList.remove('has-menu');
        },

        /* 完整复位：收面板 + 回到待机巡游 */
        resetGalaxyView() {
            this._closePanelOnly();
            this.mode = 'idle';
        },

        _renderModuleLink(item, index) {
            const source = Array.isArray(item)
                ? { label: item[0], href: item[1], meta: item[2] }
                : item;
            const label = this._escapeHtml(source.label || '');
            const href = this._escapeHtml(source.href || '#planets');
            const rawHash = source.href && String(source.href).startsWith('#') ? String(source.href).slice(1) : '';
            const page = rawHash ? this._pageFromHashTarget(rawHash) : '';
            const pageAttr = page ? ` data-page="${this._escapeHtml(page)}"` : '';
            const no = String(index + 1).padStart(2, '0');
            const meta = source.meta
                ? `<span class="planets-module-link__meta">${this._escapeHtml(source.meta)}</span>`
                : '';
            return `<a class="planets-module-link${source.meta ? ' planets-module-link--rich' : ''}" href="${href}"${pageAttr} style="--i:${index}">` +
                `<span class="planets-module-link__no">${no}</span>` +
                `<span class="planets-module-link__body"><span class="planets-module-link__label">${label}</span>${meta}</span>` +
                `<span class="planets-module-link__arrow" aria-hidden="true">→</span></a>`;
        },

        _onModuleLinkClick(event) {
            const link = event.target.closest('a[href^="#"]');
            if (!link || !this.moduleMenu || !this.moduleMenu.contains(link)) return;

            const href = link.getAttribute('href') || '';
            const router = window.Router || (typeof Router !== 'undefined' ? Router : null);
            const hashTarget = href.slice(1);
            const page = this._pageFromHashTarget(hashTarget, router);
            if (!page) return;

            event.preventDefault();
            const rect = link.getBoundingClientRect();

            if (router && typeof router.navigateTo === 'function') {
                router.transitionOrigin = {
                    x: ((rect.left + rect.width / 2) / window.innerWidth) * 100,
                    y: ((rect.top + rect.height / 2) / window.innerHeight) * 100
                };
                router._pendingModule = null;
                router._pendingAnchor = this._isFrontierAnchor(hashTarget, router) ? hashTarget : null;
                if (!router._pendingAnchor) router._lastAppliedAnchor = null;
                this.resetGalaxyView();
                router.navigateTo(page, false);
            } else if (typeof window.navigate === 'function') {
                this.resetGalaxyView();
                window.navigate(page);
            } else {
                window.location.hash = href;
            }
        },

        _pageFromHashTarget(hashTarget, router) {
            if (!hashTarget) return '';
            const activeRouter = router || window.Router || (typeof Router !== 'undefined' ? Router : null);
            if (this._isFrontierAnchor(hashTarget, activeRouter)) {
                return activeRouter && typeof activeRouter._pageForFrontierAnchor === 'function'
                    ? activeRouter._pageForFrontierAnchor(hashTarget)
                    : 'frontier';
            }
            return hashTarget.split('/')[0];
        },

        _isFrontierAnchor(hashTarget, router) {
            if (!hashTarget || !hashTarget.startsWith('frontier-')) return false;
            const activeRouter = router || window.Router || (typeof Router !== 'undefined' ? Router : null);
            if (activeRouter && typeof activeRouter._pageForFrontierAnchor === 'function') {
                return !!activeRouter._pageForFrontierAnchor(hashTarget);
            }
            return /^frontier-(frontier|cosmos|engineering|datascience|infotech|materials|humanities)-/.test(hashTarget);
        },

        _escapeHtml(value) {
            return String(value ?? '')
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;')
                .replace(/'/g, '&#39;');
        },

        _onResize() {
            StarfieldEngine.resize(window.innerWidth, window.innerHeight);
            this._computeGeometry();
        },

        /* ── 拨盘物理 ── */
        _updatePhysics(dt) {
            if (this.dragging) return;

            if (this.mode === 'idle') {
                // 待机自转：行星缓缓巡游过准星
                if (!this.reduceMotion) this.offset += IDLE_SPEED * dt;
                return;
            }

            if (this.mode === 'settling') {
                const ease = this.reduceMotion ? 1 : 1 - Math.exp(-dt * 0.0075);
                this.offset = lerp(this.offset, this.targetOffset, ease);
                if (Math.abs(this.offset - this.targetOffset) < 0.008) {
                    this.offset = this.targetOffset;
                    this.mode = 'focus';
                    this.focusKey = GALAXY_ORDER[this.selectedIndex];
                }
            }
            // focus 模式下轮盘静止，行星由 blend 动画接管
        },

        /* ── 每帧状态计算：环形位置 + 聚焦混合 ── */
        _computeStates(time, dt) {
            const g = this.geom;
            if (!g) return;
            const ramp = this.reduceMotion ? 1 : Math.min(1, (time - this._enterT) / 800);
            const blendEase = this.reduceMotion ? 1 : 1 - Math.exp(-dt * 0.0072);
            let focusMax = 0;

            for (let i = 0; i < GALAXY_ORDER.length; i++) {
                const key = GALAXY_ORDER[i];
                const st = this._nodeState[key];
                const rel = wrapPi(this.bases[i] + this.offset);
                const a = g.marker + rel * VIS_K;

                // 轨道位置（环形：|rel|→π 时淡出，从另一端淡入 → 无缝绕回）
                const ox = g.localX + Math.cos(a) * g.rx;
                const oy = g.localY + Math.sin(a) * g.ry;
                const prox = Math.max(0, Math.cos(rel));
                const edge = Math.max(0, Math.cos(rel * 0.5));
                const oScale = 0.5 + 0.52 * Math.pow(prox, 1.5);
                const oOp = (0.2 + 0.8 * Math.pow(prox, 1.3)) * Math.pow(edge, 1.5) * ramp;

                // 聚焦混合（选中 → 放大飞向左侧定位点）
                const target = (this.mode === 'focus' && key === this.focusKey) ? 1 : 0;
                st.blend += (target - st.blend) * blendEase;
                if (st.blend < 0.001 && target === 0) st.blend = 0;
                const eB = st.blend * st.blend * (3 - 2 * st.blend);   // smoothstep

                st.x = lerp(ox, g.fx, eB);
                st.y = lerp(oy, g.fy, eB);
                st.scale = lerp(oScale, g.fScale, eB);
                st.op = lerp(oOp, 1, eB);
                st.prox = prox;
                if (st.blend > focusMax) focusMax = st.blend;
            }

            // 聚焦时其余行星退暗
            if (focusMax > 0.01) {
                for (const key of GALAXY_ORDER) {
                    if (key === this.focusKey) continue;
                    this._nodeState[key].op *= (1 - 0.62 * focusMax);
                }
            }
            this._focusMax = focusMax;

            // 行星就位后弹出介绍面板
            if (this.mode === 'focus' && focusMax > 0.72 && !this.activeGalaxy && this.focusKey) {
                this.openGalaxy(this.focusKey);
            }
        },

        /* ── DOM 应用（写在读之后，避免布局抖动） ── */
        _applyNodes() {
            const g = this.geom;
            if (!g) return;
            for (let i = 0; i < GALAXY_ORDER.length; i++) {
                const key = GALAXY_ORDER[i];
                const st = this._nodeState[key];
                const btn = this.galaxyButtons[i] && this.galaxyButtons[i].dataset.galaxy === key
                    ? this.galaxyButtons[i]
                    : this.galaxyButtons.find(b => b.dataset.galaxy === key);
                if (!btn) continue;
                btn.style.transform =
                    `translate3d(${st.x.toFixed(2)}px, ${st.y.toFixed(2)}px, 0) translate(-50%, -50%) scale(${st.scale.toFixed(3)})`;
                btn.style.opacity = st.op.toFixed(3);
                btn.style.zIndex = st.blend > 0.5 ? '30' : String(10 + Math.round(st.prox * 10));
                btn.classList.toggle('is-focus',
                    (this.mode === 'focus' && key === this.focusKey) || (this.mode !== 'focus' && st.prox > 0.92));
            }
        },

        /* ── 拨盘绘制（星场同画布，节点位置复用 _nodeState） ── */
        _drawDial(time) {
            const ctx = StarfieldEngine.ctx;
            const g = this.geom;
            if (!ctx || !g) return;
            const { sx, sy, rx, ry, sunR, marker } = g;
            const ramp = this.reduceMotion ? 1 : Math.min(1, (time - this._enterT) / 900);
            const reticleA = 1 - this._focusMax;       // 聚焦时准星淡出

            ctx.save();
            ctx.globalAlpha = ramp;

            /* 太阳辉光 + 本体 */
            let glow = ctx.createRadialGradient(sx, sy, sunR * 0.3, sx, sy, sunR * 2.3);
            glow.addColorStop(0, 'rgba(140, 190, 255, 0.16)');
            glow.addColorStop(0.5, 'rgba(120, 170, 240, 0.05)');
            glow.addColorStop(1, 'rgba(120, 170, 240, 0)');
            ctx.fillStyle = glow;
            ctx.fillRect(sx - sunR * 2.3, sy - sunR * 2.3, sunR * 4.6, sunR * 4.6);

            let body = ctx.createRadialGradient(sx - sunR * 0.28, sy - sunR * 0.22, sunR * 0.08, sx, sy, sunR);
            body.addColorStop(0, '#eaf4ff');
            body.addColorStop(0.3, '#a8ccf5');
            body.addColorStop(0.7, '#33598f');
            body.addColorStop(1, '#0d1d38');
            ctx.fillStyle = body;
            ctx.beginPath();
            ctx.arc(sx, sy, sunR, 0, TAU);
            ctx.fill();

            ctx.strokeStyle = 'rgba(160, 198, 240, 0.4)';
            ctx.lineWidth = 1;
            ctx.beginPath(); ctx.arc(sx, sy, sunR + 7, 0, TAU); ctx.stroke();
            ctx.strokeStyle = 'rgba(160, 198, 240, 0.12)';
            ctx.beginPath(); ctx.arc(sx, sy, sunR * 0.72, 0, TAU); ctx.stroke();
            ctx.beginPath(); ctx.arc(sx, sy, sunR * 0.46, 0, TAU); ctx.stroke();

            /* 太阳刻度环（缓转） */
            const sunTickRot = this.reduceMotion ? 0 : time * 0.00005;
            ctx.strokeStyle = 'rgba(160, 198, 240, 0.30)';
            for (let k = 0; k < 40; k++) {
                const a = k * TAU / 40 + sunTickRot;
                const r1 = sunR + 14, r2 = sunR + (k % 5 === 0 ? 24 : 19);
                ctx.beginPath();
                ctx.moveTo(sx + Math.cos(a) * r1, sy + Math.sin(a) * r1);
                ctx.lineTo(sx + Math.cos(a) * r2, sy + Math.sin(a) * r2);
                ctx.stroke();
            }

            /* 轨道椭圆 ×2 */
            ctx.strokeStyle = 'rgba(147, 178, 218, 0.20)';
            ctx.beginPath(); ctx.ellipse(sx, sy, rx, ry, 0, 0, TAU); ctx.stroke();
            ctx.strokeStyle = 'rgba(147, 178, 218, 0.07)';
            ctx.beginPath(); ctx.ellipse(sx, sy, rx * 0.82, ry * 0.82, 0, 0, TAU); ctx.stroke();

            /* 轨道刻度（随轮盘转动，视觉空间） */
            const tickRot = this.offset * VIS_K;
            for (let k = 0; k < 72; k++) {
                const a = k * TAU / 72 + tickRot;
                const cx = Math.cos(a), cy = Math.sin(a);
                if (cx > 0.55) continue;
                const tx = sx + cx * rx, ty = sy + cy * ry;
                const nx = cx * ry, ny = cy * rx;
                const nl = Math.hypot(nx, ny) || 1;
                const ux = nx / nl, uy = ny / nl;
                const major = k % 6 === 0;
                const prox = Math.max(0, Math.cos(wrapPi(a - marker)));
                ctx.strokeStyle = `rgba(147, 178, 218, ${(0.10 + 0.35 * prox * prox).toFixed(3)})`;
                ctx.lineWidth = major ? 1.2 : 1;
                ctx.beginPath();
                ctx.moveTo(tx + ux * 4, ty + uy * 4);
                ctx.lineTo(tx + ux * (4 + (major ? 12 : 6)), ty + uy * (4 + (major ? 12 : 6)));
                ctx.stroke();
            }

            /* 准星（聚焦时淡出） */
            if (reticleA > 0.02) {
                const mx = sx + Math.cos(marker) * rx;
                const my = sy + Math.sin(marker) * ry;
                const rr = g.compact ? 58 : 80;
                ctx.strokeStyle = `rgba(94, 228, 208, ${(0.55 * reticleA).toFixed(3)})`;
                ctx.lineWidth = 1;
                for (let q = 0; q < 4; q++) {
                    const c = q * Math.PI / 2;
                    ctx.beginPath();
                    ctx.arc(mx, my, rr, c - 0.42, c + 0.42);
                    ctx.stroke();
                    ctx.beginPath();
                    ctx.moveTo(mx + Math.cos(c) * rr, my + Math.sin(c) * rr);
                    ctx.lineTo(mx + Math.cos(c) * (rr + 10), my + Math.sin(c) * (rr + 10));
                    ctx.stroke();
                }
                /* 角度读数 */
                const degText = String(Math.round(((-this.offset / DEG) % 360 + 360) % 360));
                ctx.font = '10px "JetBrains Mono", Consolas, monospace';
                ctx.textAlign = 'center';
                ctx.fillStyle = `rgba(94, 228, 208, ${(0.66 * reticleA).toFixed(3)})`;
                ctx.fillText(`DIAL ${degText.padStart(3, ' ')}°`, mx, my + rr + 26);
            }

            /* 太阳 → 当前行星虚线（聚焦时跟随飞行位置） */
            const selKey = this.focusKey || GALAXY_ORDER[this.selectedIndex];
            const selSt = this._nodeState[selKey];
            if (selSt && selSt.op > 0.05) {
                const nx = g.rect.left + selSt.x;
                const ny = g.rect.top + selSt.y;
                const dxs = sx - nx, dys = sy - ny;
                const dl = Math.hypot(dxs, dys) || 1;
                const dux = dxs / dl, duy = dys / dl;
                const gap = 56 * selSt.scale;
                ctx.strokeStyle = `rgba(94, 228, 208, ${(0.15 + 0.16 * selSt.blend).toFixed(3)})`;
                ctx.setLineDash([4, 7]);
                ctx.beginPath();
                ctx.moveTo(nx + dux * gap, ny + duy * gap);
                ctx.lineTo(sx - dux * (sunR + 10), sy - duy * (sunR + 10));
                ctx.stroke();
                ctx.setLineDash([]);
            }

            ctx.restore();
        },

        /* ── 主循环 ── */
        _loop(time) {
            const dt = this._lastTime ? Math.min(64, time - this._lastTime) : 16;
            this._lastTime = time;

            // 几何兜底重算（低频，防字体加载/布局漂移）
            this._geomTick++;
            if (!this.geom || this._geomTick % 90 === 0) this._computeGeometry();

            this._updatePhysics(dt);
            this._computeStates(time, dt);      // 先算（读几何缓存）
            StarfieldEngine.draw(time, dt);     // 再画
            this._drawDial(time);
            this._applyNodes();                 // 最后写 DOM

            this.rafId = requestAnimationFrame(this._handlers.loop);
        }
    };

    window.initPlanets = function initPlanets() { window.PlanetsView.init(); };
    window.destroyPlanets = function destroyPlanets() { window.PlanetsView.destroy(); };
})();

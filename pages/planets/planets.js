/* ═══════════════════════════════════════════════════════════════
   星序 Astra · 总览星图  v7.0 (qianduan 重构)
   - StarfieldEngine: 三层视差星场 + 鼠标星座连线 + 流星 + 星云
   - GalaxyStage:    星系节点缓动布局 + 悬停放大 + 选中聚焦
   - CursorHalo:     鼠标辉光跟随（lerp 平滑）
   契约: window.initPlanets / window.destroyPlanets 必须存在
   ═══════════════════════════════════════════════════════════════ */

(function () {
    'use strict';

    const GALAXIES = {
        englab: {
            no: '01',
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
            no: '02',
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

    /* 星系节点的基准布局（相对 stage 中心，单位 px，会随 stage 尺寸缩放） */
    const NODE_LAYOUT = {
        englab:    { x: -0.30, y: -0.04, drift: 0.0 },
        codespace: { x:  0.30, y: -0.10, drift: 2.1 },
        frontier:  { x:  0.02, y:  0.30, drift: 4.2 }
    };

    const lerp = (a, b, t) => a + (b - a) * t;

    /* ───────────────────── 星场引擎（Canvas） ───────────────────── */
    const StarfieldEngine = {
        canvas: null, ctx: null,
        W: 0, H: 0, dpr: 1,
        stars: [],          // 三层视差星
        meteors: [],        // 流星
        nebulae: [],        // 星云
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
            this.dpr = Math.min(window.devicePixelRatio || 1, 2);
            this.W = w; this.H = h;
            this.canvas.width = Math.round(w * this.dpr);
            this.canvas.height = Math.round(h * this.dpr);
            this.canvas.style.width = w + 'px';
            this.canvas.style.height = h + 'px';
            this.ctx.setTransform(this.dpr, 0, 0, this.dpr, 0, 0);

            const count = w < 720 ? 140 : 240;
            this.stars = Array.from({ length: count }, () => {
                const depth = Math.random();          // 0 远 → 1 近
                return {
                    x: Math.random() * w,
                    y: Math.random() * h,
                    depth,
                    r: 0.35 + depth * 1.5 + Math.random() * 0.45,
                    baseA: 0.14 + depth * 0.5 + Math.random() * 0.3,
                    tw: Math.random() * Math.PI * 2,   // 闪烁相位
                    twSpeed: 0.4 + Math.random() * 1.4
                };
            });

            this.nebulae = [
                { x: w * 0.22, y: h * 0.30, r: Math.max(w, h) * 0.34, c: '96, 148, 255', a: 0.045 },
                { x: w * 0.80, y: h * 0.52, r: Math.max(w, h) * 0.30, c: '84, 226, 200', a: 0.035 },
                { x: w * 0.55, y: h * 0.85, r: Math.max(w, h) * 0.26, c: '150, 120, 255', a: 0.030 }
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

            // 鼠标位置平滑
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

            // ── 星云（微呼吸） ──
            for (const n of this.nebulae) {
                const pulse = this.reduceMotion ? 1 : 0.82 + Math.sin(time * 0.00012 + n.x) * 0.18;
                const g = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, n.r);
                g.addColorStop(0, `rgba(${n.c}, ${n.a * pulse})`);
                g.addColorStop(1, `rgba(${n.c}, 0)`);
                ctx.fillStyle = g;
                ctx.fillRect(n.x - n.r, n.y - n.r, n.r * 2, n.r * 2);
            }

            // ── 三层视差星（跟随鼠标反向轻移 + 闪烁） ──
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
                ctx.arc(sx, sy, s.r, 0, Math.PI * 2);
                ctx.fill();

                // 近层亮星十字光芒
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

            // ── 鼠标星座连线：光标附近的星互相连 + 连向光标 ──
            if (mouse.x > -9000) {
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
                    // 星 → 光标
                    ctx.globalAlpha = fade * 0.34;
                    ctx.strokeStyle = '#8fc4ff';
                    ctx.beginPath();
                    ctx.moveTo(a.x, a.y);
                    ctx.lineTo(mouse.x, mouse.y);
                    ctx.stroke();
                    // 星 → 邻近星
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
                    // 被连的星轻微增亮
                    ctx.globalAlpha = fade * 0.5;
                    ctx.fillStyle = '#dcecff';
                    ctx.beginPath();
                    ctx.arc(a.x, a.y, a.r + 0.6, 0, Math.PI * 2);
                    ctx.fill();
                }
                ctx.restore();
            }

            // ── 流星 ──
            if (!this.reduceMotion) {
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

    /* ───────────────────── 页面控制器 ───────────────────── */
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
        _lastTime: 0,
        _bound: false,
        _handlers: null,
        _nodeState: null,     // 每个节点的当前/目标位置（lerp 用）

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

            // 节点位置状态
            this._nodeState = {};
            this.galaxyButtons.forEach(btn => {
                this._nodeState[btn.dataset.galaxy] = { x: 0, y: 0, s: 0.001, tx: 0, ty: 0, ts: 1 };
            });

            // 事件绑定
            this._handlers = {
                resize: this._onResize.bind(this),
                mouse: this._onMouseMove.bind(this),
                leave: this._onMouseLeave.bind(this),
                galaxyClick: (e) => this.openGalaxy(e.currentTarget.dataset.galaxy),
                close: () => this.resetGalaxyView(),
                mark: (e) => { e.preventDefault(); this.resetGalaxyView(); },
                moduleLink: this._onModuleLinkClick.bind(this),
                key: (e) => { if (e.key === 'Escape' && this.activeGalaxy) this.resetGalaxyView(); },
                loop: this._loop.bind(this)
            };

            StarfieldEngine.setup(this.canvas, this.reduceMotion);
            this._onResize();

            window.addEventListener('resize', this._handlers.resize);
            document.addEventListener('mousemove', this._handlers.mouse);
            document.addEventListener('mouseleave', this._handlers.leave);
            document.addEventListener('keydown', this._handlers.key);
            this.galaxyButtons.forEach(b => b.addEventListener('click', this._handlers.galaxyClick));
            const close = this.root.querySelector('[data-close-menu]');
            if (close) close.addEventListener('click', this._handlers.close);
            const mark = this.root.querySelector('.planets-mark');
            if (mark) mark.addEventListener('click', this._handlers.mark);
            if (this.moduleMenu) this.moduleMenu.addEventListener('click', this._handlers.moduleLink);
            this._bound = true;

            // 入场动画：标题逐行 + 节点浮现
            this.root.classList.remove('is-entered');
            requestAnimationFrame(() => requestAnimationFrame(() => this.root.classList.add('is-entered')));

            this._lastTime = 0;
            this._loop(0);
        },

        destroy() {
            if (this.rafId) cancelAnimationFrame(this.rafId);
            this.rafId = 0;
            if (this._bound && this._handlers) {
                window.removeEventListener('resize', this._handlers.resize);
                document.removeEventListener('mousemove', this._handlers.mouse);
                document.removeEventListener('mouseleave', this._handlers.leave);
                document.removeEventListener('keydown', this._handlers.key);
                this.galaxyButtons.forEach(b => b.removeEventListener('click', this._handlers.galaxyClick));
                const close = this.root && this.root.querySelector('[data-close-menu]');
                if (close) close.removeEventListener('click', this._handlers.close);
                const mark = this.root && this.root.querySelector('.planets-mark');
                if (mark) mark.removeEventListener('click', this._handlers.mark);
                if (this.moduleMenu) this.moduleMenu.removeEventListener('click', this._handlers.moduleLink);
            }
            this._bound = false;
            this.activeGalaxy = null;
            document.body.classList.remove('planets-scroll-locked');
        },

        /* ── 交互 ── */
        _onMouseMove(e) {
            StarfieldEngine.onMouse(e.clientX, e.clientY);
            if (this.halo) {
                this.halo.style.setProperty('--hx', e.clientX + 'px');
                this.halo.style.setProperty('--hy', e.clientY + 'px');
                this.halo.classList.add('is-on');
            }
            // 标题视差
            if (this.root) {
                const rx = (e.clientX / window.innerWidth - 0.5);
                const ry = (e.clientY / window.innerHeight - 0.5);
                this.root.style.setProperty('--par-x', (rx * -14).toFixed(2) + 'px');
                this.root.style.setProperty('--par-y', (ry * -10).toFixed(2) + 'px');
            }
        },

        _onMouseLeave() {
            if (this.halo) this.halo.classList.remove('is-on');
        },

        openGalaxy(key) {
            const source = GALAXIES[key];
            if (!source || !this.menu || !this.moduleMenu) return;
            this.activeGalaxy = key;
            if (this.menuState) this.menuState.textContent = source.state || '进入星系 · ' + source.no;
            this.menuTitle.textContent = source.title;
            this.menuCopy.textContent = source.copy;
            this.moduleMenu.innerHTML = source.modules.map((item, i) => this._renderModuleLink(item, i)).join('');
            this.galaxyButtons.forEach(btn => btn.classList.toggle('is-selected', btn.dataset.galaxy === key));
            this.stage.classList.add('has-open-menu');
            this.menu.classList.add('is-open');
        },

        resetGalaxyView() {
            this.activeGalaxy = null;
            this.galaxyButtons.forEach(btn => btn.classList.remove('is-selected'));
            if (this.stage) this.stage.classList.remove('has-open-menu');
            if (this.menu) this.menu.classList.remove('is-open');
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

        /* ── 布局 ── */
        _onResize() {
            StarfieldEngine.resize(window.innerWidth, window.innerHeight);
        },

        /* 每帧更新星系节点位置（lerp 缓动） */
        _layoutNodes(time) {
            if (!this.stage) return;
            const rect = this.stage.getBoundingClientRect();
            if (rect.width < 10) return;
            const compact = rect.width < 620;
            const halfW = rect.width / 2;
            const halfH = rect.height / 2;

            this.galaxyButtons.forEach(btn => {
                const key = btn.dataset.galaxy;
                const base = NODE_LAYOUT[key];
                const st = this._nodeState[key];
                if (!base || !st) return;

                if (this.activeGalaxy) {
                    const selected = key === this.activeGalaxy;
                    if (selected) {
                        st.tx = compact ? 0 : -halfW * 0.42;
                        st.ty = compact ? -halfH * 0.46 : -halfH * 0.18;
                        st.ts = compact ? 1.0 : 1.14;
                    } else {
                        const inactive = this.galaxyButtons.filter(b => b.dataset.galaxy !== this.activeGalaxy);
                        const idx = inactive.indexOf(btn);
                        const center = (inactive.length - 1) / 2;
                        st.tx = compact ? (idx - center) * rect.width * 0.34 : halfW * 0.46;
                        st.ty = compact ? halfH * 0.55 : halfH * 0.05 + (idx - center) * 150;
                        st.ts = 0.62;
                    }
                } else {
                    const drift = this.reduceMotion ? 0 : Math.sin(time * 0.00035 + base.drift) * 10;
                    const drift2 = this.reduceMotion ? 0 : Math.cos(time * 0.00028 + base.drift * 1.7) * 7;
                    st.tx = base.x * rect.width + drift;
                    st.ty = base.y * rect.height + drift2;
                    st.ts = 1;
                }

                // lerp
                const ease = this.reduceMotion ? 1 : 0.085;
                st.x = lerp(st.x, st.tx, ease);
                st.y = lerp(st.y, st.ty, ease);
                st.s = lerp(st.s, st.ts, ease);

                btn.style.transform =
                    `translate(calc(-50% + ${st.x.toFixed(2)}px), calc(-50% + ${st.y.toFixed(2)}px)) scale(${st.s.toFixed(3)})`;
            });
        },

        _loop(time) {
            const dt = this._lastTime ? Math.min(64, time - this._lastTime) : 16;
            this._lastTime = time;
            StarfieldEngine.draw(time, dt);
            this._layoutNodes(time);
            if (!this.reduceMotion) {
                this.rafId = requestAnimationFrame(this._handlers.loop);
            } else {
                // 降级：静态一帧 + 低频重绘（保证星座连线仍随鼠标更新）
                this.rafId = 0;
                setTimeout(() => { if (this._bound) this._loop(performance.now()); }, 250);
            }
        }
    };

    window.initPlanets = function initPlanets() { window.PlanetsView.init(); };
    window.destroyPlanets = function destroyPlanets() { window.PlanetsView.destroy(); };
})();

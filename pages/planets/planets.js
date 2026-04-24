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

    hovered: null,        // 当前 hover 的对象（galaxy: subject; subject: satellite 或 'center'）
    stars: [],

    // ── v4.4：星系作为目录 — 双层星系状态 ──
    mode: 'galaxy',       // 'galaxy' | 'subject'
    currentSubject: null, // 进入子星系后保存当前 subject 对象
    satellites: [],       // 当前子星系的卫星列表
    tIn: 0,               // 进入 subject 的过渡进度 0→1
    tInTarget: 0,
    subjTime: 0,          // 卫星轨道独立时间累加（ms）
    launchingSat: null,   // v4.4-α5：正在 zoom 跳转的卫星
    tLaunch: 0,           // 0→1，控制跳转动画进度
    tLaunchTarget: 0,

    subjects: [
        { id: 'mathematics', label: '数学', desc: '函数·几何·概率·向量·圆锥曲线 (15 实验)', color: '#5b8dce', angle: 0 },
        { id: 'physics',     label: '物理', desc: '力学·电磁·波动·相对论·万有引力 (17 实验)', color: '#a78bfa', angle: 1.2566 }, // 2π/5
        { id: 'chemistry',   label: '化学', desc: '周期表·反应·平衡·电化学·有机化学 (12 实验)', color: '#10b981', angle: 2.5132 },
        { id: 'algorithms',  label: '算法', desc: '排序·搜索·图·动态规划·KMP (8 实验)', color: '#f59e0b', angle: 3.7699 },
        { id: 'biology',     label: '生物', desc: '细胞·DNA·光合·遗传·神经免疫 (13 实验)', color: '#06b6d4', angle: 5.0265 }
    ],

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
        // 离开页面时复位为 galaxy 模式，避免下次回来仍在 subject 状态
        this.mode = 'galaxy';
        this.currentSubject = null;
        this.satellites = [];
        this.tIn = 0; this.tInTarget = 0;
        this.launchingSat = null;
        this.tLaunch = 0; this.tLaunchTarget = 0;
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
        if (e.key === 'Escape' && this.mode === 'subject') {
            this._exitSubject();
        }
    },

    _handleTap() {
        if (!this.hovered) return;
        if (this.mode === 'galaxy') {
            // 进入学科子星系
            this._enterSubject(this.hovered);
        } else {
            // subject 模式
            if (this.hovered === '__center') {
                this._exitSubject();
            } else {
                this._enterExperiment(this.hovered);
            }
        }
    },

    // ── v4.4 子星系：进入学科 ──
    _enterSubject(subject) {
        if (!subject) return;
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
        this.mode = 'galaxy';
        this.currentSubject = null;
        this.satellites = [];
        this.tInTarget = 0;
        this.hovered = null;
        this._updateChrome();
        this._updateInfo();
    },

    _enterExperiment(sat) {
        if (!sat || !this.currentSubject) return;
        if (this.launchingSat) return; // 防重点
        const subjectId = this.currentSubject.id;
        const expId = sat.id;
        // 启动 zoom-into-satellite 动画
        this.launchingSat = sat;
        this.tLaunch = 0;
        this.tLaunchTarget = 1;
        this.autoRotate = false;
        // 锁定靠近相机的 yaw：让该卫星转到正面（z = +radius）以便冲出画面
        const a = sat.angle + this.subjTime * (sat.ring === 0 ? 0.00018 : 0.00012);
        // 在 _planetPos 的坐标系： x=r·cosα, z=r·sinα；投影经 yaw 旋转。要让 z 坐标走到正面，
        // 调整 targetYaw 使该点靠近中姮平面。简单起见：允许位置保持，动画同时起作。
        // 1) 等动画推进到 0.85 后跳转（~480ms）
        const navDelay = 480;
        clearTimeout(this._navTimer);
        this._navTimer = setTimeout(() => {
            window.location.hash = '#' + subjectId;
            // 2) 再等 router 转场完成调 ModuleSelector
            setTimeout(() => {
                if (typeof ModuleSelector !== 'undefined' && typeof ModuleSelector.openModule === 'function') {
                    try { ModuleSelector.openModule(subjectId, expId); } catch (err) { /* noop */ }
                }
            }, 600);
        }, navDelay);
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
            // v4.4-α7：subject 模式下把标题区替换为面包屑
            if (title) {
                title.innerHTML = `
                    <div class="planets-crumb-row">
                        <button type="button" class="planets-crumb planets-crumb--root" data-action="back-to-galaxy" aria-label="返回主星系">主星系</button>
                        <span class="planets-crumb-sep">›</span>
                        <span class="planets-crumb planets-crumb--subject">${s.label}</span>
                        <span class="planets-crumb-sep planets-crumb-sep--exp" data-exp-sep>·</span>
                        <span class="planets-crumb planets-crumb--exp" data-exp-name></span>
                    </div>
                    <div class="planets-subtitle">TAP SATELLITE TO ENTER · ESC RETURN</div>
                `;
                const backBtn = title.querySelector('[data-action="back-to-galaxy"]');
                if (backBtn) backBtn.addEventListener('click', () => this._exitSubject());
            }
            if (hudBL) hudBL.innerHTML = '<div>← DRAG TO ROTATE</div><div>TAP SATELLITE / ESC RETURN</div>';
            if (hudTL) hudTL.innerHTML = `<div><span class="blink">●</span> ${s.id.toUpperCase()}.SCAN</div><div>MODE: SUB-ORBIT</div><div>NODES: ${this.satellites.length}</div>`;
        } else {
            if (title) {
                title.innerHTML = `星 系 导 航<div class="planets-subtitle">SUBJECT · GALAXY · MAP</div>`;
            }
            if (hudBL) hudBL.innerHTML = '<div>← DRAG TO ROTATE</div><div>TAP PLANET TO ENTER</div>';
            if (hudTL) hudTL.innerHTML = '<div><span class="blink">●</span> SYS.SCAN</div><div>MODE: ORBIT</div><div>NODES: 5</div>';
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
        if (this.mode === 'galaxy' || this.tIn < 0.5) {
            // 主星系：测试学科行星
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
                    const radius = Math.max(22, 40 * proj.scale / 200);   // v44c：热区跳本体略大，手机友好
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
        if (this.mode === 'galaxy' && this.hovered && this.hovered.id) {
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
        // v4.4-α5：zoom-into-satellite 动画推进（线性以保证可预测的 480ms）
        if (this.launchingSat) {
            this.tLaunch = Math.min(1, this.tLaunch + dt / 480);
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
        const aGalaxy = 1 - this.tIn;     // 主星系层不透明度
        const aSubject = this.tIn;        // 子星系层不透明度

        // ── 主星系层（galaxy）────────────────────────
        if (aGalaxy > 0.02) {
            ctx.save();
            ctx.globalAlpha = aGalaxy;

            // central core
            const coreR = Math.min(this.W, this.H) * 0.06;
            const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 2);
            grad.addColorStop(0, 'rgba(58,169,255,0.4)');
            grad.addColorStop(0.5, 'rgba(58,169,255,0.1)');
            grad.addColorStop(1, 'rgba(58,169,255,0)');
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(cx, cy, coreR * 2, 0, Math.PI * 2);
            ctx.fill();

            ctx.strokeStyle = 'rgba(58,169,255,0.6)';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
            ctx.stroke();

            // 主轨道环
            ctx.strokeStyle = 'rgba(58,169,255,0.18)';
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
            // launch 时其他元素逐渐淡出
            const subAlpha = aSubject * (1 - this.tLaunch * 0.85);
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
                this._drawSatellite(ctx, sat, proj, this.hovered === sat, s.color);
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
        }
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

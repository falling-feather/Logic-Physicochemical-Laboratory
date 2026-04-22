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

    hovered: null,
    stars: [],

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

        this._resize();
        window.addEventListener('resize', this._resize);
        this.canvas.addEventListener('mousedown', this._onDown);
        window.addEventListener('mousemove', this._onMove);
        window.addEventListener('mouseup', this._onUp);
        this.canvas.addEventListener('click', this._onClick);
        this.canvas.addEventListener('touchstart', this._onTouchStart, { passive: false });
        this.canvas.addEventListener('touchmove', this._onTouchMove, { passive: false });
        this.canvas.addEventListener('touchend', this._onTouchEnd);

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
        if (this.hovered) {
            window.location.hash = '#' + this.hovered.id;
        }
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
        if (!this.moved && this.hovered) {
            window.location.hash = '#' + this.hovered.id;
        }
        this.isDragging = false;
        clearTimeout(this._autoTimer);
        this._autoTimer = setTimeout(() => { this.autoRotate = true; this.hovered = null; this._updateInfo(); }, 4000);
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
        const projected = this.subjects.map(s => {
            const p = this._planetPos(s);
            const proj = this._project(p.x, p.y, p.z);
            return { s, proj };
        }).sort((a, b) => b.proj.z - a.proj.z); // closer first

        this.hovered = null;
        for (const { s, proj } of projected) {
            const radius = Math.max(28, 60 * proj.scale / 200);
            const dx = mx - proj.x, dy = my - proj.y;
            if (dx * dx + dy * dy <= radius * radius) {
                this.hovered = s;
                break;
            }
        }
        this.canvas.style.cursor = this.hovered ? 'pointer' : (this.isDragging ? 'grabbing' : 'grab');
        this._updateInfo();
    },

    _updateInfo() {
        if (!this.info) return;
        if (this.hovered) {
            this.info.classList.add('planets-info--visible');
            this.info.querySelector('.planets-info__name').textContent = this.hovered.label;
            this.info.querySelector('.planets-info__desc').textContent = this.hovered.desc;
            this.info.style.borderLeftColor = this.hovered.color;
        } else {
            this.info.classList.remove('planets-info--visible');
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

        this._draw();
        this.rafId = requestAnimationFrame(this._loop);
    },

    _draw() {
        const ctx = this.ctx;
        // backdrop
        ctx.fillStyle = 'rgba(0,5,8,0.4)'; // partial trail
        ctx.fillRect(0, 0, this.W, this.H);

        // background stars (simple parallax dots)
        for (const star of this.stars) {
            const p = this._project(star.x * 4, star.y * 4, star.z * 4 - 1);
            const sz = Math.max(0.3, 1.4 * p.scale / 200);
            ctx.globalAlpha = star.a * Math.min(1, p.scale / 200);
            ctx.fillStyle = '#7ce7d5';
            ctx.fillRect(p.x, p.y, sz, sz);
        }
        ctx.globalAlpha = 1;

        // central core
        const cx = this.W / 2, cy = this.H / 2;
        const coreR = Math.min(this.W, this.H) * 0.06;
        const grad = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 2);
        grad.addColorStop(0, 'rgba(0,255,213,0.4)');
        grad.addColorStop(0.5, 'rgba(0,255,213,0.1)');
        grad.addColorStop(1, 'rgba(0,255,213,0)');
        ctx.fillStyle = grad;
        ctx.beginPath();
        ctx.arc(cx, cy, coreR * 2, 0, Math.PI * 2);
        ctx.fill();

        ctx.strokeStyle = 'rgba(0,255,213,0.6)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(cx, cy, coreR, 0, Math.PI * 2);
        ctx.stroke();

        // orbit ring (project a circle in xz plane at y=0)
        ctx.strokeStyle = 'rgba(0,255,213,0.18)';
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

        // planets — project, sort by depth, draw far→near
        const items = this.subjects.map(s => {
            const pos = this._planetPos(s);
            const proj = this._project(pos.x, pos.y, pos.z);
            return { s, proj };
        }).sort((a, b) => a.proj.z - b.proj.z);

        for (const { s, proj } of items) {
            const planetR = Math.max(20, 42 * proj.scale / 200);
            const isHover = this.hovered === s;
            const depthFactor = (proj.z + 2) / 4; // 0~1
            const alpha = 0.5 + 0.5 * Math.max(0.2, depthFactor);

            // outer glow
            const glow = ctx.createRadialGradient(proj.x, proj.y, 0, proj.x, proj.y, planetR * 2.6);
            glow.addColorStop(0, this._hexA(s.color, isHover ? 0.45 : 0.22 * alpha));
            glow.addColorStop(1, this._hexA(s.color, 0));
            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(proj.x, proj.y, planetR * 2.6, 0, Math.PI * 2);
            ctx.fill();

            // body — translucent dark + cyan ring
            ctx.fillStyle = `rgba(0,30,30,${0.65 * alpha})`;
            ctx.beginPath();
            ctx.arc(proj.x, proj.y, planetR, 0, Math.PI * 2);
            ctx.fill();

            ctx.strokeStyle = isHover ? '#00ffd5' : `rgba(0,255,213,${0.55 * alpha})`;
            ctx.lineWidth = isHover ? 2 : 1.2;
            ctx.beginPath();
            ctx.arc(proj.x, proj.y, planetR, 0, Math.PI * 2);
            ctx.stroke();

            // inner crosshair / equator ring
            ctx.strokeStyle = `rgba(0,255,213,${0.35 * alpha})`;
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

            // subject color dot at center
            ctx.fillStyle = this._hexA(s.color, alpha);
            ctx.beginPath();
            ctx.arc(proj.x, proj.y, planetR * 0.18, 0, Math.PI * 2);
            ctx.fill();

            // label
            ctx.fillStyle = isHover ? '#00ffd5' : `rgba(212,255,243,${0.85 * alpha})`;
            ctx.font = `${isHover ? 'bold ' : ''}${Math.max(11, 14 * proj.scale / 200)}px var(--font-display, system-ui)`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.fillText(s.label, proj.x, proj.y + planetR + 10);
        }
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

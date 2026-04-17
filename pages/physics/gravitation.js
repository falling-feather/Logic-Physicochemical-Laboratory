/* ═══════════════════════════════════════════════════
   Universal Gravitation – Orbital Simulation
   ═══════════════════════════════════════════════════ */
const Gravitation = {
    _listeners: [],
    _on(el, evt, fn, opts) { el.addEventListener(evt, fn, opts); this._listeners.push({ el, evt, fn, opts }); },
    canvas: null, ctx: null, animId: null,
    paused: false,
    mode: 'orbit', // orbit | field
    // central body
    centralMass: 500,
    centralR: 30,
    // satellites
    satellites: [],
    G: 0.8,
    trailLen: 200,
    showVectors: true,

    init() {
        this.canvas = document.getElementById('gravitation-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.paused = false;
        this._resize();
        this._on(window, 'resize', () => this._resize());
        this._buildControls();
        this._initSatellites();
        this.updateInfo();
        this._loop();
    },
    destroy() {
        if (this.animId) { cancelAnimationFrame(this.animId); this.animId = null; }
        this._listeners.forEach(l => l.el.removeEventListener(l.evt, l.fn, l.opts));
        this._listeners.length = 0;
        const c = document.getElementById('gravitation-controls');
        if (c) c.innerHTML = '';
    },
    _resize() {
        if (window.PhysicsZoom && window.PhysicsZoom.movedCanvas === this.canvas) return;
        const p = this.canvas.parentElement;
        const dpr = window.devicePixelRatio || 1;
        const w = p.clientWidth;
        const h = Math.min(Math.max(w * 0.56, 360), 560);
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w;
        this.H = h;
        this.cx = this.W / 2;
        this.cy = this.H / 2;
    },
    _buildControls() {
        const ctrl = document.getElementById('gravitation-controls');
        if (!ctrl) return;
        ctrl.innerHTML = '';
        // mode buttons
        const modes = [
            { id: 'orbit', label: '\u8f68\u9053\u6a21\u62df' },
            { id: 'field', label: '\u5f15\u529b\u573a' }
        ];
        const btnWrap = document.createElement('div');
        btnWrap.className = 'grav-mode-btns';
        modes.forEach(m => {
            const b = document.createElement('button');
            b.className = 'grav-mode-btn' + (m.id === this.mode ? ' active' : '');
            b.textContent = m.label;
            this._on(b, 'click', () => {
                this.mode = m.id;
                btnWrap.querySelectorAll('.grav-mode-btn').forEach(x => x.classList.remove('active'));
                b.classList.add('active');
                this.updateInfo();
            });
            btnWrap.appendChild(b);
        });
        ctrl.appendChild(btnWrap);
        // mass slider
        const wrap = document.createElement('label');
        wrap.className = 'grav-param';
        wrap.innerHTML = '<span>\u4e2d\u5fc3\u8d28\u91cf M=</span>';
        const inp = document.createElement('input');
        inp.type = 'range'; inp.min = 100; inp.max = 1500; inp.step = 50; inp.value = this.centralMass;
        const val = document.createElement('span');
        val.textContent = this.centralMass;
        this._on(inp, 'input', () => {
            this.centralMass = parseFloat(inp.value);
            val.textContent = inp.value;
        });
        wrap.appendChild(inp);
        wrap.appendChild(val);
        ctrl.appendChild(wrap);
        // vector toggle
        const vb = document.createElement('button');
        vb.className = 'grav-mode-btn active';
        vb.textContent = '\u529b\u5411\u91cf';
        this._on(vb, 'click', () => {
            this.showVectors = !this.showVectors;
            vb.classList.toggle('active', this.showVectors);
        });
        ctrl.appendChild(vb);

        const pauseBtn = document.getElementById('grav-pause');
        if (pauseBtn) {
            pauseBtn.textContent = '暂停';
            this._on(pauseBtn, 'click', () => {
                this.paused = !this.paused;
                pauseBtn.textContent = this.paused ? '继续' : '暂停';
            });
        }

        const resetBtn = document.getElementById('grav-reset');
        if (resetBtn) {
            this._on(resetBtn, 'click', () => {
                this.paused = false;
                if (pauseBtn) pauseBtn.textContent = '暂停';
                this._initSatellites();
            });
        }
    },
    _initSatellites() {
        this.satellites = [];
        const orbits = [
            { dist: 100, speed: 2.2, color: 'rgba(100,180,255,0.8)', r: 6, name: '\u536b\u661f A' },
            { dist: 160, speed: 1.5, color: 'rgba(255,180,100,0.8)', r: 8, name: '\u536b\u661f B' },
            { dist: 230, speed: 1.0, color: 'rgba(100,255,180,0.8)', r: 5, name: '\u536b\u661f C' }
        ];
        orbits.forEach(o => {
            const angle = Math.random() * Math.PI * 2;
            this.satellites.push({
                x: this.cx + o.dist * Math.cos(angle),
                y: this.cy + o.dist * Math.sin(angle),
                vx: -o.speed * Math.sin(angle),
                vy: o.speed * Math.cos(angle),
                r: o.r,
                color: o.color,
                name: o.name,
                trail: []
            });
        });
    },
    _stepPhysics() {
        if (this.paused) return;
        const G = this.G, M = this.centralMass;
        this.satellites.forEach(s => {
            const dx = this.cx - s.x;
            const dy = this.cy - s.y;
            const dist = Math.sqrt(dx * dx + dy * dy);
            if (dist < this.centralR) return;
            const F = G * M / (dist * dist);
            const ax = F * dx / dist;
            const ay = F * dy / dist;
            s.vx += ax;
            s.vy += ay;
            s.x += s.vx;
            s.y += s.vy;
            s.trail.push({ x: s.x, y: s.y });
            if (s.trail.length > this.trailLen) s.trail.shift();
        });
    },
    _drawOrbit() {
        const ctx = this.ctx, W = this.W, H = this.H;
        this._stepPhysics();

        // starfield background
        if (!this._stars) {
            this._stars = [];
            for (let i = 0; i < 60; i++) {
                this._stars.push({ x: Math.random() * W, y: Math.random() * H, r: Math.random() * 1.5 + 0.5, a: Math.random() });
            }
        }
        this._stars.forEach(s => {
            ctx.beginPath();
            ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255,255,255,' + (s.a * 0.3) + ')';
            ctx.fill();
        });

        // central body (sun/planet)
        const grd = ctx.createRadialGradient(this.cx, this.cy, 0, this.cx, this.cy, this.centralR);
        grd.addColorStop(0, 'rgba(255,200,50,0.9)');
        grd.addColorStop(0.7, 'rgba(255,150,30,0.7)');
        grd.addColorStop(1, 'rgba(255,100,0,0.2)');
        ctx.beginPath();
        ctx.arc(this.cx, this.cy, this.centralR, 0, Math.PI * 2);
        ctx.fillStyle = grd;
        ctx.fill();
        // glow
        ctx.beginPath();
        ctx.arc(this.cx, this.cy, this.centralR + 8, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,200,50,0.1)';
        ctx.fill();
        // label
        ctx.font = '11px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(255,200,50,0.8)';
        ctx.fillText('M = ' + this.centralMass, this.cx, this.cy + this.centralR + 18);

        // satellites
        this.satellites.forEach(s => {
            // trail
            if (s.trail.length > 1) {
                ctx.beginPath();
                s.trail.forEach((p, i) => {
                    if (i === 0) ctx.moveTo(p.x, p.y);
                    else ctx.lineTo(p.x, p.y);
                });
                ctx.strokeStyle = s.color.replace('0.8', '0.2');
                ctx.lineWidth = 1;
                ctx.stroke();
            }
            // body
            ctx.beginPath();
            ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
            ctx.fillStyle = s.color;
            ctx.fill();
            // name
            ctx.font = '10px "Noto Sans SC", sans-serif';
            ctx.fillStyle = s.color;
            ctx.fillText(s.name, s.x, s.y - s.r - 5);
            // force vector
            if (this.showVectors) {
                const dx = this.cx - s.x, dy = this.cy - s.y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                const F = this.G * this.centralMass / (dist * dist);
                const scale = F * 10;
                const ux = dx / dist, uy = dy / dist;
                ctx.beginPath();
                ctx.moveTo(s.x, s.y);
                ctx.lineTo(s.x + ux * scale, s.y + uy * scale);
                ctx.strokeStyle = 'rgba(255,100,100,0.6)';
                ctx.lineWidth = 2;
                ctx.stroke();
                // arrowhead
                const ax = s.x + ux * scale, ay = s.y + uy * scale;
                const angle = Math.atan2(uy, ux);
                ctx.beginPath();
                ctx.moveTo(ax, ay);
                ctx.lineTo(ax - 6 * Math.cos(angle - 0.4), ay - 6 * Math.sin(angle - 0.4));
                ctx.lineTo(ax - 6 * Math.cos(angle + 0.4), ay - 6 * Math.sin(angle + 0.4));
                ctx.closePath();
                ctx.fillStyle = 'rgba(255,100,100,0.6)';
                ctx.fill();
                // velocity vector
                const vScale = 8;
                ctx.beginPath();
                ctx.moveTo(s.x, s.y);
                ctx.lineTo(s.x + s.vx * vScale, s.y + s.vy * vScale);
                ctx.strokeStyle = 'rgba(100,200,100,0.6)';
                ctx.lineWidth = 2;
                ctx.stroke();
            }
        });

        // formula
        ctx.font = 'bold 13px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillStyle = 'rgba(139,111,192,0.9)';
        ctx.fillText('F = GMm/r\u00B2', 14, 25);
        ctx.font = '11px "Noto Sans SC", sans-serif';
        ctx.fillStyle = 'rgba(200,200,200,0.5)';
        ctx.fillText('\u7EA2: \u5F15\u529B  \u7EFF: \u901F\u5EA6', 14, 45);
    },
    _drawField() {
        const ctx = this.ctx, W = this.W, H = this.H;
        const step = 35;
        const M = this.centralMass;
        ctx.font = 'bold 13px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(139,111,192,0.9)';
        ctx.fillText('\u5F15\u529B\u573A\u5206\u5E03 (g = GM/r\u00B2)', W / 2, 25);

        // central body
        ctx.beginPath();
        ctx.arc(this.cx, this.cy, this.centralR * 0.8, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,200,50,0.7)';
        ctx.fill();

        // field arrows
        for (let x = step; x < W; x += step) {
            for (let y = step; y < H; y += step) {
                const dx = this.cx - x, dy = this.cy - y;
                const dist = Math.sqrt(dx * dx + dy * dy);
                if (dist < this.centralR * 1.2) continue;
                const g = this.G * M / (dist * dist);
                const len = Math.min(g * 8, step * 0.6);
                const ux = dx / dist, uy = dy / dist;
                const alpha = Math.min(0.7, g * 2);
                ctx.beginPath();
                ctx.moveTo(x, y);
                ctx.lineTo(x + ux * len, y + uy * len);
                ctx.strokeStyle = 'rgba(139,111,192,' + alpha + ')';
                ctx.lineWidth = 1.5;
                ctx.stroke();
                // small arrowhead
                const ax = x + ux * len, ay = y + uy * len;
                const angle = Math.atan2(uy, ux);
                ctx.beginPath();
                ctx.moveTo(ax, ay);
                ctx.lineTo(ax - 4 * Math.cos(angle - 0.5), ay - 4 * Math.sin(angle - 0.5));
                ctx.lineTo(ax - 4 * Math.cos(angle + 0.5), ay - 4 * Math.sin(angle + 0.5));
                ctx.closePath();
                ctx.fillStyle = 'rgba(139,111,192,' + alpha + ')';
                ctx.fill();
            }
        }
        // equipotential circles
        ctx.setLineDash([4, 6]);
        [80, 140, 210].forEach((r, i) => {
            ctx.beginPath();
            ctx.arc(this.cx, this.cy, r, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(139,111,192,' + (0.3 - i * 0.08) + ')';
            ctx.lineWidth = 1;
            ctx.stroke();
        });
        ctx.setLineDash([]);
    },
    _loop() {
        this.ctx.clearRect(0, 0, this.W, this.H);
        if (this.mode === 'orbit') {
            this._drawOrbit();
        } else {
            this._drawField();
        }
        this.animId = requestAnimationFrame(() => this._loop());
    },

    /* ── education panel ── */
    updateInfo() {
        const el = document.getElementById('grav-info');
        if (!el) return;
        const M = this.centralMass;
        let h = '';
        if (this.mode === 'orbit') {
            h = `<div class="ac-hd"><span class="ac-tag">轨道</span>万有引力与天体运动</div>
<div class="ac-row"><span class="ac-key">万有引力定律</span>F = GMm/r² — 任意两质点间的引力，G = 6.674×10⁻¹¹ N·m²/kg²</div>
<div class="ac-row"><span class="ac-key ac-key--purple">轨道速度</span>GMm/r² = mv²/r → v = √(GM/r) — 轨道越高速度越小</div>
<div class="ac-row"><span class="ac-key ac-key--amber">开普勒第三定律</span>T²/r³ = 4π²/(GM) — 所有卫星的 T²/r³ 为同一常数</div>
<div class="ac-row"><span class="ac-key">第一宇宙速度</span>v₁ = √(gR) ≈ 7.9 km/s — 近地圆轨道最小发射速度，也是最大环绕速度</div>
<div class="ac-note">💡 人教版必修2：向心力由万有引力提供。近地卫星速度最大、周期最短。当前中心质量 M = ${M}，调节滑块观察轨道变化</div>`;
        } else {
            h = `<div class="ac-hd"><span class="ac-tag ac-tag--amber">引力场</span>引力场强度分布</div>
<div class="ac-row"><span class="ac-key">场强定义</span>g = F/m = GM/r² — 距质心 r 处的引力场强度（单位质量受力）</div>
<div class="ac-row"><span class="ac-key ac-key--purple">等势面</span>虚线圆 = 引力势能相等的面，球对称质量的等势面为同心球面</div>
<div class="ac-row"><span class="ac-key ac-key--amber">场线特征</span>箭头指向质心，越靠近中心越密集 → 场强越大</div>
<div class="ac-row"><span class="ac-key">表面重力</span>g₀ = GM/R² — 天体表面的重力加速度，地球 g₀ ≈ 9.8 m/s²</div>
<div class="ac-note">💡 人教版必修2：引力场强度随距离平方反比递减。等势面与场线处处垂直。当前 M = ${M}</div>`;
        }
        el.innerHTML = h;
    }
};

function initGravitation() { Gravitation.init(); }
window.Gravitation = Gravitation;
// ===== Mechanical Energy Conservation =====
// Roller coaster with PE/KE bar chart

const EnergyConservation = {
    canvas: null, ctx: null, W: 0, H: 0,
    _listeners: [],
    _resizeObs: null,
    _raf: null,

    running: true,
    time: 0,
    g: 9.8,
    mass: 1.0,
    friction: 0,
    ballPos: 0, // position along track (0-1)
    ballSpeed: 0,
    lastTime: 0,

    // Track is a series of y-values (heights)
    trackPoints: [],

    colors: {
        track: 'rgba(139,111,192,0.4)',
        ball: '#8b6fc0',
        pe: '#5b8dce',
        ke: '#e06c75',
        total: '#e5c07b'
    },

    _on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts);
        this._listeners.push({ el, evt, fn, opts });
    },

    init() {
        this.canvas = document.getElementById('energy-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.running = true;
        this.lastTime = performance.now();
        this.buildTrack();
        this.ballPos = 0;
        this.ballSpeed = 0;
        this.resize();
        this.bindEvents();
        this.updateInfo();
        this.loop();
    },

    destroy() {
        this.running = false;
        if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
        for (const l of this._listeners) l.el.removeEventListener(l.evt, l.fn, l.opts);
        this._listeners = [];
        if (this._resizeObs) { this._resizeObs.disconnect(); this._resizeObs = null; }
    },

    resize() {
        if (window.PhysicsZoom && window.PhysicsZoom.movedCanvas === this.canvas) return;
        const wrap = this.canvas.parentElement;
        if (!wrap) return;
        const dpr = window.devicePixelRatio || 1;
        const rect = wrap.getBoundingClientRect();
        const w = rect.width;
        const h = Math.min(w * 0.55, 380);
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w;
        this.H = h;
    },

    buildTrack() {
        // Generate a roller coaster track as height values
        const n = 200;
        this.trackPoints = [];
        for (let i = 0; i <= n; i++) {
            const t = i / n;
            // Custom roller coaster profile
            const h = 0.8 * Math.sin(t * Math.PI) * (1 - 0.3 * Math.sin(t * 3 * Math.PI))
                    + 0.15 * Math.sin(t * 5 * Math.PI);
            this.trackPoints.push(Math.max(0, h));
        }
        // Ensure start is high, end is low
        this.trackPoints[0] = 0.85;
    },

    bindEvents() {
        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => { this.resize(); });
            this._resizeObs.observe(this.canvas.parentElement);
        }

        const fricSlider = document.getElementById('energy-friction');
        if (fricSlider) this._on(fricSlider, 'input', () => {
            this.friction = parseFloat(fricSlider.value);
        });

        const playBtn = document.getElementById('energy-play');
        if (playBtn) this._on(playBtn, 'click', () => {
            this.running = !this.running;
            playBtn.textContent = this.running ? '\u23f8 \u6682\u505c' : '\u25b6 \u64ad\u653e';
            if (this.running) { this.lastTime = performance.now(); this.loop(); }
        });

        const resetBtn = document.getElementById('energy-reset');
        if (resetBtn) this._on(resetBtn, 'click', () => {
            this.ballPos = 0;
            this.ballSpeed = 0;
            this.running = true;
            this.lastTime = performance.now();
            const pb = document.getElementById('energy-play');
            if (pb) pb.textContent = '\u23f8 \u6682\u505c';
            this.loop();
        });
    },

    getHeight(pos) {
        const n = this.trackPoints.length - 1;
        const i = pos * n;
        const i0 = Math.floor(i);
        const i1 = Math.min(i0 + 1, n);
        const t = i - i0;
        return this.trackPoints[i0] * (1 - t) + this.trackPoints[i1] * t;
    },

    getSlope(pos) {
        const dp = 0.002;
        const h1 = this.getHeight(Math.max(0, pos - dp));
        const h2 = this.getHeight(Math.min(1, pos + dp));
        return (h2 - h1) / (dp * 2);
    },

    loop() {
        if (!this.running) return;
        const now = performance.now();
        const dt = Math.min((now - this.lastTime) / 1000, 0.03);
        this.lastTime = now;

        // Physics: energy-based approach
        const slope = this.getSlope(this.ballPos);
        const trackScale = 5; // world height scale
        const accel = -this.g * slope * trackScale;
        const frictionDecel = this.friction * (this.ballSpeed > 0 ? 1 : -1) * this.g;

        this.ballSpeed += (accel - frictionDecel) * dt;
        this.ballPos += this.ballSpeed * dt * 0.15;

        // Clamp
        if (this.ballPos < 0) { this.ballPos = 0; this.ballSpeed = Math.abs(this.ballSpeed) * 0.8; }
        if (this.ballPos > 1) { this.ballPos = 1; this.ballSpeed = -Math.abs(this.ballSpeed) * 0.8; }

        this.draw();
        this._raf = requestAnimationFrame(() => this.loop());
    },

    draw() {
        const { ctx, W, H } = this;
        if (!ctx || W === 0) return;
        ctx.clearRect(0, 0, W, H);

        const trackArea = { x: 20, y: 20, w: W * 0.65, h: H - 40 };
        const barArea = { x: W * 0.7, y: 20, w: W * 0.25, h: H - 60 };

        this.drawTrack(trackArea);
        this.drawBall(trackArea);
        this.drawEnergyBars(barArea);
        this.drawStats(trackArea);
    },

    drawTrack(area) {
        const { ctx } = this;
        const n = this.trackPoints.length;

        ctx.strokeStyle = this.colors.track;
        ctx.lineWidth = 2;
        ctx.beginPath();
        for (let i = 0; i < n; i++) {
            const x = area.x + (i / (n - 1)) * area.w;
            const y = area.y + area.h - this.trackPoints[i] * area.h;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();

        // Fill below track
        ctx.lineTo(area.x + area.w, area.y + area.h);
        ctx.lineTo(area.x, area.y + area.h);
        ctx.closePath();
        ctx.fillStyle = 'rgba(139,111,192,0.05)';
        ctx.fill();
    },

    drawBall(area) {
        const { ctx } = this;
        const h = this.getHeight(this.ballPos);
        const x = area.x + this.ballPos * area.w;
        const y = area.y + area.h - h * area.h;

        ctx.fillStyle = this.colors.ball;
        ctx.shadowColor = this.colors.ball;
        ctx.shadowBlur = 10;
        ctx.beginPath();
        ctx.arc(x, y - 6, 7, 0, Math.PI * 2);
        ctx.fill();
        ctx.shadowBlur = 0;

        // Height dashed line
        ctx.strokeStyle = 'rgba(91,141,206,0.2)';
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(x, y);
        ctx.lineTo(x, area.y + area.h);
        ctx.stroke();
        ctx.setLineDash([]);

        // h label
        ctx.fillStyle = 'rgba(91,141,206,0.5)';
        ctx.font = '10px var(--font-mono)';
        ctx.textAlign = 'left';
        ctx.fillText('h=' + (h * 5).toFixed(1) + 'm', x + 8, (y + area.y + area.h) / 2);
    },

    drawEnergyBars(area) {
        const { ctx } = this;
        const h = this.getHeight(this.ballPos);
        const heightM = h * 5;
        const v = Math.abs(this.ballSpeed) * 0.15 * 5;
        const m = this.mass;

        const PE = m * this.g * heightM;
        const KE = 0.5 * m * v * v;
        const total = PE + KE;
        const maxE = Math.max(total, m * this.g * 0.85 * 5) * 1.1;

        const barW = 30;
        const gap = 20;
        const labels = ['PE', 'KE', 'E'];
        const colors = [this.colors.pe, this.colors.ke, this.colors.total];
        const values = [PE, KE, total];

        labels.forEach((label, i) => {
            const x = area.x + i * (barW + gap);
            const barH = (values[i] / maxE) * area.h;
            const y = area.y + area.h - barH;

            ctx.fillStyle = colors[i];
            ctx.globalAlpha = 0.7;
            ctx.fillRect(x, y, barW, barH);
            ctx.globalAlpha = 1;

            // Label
            ctx.fillStyle = colors[i];
            ctx.font = 'bold 11px var(--font-sans)';
            ctx.textAlign = 'center';
            ctx.fillText(label, x + barW / 2, area.y + area.h + 16);

            // Value
            ctx.font = '10px var(--font-mono)';
            ctx.fillText(values[i].toFixed(1) + 'J', x + barW / 2, y - 4);
        });
    },

    drawStats(area) {
        const { ctx } = this;
        const h = this.getHeight(this.ballPos);
        const v = Math.abs(this.ballSpeed) * 0.15 * 5;
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.font = '10px var(--font-mono)';
        ctx.textAlign = 'left';
        ctx.fillText('v = ' + v.toFixed(2) + ' m/s', area.x, area.y + area.h + 16);
    },

    /* ── education panel ── */
    updateInfo() {
        const el = document.getElementById('energy-info');
        if (!el) return;
        const fricDesc = this.friction > 0
            ? `摩擦系数 μ = ${this.friction.toFixed(2)}，机械能逐渐减少转化为内能`
            : '无摩擦，机械能守恒 E<sub>k</sub> + E<sub>p</sub> = 常数';
        el.innerHTML = `<div class="ac-hd"><span class="ac-tag">能量</span>机械能守恒定律</div>
<div class="ac-row"><span class="ac-key">动能</span>E<sub>k</sub> = ½mv² — 物体由于运动而具有的能量</div>
<div class="ac-row"><span class="ac-key ac-key--purple">重力势能</span>E<sub>p</sub> = mgh — 物体由于被举高而具有的能量（以轨道最低点为零势面）</div>
<div class="ac-row"><span class="ac-key ac-key--amber">动能定理</span>W<sub>合</sub> = ΔE<sub>k</sub> — 合力做的功等于动能的变化量</div>
<div class="ac-row"><span class="ac-key">守恒条件</span>只有重力（或弹力）做功时，机械能守恒: E<sub>k1</sub> + E<sub>p1</sub> = E<sub>k2</sub> + E<sub>p2</sub></div>
<div class="ac-note">💡 人教版必修2：${fricDesc}。观察 PE/KE 柱形图的此消彼长理解能量转化</div>`;
    }
};

function initEnergyConservation() {
    EnergyConservation.init();
}

window.EnergyConservation = EnergyConservation;
window.initEnergyConservation = initEnergyConservation;
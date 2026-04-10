// ===== 波动演示引擎 =====

const WaveDemo = {
    canvas: null,
    ctx: null,
    animId: null,
    time: 0,
    running: true,

    // 波 1 参数
    A1: 60,      // 振幅 px
    f1: 1.2,     // 频率 Hz
    λ1: 200,     // 波长 px
    φ1: 0,       // 初相位 rad

    // 波 2 参数
    A2: 60,
    f2: 1.2,
    λ2: 200,
    φ2: 0,

    showWave1: true,
    showWave2: true,
    showSum: true,

    // 颜色
    COLOR_W1: '#ef4444',    // 红
    COLOR_W2: '#3b82f6',    // 蓝
    COLOR_SUM: '#a78bfa',   // 紫

    init() {
        this.canvas = document.getElementById('wave-canvas');
        if (!this.canvas) return;

        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
        this.bindControls();

        window.addEventListener('resize', () => this.resizeCanvas());
        this.start();
    },

    resizeCanvas() {
        if (!this.canvas) return;
        const container = this.canvas.parentElement;
        const rect = container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = rect.width;
        this.H = rect.height;
    },

    /* ── 控件绑定 ── */
    bindControls() {
        const bind = (id, prop, displayId, format) => {
            const el = document.getElementById(id);
            if (!el) return;
            el.addEventListener('input', (e) => {
                this[prop] = parseFloat(e.target.value);
                const display = document.getElementById(displayId);
                if (display) display.textContent = format ? format(this[prop]) : this[prop];
            });
        };

        bind('wave-a1', 'A1', 'wave-a1-value');
        bind('wave-f1', 'f1', 'wave-f1-value', v => v.toFixed(1));
        bind('wave-l1', 'λ1', 'wave-l1-value');

        bind('wave-a2', 'A2', 'wave-a2-value');
        bind('wave-f2', 'f2', 'wave-f2-value', v => v.toFixed(1));
        bind('wave-l2', 'λ2', 'wave-l2-value');

        // Toggle visibility
        const t1 = document.getElementById('wave-show1');
        const t2 = document.getElementById('wave-show2');
        const ts = document.getElementById('wave-show-sum');
        if (t1) t1.addEventListener('change', e => { this.showWave1 = e.target.checked; });
        if (t2) t2.addEventListener('change', e => { this.showWave2 = e.target.checked; });
        if (ts) ts.addEventListener('change', e => { this.showSum = e.target.checked; });

        // Presets
        const presetBtns = document.querySelectorAll('[data-wave-preset]');
        presetBtns.forEach(btn => {
            btn.addEventListener('click', () => {
                this.applyPreset(btn.dataset.wavePreset);
                presetBtns.forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
            });
        });

        // Pause
        const pauseBtn = document.getElementById('wave-pause');
        if (pauseBtn) {
            pauseBtn.addEventListener('click', () => {
                this.running = !this.running;
                pauseBtn.textContent = this.running ? '暂停' : '继续';
                if (this.running) this.start();
            });
        }

        // Reset time
        const resetBtn = document.getElementById('wave-reset');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.time = 0;
            });
        }
    },

    /* ── 预设 ── */
    applyPreset(name) {
        const presets = {
            standing: { A1: 60, f1: 1.5, λ1: 200, A2: 60, f2: 1.5, λ2: 200, φ2: Math.PI, note: '同频反向 → 驻波' },
            beat:     { A1: 60, f1: 1.0, λ1: 200, A2: 60, f2: 1.2, λ2: 200, φ2: 0, note: '频率微差 → 拍频' },
            constructive: { A1: 60, f1: 1.2, λ1: 200, A2: 60, f2: 1.2, λ2: 200, φ2: 0, note: '同频同相 → 加强' },
            destructive:  { A1: 60, f1: 1.2, λ1: 200, A2: 60, f2: 1.2, λ2: 200, φ2: Math.PI, note: '同频反相 → 抵消' },
        };
        const p = presets[name];
        if (!p) return;

        this.A1 = p.A1; this.f1 = p.f1; this.λ1 = p.λ1; this.φ1 = 0;
        this.A2 = p.A2; this.f2 = p.f2; this.λ2 = p.λ2; this.φ2 = p.φ2;
        this.time = 0;

        // Sync sliders
        this.syncSlider('wave-a1', p.A1, 'wave-a1-value');
        this.syncSlider('wave-f1', p.f1, 'wave-f1-value', v => v.toFixed(1));
        this.syncSlider('wave-l1', p.λ1, 'wave-l1-value');
        this.syncSlider('wave-a2', p.A2, 'wave-a2-value');
        this.syncSlider('wave-f2', p.f2, 'wave-f2-value', v => v.toFixed(1));
        this.syncSlider('wave-l2', p.λ2, 'wave-l2-value');
    },

    syncSlider(id, value, displayId, format) {
        const el = document.getElementById(id);
        if (el) el.value = value;
        const disp = document.getElementById(displayId);
        if (disp) disp.textContent = format ? format(value) : value;
    },

    /* ── 单个波的 y 值 ── */
    waveY(x, A, f, λ, φ, t) {
        return A * Math.sin(2 * Math.PI * (x / λ - f * t) + φ);
    },

    /* ── 动画循环 ── */
    start() {
        if (this.animId) cancelAnimationFrame(this.animId);
        let last = performance.now();

        const loop = (now) => {
            if (!this.running) return;
            const dt = Math.min((now - last) / 1000, 0.05);
            last = now;
            this.time += dt;
            this.render();
            this.animId = requestAnimationFrame(loop);
        };
        this.animId = requestAnimationFrame(loop);
    },

    /* ── 渲染 ── */
    render() {
        const ctx = this.ctx;
        if (!ctx) return;
        const W = this.W, H = this.H;
        const midY = H / 2;

        ctx.clearRect(0, 0, W, H);

        // 背景网格
        this.drawGrid(midY);

        // 中轴线
        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.moveTo(0, midY); ctx.lineTo(W, midY); ctx.stroke();
        ctx.setLineDash([]);

        // 波形绘制
        if (this.showWave1) this.drawWave(ctx, W, midY, this.A1, this.f1, this.λ1, this.φ1, this.COLOR_W1, 0.5);
        if (this.showWave2) this.drawWave(ctx, W, midY, this.A2, this.f2, this.λ2, this.φ2, this.COLOR_W2, 0.5);

        // 叠加波
        if (this.showSum && (this.showWave1 || this.showWave2)) {
            this.drawSumWave(ctx, W, midY);
        }

        // 振幅标注
        this.drawAmplitudeMarkers(ctx, W, midY);
    },

    drawGrid(midY) {
        const ctx = this.ctx;
        ctx.strokeStyle = 'rgba(255,255,255,0.03)';
        ctx.lineWidth = 0.5;
        const step = 40;
        for (let x = step; x < this.W; x += step) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, this.H); ctx.stroke();
        }
        for (let y = step; y < this.H; y += step) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(this.W, y); ctx.stroke();
        }
    },

    drawWave(ctx, W, midY, A, f, λ, φ, color, alpha) {
        ctx.beginPath();
        ctx.strokeStyle = color;
        ctx.globalAlpha = alpha;
        ctx.lineWidth = 2;

        for (let px = 0; px <= W; px += 2) {
            const y = midY - this.waveY(px, A, f, λ, φ, this.time);
            if (px === 0) ctx.moveTo(px, y);
            else ctx.lineTo(px, y);
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
    },

    drawSumWave(ctx, W, midY) {
        ctx.beginPath();
        ctx.strokeStyle = this.COLOR_SUM;
        ctx.lineWidth = 2.5;
        ctx.shadowColor = this.COLOR_SUM;
        ctx.shadowBlur = 8;

        for (let px = 0; px <= W; px += 2) {
            let y = 0;
            if (this.showWave1) y += this.waveY(px, this.A1, this.f1, this.λ1, this.φ1, this.time);
            if (this.showWave2) y += this.waveY(px, this.A2, this.f2, this.λ2, this.φ2, this.time);
            const screenY = midY - y;
            if (px === 0) ctx.moveTo(px, screenY);
            else ctx.lineTo(px, screenY);
        }
        ctx.stroke();
        ctx.shadowBlur = 0;
    },

    drawAmplitudeMarkers(ctx, W, midY) {
        ctx.font = '500 11px JetBrains Mono, monospace';
        ctx.fillStyle = 'rgba(255,255,255,0.25)';
        ctx.textAlign = 'left';

        // 标注 +A 和 -A
        const maxA = Math.max(this.A1, this.A2);
        if (maxA > 10) {
            ctx.fillText('+A', 6, midY - maxA + 4);
            ctx.fillText('−A', 6, midY + maxA + 12);

            ctx.strokeStyle = 'rgba(255,255,255,0.06)';
            ctx.lineWidth = 0.5;
            ctx.setLineDash([2, 6]);
            ctx.beginPath(); ctx.moveTo(0, midY - maxA); ctx.lineTo(W, midY - maxA); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(0, midY + maxA); ctx.lineTo(W, midY + maxA); ctx.stroke();
            ctx.setLineDash([]);
        }
    }
};

function initWaves() {
    WaveDemo.init();
}

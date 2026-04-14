// ===== Circuit Analysis Visualization =====
// Simple DC circuit with resistors, battery, Ohm's law

const CircuitAnalysis = {
    canvas: null, ctx: null, W: 0, H: 0,
    _listeners: [],
    _resizeObs: null,
    _raf: null,
    time: 0,
    running: true,

    // Circuit params
    voltage: 12,   // V
    R1: 4,         // ohm
    R2: 6,         // ohm
    mode: 'series', // 'series' or 'parallel'

    _on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts);
        this._listeners.push({ el, evt, fn, opts });
    },

    init() {
        this.canvas = document.getElementById('circuit-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.time = 0;
        this.running = true;
        this.resize();
        this.bindEvents();
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
        const wrap = this.canvas.parentElement;
        if (!wrap) return;
        const dpr = window.devicePixelRatio || 1;
        const rect = wrap.getBoundingClientRect();
        const w = rect.width;
        const h = Math.min(w * 0.6, 380);
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w;
        this.H = h;
    },

    bindEvents() {
        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => this.resize());
            this._resizeObs.observe(this.canvas.parentElement);
        }

        const bindSlider = (id, prop) => {
            const el = document.getElementById(id);
            if (!el) return;
            this._on(el, 'input', () => {
                this[prop] = parseFloat(el.value);
                const disp = document.getElementById(id + '-val');
                if (disp) disp.textContent = el.value;
            });
        };
        bindSlider('circuit-voltage', 'voltage');
        bindSlider('circuit-r1', 'R1');
        bindSlider('circuit-r2', 'R2');

        document.querySelectorAll('.circuit-mode-btn').forEach(btn => {
            this._on(btn, 'click', () => {
                document.querySelectorAll('.circuit-mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.mode = btn.dataset.mode;
            });
        });
    },

    loop() {
        if (!this.running) return;
        this.time += 0.016;
        this.draw();
        this._raf = requestAnimationFrame(() => this.loop());
    },

    draw() {
        const { ctx, W, H, mode } = this;
        if (!ctx || W === 0) return;
        ctx.clearRect(0, 0, W, H);

        if (mode === 'series') this.drawSeries();
        else this.drawParallel();

        this.drawStats();
    },

    drawSeries() {
        const { ctx, W, H, time, voltage, R1, R2 } = this;
        const pad = 40;
        const left = pad, right = W - pad, top = pad + 20, bottom = H - pad;
        const midX = W / 2;

        // Wire path: left-top -> right-top -> right-bottom -> left-bottom -> left-top
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(left, top);
        ctx.lineTo(right, top);
        ctx.lineTo(right, bottom);
        ctx.lineTo(left, bottom);
        ctx.lineTo(left, top);
        ctx.stroke();

        // Battery (left side, vertical)
        const batY = (top + bottom) / 2;
        this.drawBattery(left, batY - 20, left, batY + 20, voltage);

        // R1 (top wire)
        const r1x1 = left + (right - left) * 0.25;
        const r1x2 = left + (right - left) * 0.45;
        this.drawResistor(r1x1, top, r1x2, top, 'R\u2081=' + R1 + '\u03a9');

        // R2 (top wire, after R1)
        const r2x1 = left + (right - left) * 0.55;
        const r2x2 = left + (right - left) * 0.75;
        this.drawResistor(r2x1, top, r2x2, top, 'R\u2082=' + R2 + '\u03a9');

        // Current arrows (electron particles along wire path)
        const totalR = R1 + R2;
        const I = voltage / totalR;
        const speed = I * 8;

        // Particles along the rectangular path
        const path = [
            { x: left, y: top }, { x: right, y: top },
            { x: right, y: bottom }, { x: left, y: bottom }
        ];
        this.drawCurrentParticles(path, speed, 20);

        // Current direction arrow
        ctx.fillStyle = 'rgba(229,192,123,0.4)';
        ctx.font = '10px var(--font-sans)';
        ctx.textAlign = 'center';
        ctx.fillText('I = ' + I.toFixed(2) + ' A \u2192', midX, top - 8);
    },

    drawParallel() {
        const { ctx, W, H, time, voltage, R1, R2 } = this;
        const pad = 40;
        const left = pad, right = W - pad, top = pad + 20, bottom = H - pad;
        const cy = (top + bottom) / 2;
        const branchTop = cy - 35;
        const branchBot = cy + 35;

        // Main wire
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 2;

        // Left vertical + horizontal to split
        const splitL = left + (right - left) * 0.3;
        const splitR = left + (right - left) * 0.7;

        ctx.beginPath();
        ctx.moveTo(left, cy);
        ctx.lineTo(splitL, cy);
        ctx.stroke();

        // Split to two branches
        ctx.beginPath();
        ctx.moveTo(splitL, cy); ctx.lineTo(splitL, branchTop);
        ctx.lineTo(splitR, branchTop); ctx.lineTo(splitR, cy);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(splitL, cy); ctx.lineTo(splitL, branchBot);
        ctx.lineTo(splitR, branchBot); ctx.lineTo(splitR, cy);
        ctx.stroke();

        // Continue right + back
        ctx.beginPath();
        ctx.moveTo(splitR, cy);
        ctx.lineTo(right, cy);
        ctx.lineTo(right, bottom);
        ctx.lineTo(left, bottom);
        ctx.lineTo(left, cy);
        ctx.stroke();

        // Battery (bottom)
        const batX = (left + right) / 2;
        this.drawBattery(batX - 15, bottom, batX + 15, bottom, voltage);

        // R1 (top branch)
        const rmidL = (splitL + splitR) / 2 - 25;
        const rmidR = (splitL + splitR) / 2 + 25;
        this.drawResistor(rmidL, branchTop, rmidR, branchTop, 'R\u2081=' + R1 + '\u03a9');

        // R2 (bottom branch)
        this.drawResistor(rmidL, branchBot, rmidR, branchBot, 'R\u2082=' + R2 + '\u03a9');

        // Current
        const I1 = voltage / R1;
        const I2 = voltage / R2;
        const Itotal = I1 + I2;

        // Particles on both branches
        const pathTop = [
            { x: left, y: cy }, { x: splitL, y: cy }, { x: splitL, y: branchTop },
            { x: splitR, y: branchTop }, { x: splitR, y: cy }, { x: right, y: cy },
            { x: right, y: bottom }, { x: left, y: bottom }
        ];
        const pathBot = [
            { x: left, y: cy }, { x: splitL, y: cy }, { x: splitL, y: branchBot },
            { x: splitR, y: branchBot }, { x: splitR, y: cy }, { x: right, y: cy },
            { x: right, y: bottom }, { x: left, y: bottom }
        ];
        this.drawCurrentParticles(pathTop, I1 * 8, 12);
        this.drawCurrentParticles(pathBot, I2 * 8, 10);

        ctx.fillStyle = 'rgba(229,192,123,0.4)';
        ctx.font = '10px var(--font-sans)';
        ctx.textAlign = 'left';
        ctx.fillText('I\u2081=' + I1.toFixed(2) + 'A', splitR + 5, branchTop - 5);
        ctx.fillText('I\u2082=' + I2.toFixed(2) + 'A', splitR + 5, branchBot - 5);
        ctx.textAlign = 'center';
        ctx.fillText('I=' + Itotal.toFixed(2) + 'A', (left + splitL) / 2, cy - 8);
    },

    drawBattery(x1, y1, x2, y2, V) {
        const ctx = this.ctx;
        const mx = (x1 + x2) / 2, my = (y1 + y2) / 2;

        // + and - lines
        ctx.strokeStyle = 'rgba(229,192,123,0.6)';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(mx - 8, my - 5);
        ctx.lineTo(mx + 8, my - 5);
        ctx.stroke();
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(mx - 4, my + 5);
        ctx.lineTo(mx + 4, my + 5);
        ctx.stroke();

        ctx.fillStyle = 'rgba(229,192,123,0.5)';
        ctx.font = '9px var(--font-mono)';
        ctx.textAlign = 'center';
        ctx.fillText(V + 'V', mx + 18, my + 3);
        ctx.fillText('+', mx - 14, my - 3);
        ctx.fillText('\u2212', mx - 14, my + 8);
    },

    drawResistor(x1, y, x2, y2, label) {
        const ctx = this.ctx;
        const len = x2 - x1;
        const n = 5; // zigzag teeth
        const amp = 8;

        ctx.strokeStyle = 'rgba(139,111,192,0.7)';
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(x1, y);
        for (let i = 0; i <= n; i++) {
            const t = i / n;
            const px = x1 + t * len;
            const py = y + (i % 2 === 0 ? -amp : amp) * (i > 0 && i < n ? 1 : 0);
            ctx.lineTo(px, py);
        }
        ctx.lineTo(x2, y);
        ctx.stroke();

        ctx.fillStyle = 'rgba(139,111,192,0.5)';
        ctx.font = '10px var(--font-mono)';
        ctx.textAlign = 'center';
        ctx.fillText(label, (x1 + x2) / 2, y + amp + 14);
    },

    drawCurrentParticles(path, speed, count) {
        const ctx = this.ctx;
        // Calculate total path length
        let totalLen = 0;
        const segs = [];
        for (let i = 0; i < path.length; i++) {
            const a = path[i], b = path[(i + 1) % path.length];
            const d = Math.hypot(b.x - a.x, b.y - a.y);
            segs.push({ a, b, d, cumLen: totalLen });
            totalLen += d;
        }

        for (let i = 0; i < count; i++) {
            const offset = ((i / count) * totalLen + this.time * speed * 30) % totalLen;
            let pos = null;
            for (const seg of segs) {
                if (offset >= seg.cumLen && offset < seg.cumLen + seg.d) {
                    const t = (offset - seg.cumLen) / seg.d;
                    pos = {
                        x: seg.a.x + (seg.b.x - seg.a.x) * t,
                        y: seg.a.y + (seg.b.y - seg.a.y) * t
                    };
                    break;
                }
            }
            if (!pos) {
                const last = segs[segs.length - 1];
                pos = { x: last.b.x, y: last.b.y };
            }
            ctx.fillStyle = 'rgba(91,141,206,0.6)';
            ctx.beginPath();
            ctx.arc(pos.x, pos.y, 2.5, 0, Math.PI * 2);
            ctx.fill();
        }
    },

    drawStats() {
        const { ctx, W, H, voltage, R1, R2, mode } = this;
        let Req, I, P;
        if (mode === 'series') {
            Req = R1 + R2;
            I = voltage / Req;
        } else {
            Req = (R1 * R2) / (R1 + R2);
            I = voltage / Req;
        }
        P = voltage * I;

        const lines = [
            mode === 'series' ? 'R\u2091q = R\u2081+R\u2082 = ' + Req.toFixed(1) + ' \u03a9' : 'R\u2091q = R\u2081R\u2082/(R\u2081+R\u2082) = ' + Req.toFixed(1) + ' \u03a9',
            'I = V/R\u2091q = ' + I.toFixed(2) + ' A',
            'P = VI = ' + P.toFixed(1) + ' W'
        ];

        ctx.fillStyle = 'rgba(255,255,255,0.25)';
        ctx.font = '11px var(--font-mono)';
        ctx.textAlign = 'right';
        lines.forEach((l, i) => {
            ctx.fillText(l, W - 15, H - 10 - (lines.length - 1 - i) * 16);
        });
    }
};

function initCircuitAnalysis() {
    CircuitAnalysis.init();
}

window.CircuitAnalysis = CircuitAnalysis;
window.initCircuitAnalysis = initCircuitAnalysis;
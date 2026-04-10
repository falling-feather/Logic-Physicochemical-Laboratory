// ===== 微积分可视化 =====

const Calculus = {
    canvas: null,
    ctx: null,
    // Current state
    expr: 'sin(x)',
    fn: null,
    dfn: null, // numerical derivative
    mode: 'derivative', // 'derivative' | 'integral'
    param: 0,   // x-position for tangent line; or integration upper bound
    xmin: -8, xmax: 8,
    ymin: -3, ymax: 3,
    animating: false,
    animId: null,
    showFunction: true,
    showDerivative: true,

    init() {
        this.canvas = document.getElementById('calculus-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.compileExpr();
        this.bindControls();
        this.draw();
    },

    bindControls() {
        const exprInput = document.getElementById('calc-expr');
        if (exprInput) {
            exprInput.addEventListener('input', () => {
                this.expr = exprInput.value;
                this.compileExpr();
                this.draw();
            });
        }

        const slider = document.getElementById('calc-param');
        if (slider) {
            slider.addEventListener('input', (e) => {
                this.param = parseFloat(e.target.value);
                const lbl = document.getElementById('calc-param-value');
                if (lbl) lbl.textContent = this.param.toFixed(2);
                this.draw();
            });
        }

        // Canvas mouse interaction: move tangent point / integral bound
        if (this.canvas) {
            this.canvas.addEventListener('mousemove', (e) => {
                if (this.animating) return;
                const rect = this.canvas.getBoundingClientRect();
                const mx = (e.clientX - rect.left) / rect.width;
                const x = this.xmin + (this.xmax - this.xmin) * mx;
                this.param = Math.round(x * 100) / 100;
                const slider = document.getElementById('calc-param');
                if (slider) slider.value = this.param;
                const lbl = document.getElementById('calc-param-value');
                if (lbl) lbl.textContent = this.param.toFixed(2);
                this.draw();
            });

            this.canvas.addEventListener('mouseleave', () => {
                // keep current param
            });
        }
    },

    compileExpr() {
        if (typeof compileExpression === 'function') {
            this.fn = compileExpression(this.expr);
        } else {
            // Fallback: basic eval with safety
            this.fn = this._basicCompile(this.expr);
        }
    },

    _basicCompile(exprStr) {
        let s = exprStr.trim();
        if (!s) return null;
        const funcs = {
            sin: 'Math.sin', cos: 'Math.cos', tan: 'Math.tan',
            abs: 'Math.abs', sqrt: 'Math.sqrt', exp: 'Math.exp',
            log: 'Math.log10', ln: 'Math.log'
        };
        for (const [k, v] of Object.entries(funcs)) {
            s = s.replace(new RegExp('\\b' + k + '\\s*\\(', 'g'), v + '(');
        }
        s = s.replace(/\bpi\b/gi, 'Math.PI');
        // Power
        s = s.replace(/\^/g, '**');
        try { return new Function('x', 'return (' + s + ')'); }
        catch (e) { return null; }
    },

    evaluate(x) {
        if (!this.fn) return NaN;
        try { const y = this.fn(x); return isFinite(y) ? y : NaN; }
        catch (e) { return NaN; }
    },

    derivative(x) {
        const h = 1e-6;
        const yp = this.evaluate(x + h);
        const ym = this.evaluate(x - h);
        if (isNaN(yp) || isNaN(ym)) return NaN;
        return (yp - ym) / (2 * h);
    },

    numericalIntegral(a, b) {
        // Simpson's rule
        const n = 200;
        const dx = (b - a) / n;
        let sum = this.evaluate(a) + this.evaluate(b);
        for (let i = 1; i < n; i++) {
            const x = a + i * dx;
            sum += this.evaluate(x) * (i % 2 === 0 ? 2 : 4);
        }
        return sum * dx / 3;
    },

    sizeCanvas() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.parentElement.getBoundingClientRect();
        const w = Math.round(rect.width);
        const h = Math.round(Math.max(w * 0.55, 280));
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        return { w, h };
    },

    mapX(x, w) { return ((x - this.xmin) / (this.xmax - this.xmin)) * w; },
    mapY(y, h) { return ((this.ymax - y) / (this.ymax - this.ymin)) * h; },

    draw() {
        if (!this.ctx) return;
        const { w, h } = this.sizeCanvas();
        const ctx = this.ctx;

        // Background
        ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface-2').trim() || '#151822';
        ctx.fillRect(0, 0, w, h);

        // Grid
        this.drawGrid(ctx, w, h);

        // Axes
        this.drawAxes(ctx, w, h);

        if (!this.fn) {
            this.setInfo('无法解析表达式');
            return;
        }

        if (this.mode === 'integral') {
            this.drawIntegral(ctx, w, h);
        }

        // Draw function curve
        if (this.showFunction) {
            this.drawCurve(ctx, w, h, (x) => this.evaluate(x), '#5b8dce', 2.5);
        }

        if (this.mode === 'derivative') {
            this.drawTangent(ctx, w, h);
            // Draw derivative curve (dimmer)
            if (this.showDerivative) {
                this.drawCurve(ctx, w, h, (x) => this.derivative(x), 'rgba(196,121,58,0.5)', 1.5);
            }
        }

        this.updateInfo();
    },

    drawGrid(ctx, w, h) {
        ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 1;
        const step = this.niceStep(this.xmax - this.xmin);
        for (let gx = Math.ceil(this.xmin / step) * step; gx <= this.xmax; gx += step) {
            const px = this.mapX(gx, w);
            ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, h); ctx.stroke();
        }
        const stepY = this.niceStep(this.ymax - this.ymin);
        for (let gy = Math.ceil(this.ymin / stepY) * stepY; gy <= this.ymax; gy += stepY) {
            const py = this.mapY(gy, h);
            ctx.beginPath(); ctx.moveTo(0, py); ctx.lineTo(w, py); ctx.stroke();
        }
    },

    drawAxes(ctx, w, h) {
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 1.5;
        // X axis
        if (this.ymin <= 0 && this.ymax >= 0) {
            const ay = this.mapY(0, h);
            ctx.beginPath(); ctx.moveTo(0, ay); ctx.lineTo(w, ay); ctx.stroke();
        }
        // Y axis
        if (this.xmin <= 0 && this.xmax >= 0) {
            const ax = this.mapX(0, w);
            ctx.beginPath(); ctx.moveTo(ax, 0); ctx.lineTo(ax, h); ctx.stroke();
        }

        // Labels
        ctx.fillStyle = 'rgba(255,255,255,0.2)';
        ctx.font = '10px monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        const step = this.niceStep(this.xmax - this.xmin);
        for (let lx = Math.ceil(this.xmin / step) * step; lx <= this.xmax; lx += step) {
            if (Math.abs(lx) < 1e-10) continue;
            const px = this.mapX(lx, w);
            const ay = this.ymin <= 0 && this.ymax >= 0 ? this.mapY(0, h) : h;
            ctx.fillText(this.fmt(lx), px, Math.min(ay + 3, h - 12));
        }
    },

    drawCurve(ctx, w, h, fn, color, lineWidth) {
        ctx.strokeStyle = color;
        ctx.lineWidth = lineWidth;
        ctx.lineJoin = 'round';
        ctx.beginPath();
        let drawing = false;
        const steps = w * 2;
        for (let i = 0; i <= steps; i++) {
            const x = this.xmin + (this.xmax - this.xmin) * (i / steps);
            const y = fn(x);
            if (isNaN(y) || !isFinite(y) || y < this.ymin - (this.ymax - this.ymin) * 2 || y > this.ymax + (this.ymax - this.ymin) * 2) {
                drawing = false; continue;
            }
            const px = this.mapX(x, w), py = this.mapY(y, h);
            if (!drawing) { ctx.moveTo(px, py); drawing = true; }
            else ctx.lineTo(px, py);
        }
        ctx.stroke();
    },

    drawTangent(ctx, w, h) {
        const x0 = this.param;
        const y0 = this.evaluate(x0);
        const slope = this.derivative(x0);
        if (isNaN(y0) || isNaN(slope)) return;

        const px = this.mapX(x0, w);
        const py = this.mapY(y0, h);

        // Tangent line
        const len = (this.xmax - this.xmin) * 0.3;
        const x1 = x0 - len, y1 = y0 - slope * len;
        const x2 = x0 + len, y2 = y0 + slope * len;

        ctx.strokeStyle = '#c4793a';
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.beginPath();
        ctx.moveTo(this.mapX(x1, w), this.mapY(y1, h));
        ctx.lineTo(this.mapX(x2, w), this.mapY(y2, h));
        ctx.stroke();
        ctx.setLineDash([]);

        // Point
        ctx.beginPath();
        ctx.arc(px, py, 6, 0, Math.PI * 2);
        ctx.fillStyle = '#c4793a';
        ctx.shadowColor = '#c4793a';
        ctx.shadowBlur = 12;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Slope label
        ctx.fillStyle = 'rgba(255,255,255,0.7)';
        ctx.font = '12px Inter, sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`斜率 = ${slope.toFixed(3)}`, px + 10, py - 10);
    },

    drawIntegral(ctx, w, h) {
        const a = 0; // lower bound fixed at 0
        const b = this.param;
        if (Math.abs(b - a) < 0.01) return;

        const lo = Math.min(a, b), hi = Math.max(a, b);
        const sign = b >= a ? 1 : -1;
        const steps = Math.max(Math.round(Math.abs(hi - lo) / ((this.xmax - this.xmin) / w)), 2);
        const dx = (hi - lo) / steps;

        // Fill area
        ctx.beginPath();
        ctx.moveTo(this.mapX(lo, w), this.mapY(0, h));
        for (let i = 0; i <= steps; i++) {
            const x = lo + i * dx;
            const y = this.evaluate(x);
            if (isNaN(y)) continue;
            ctx.lineTo(this.mapX(x, w), this.mapY(y, h));
        }
        ctx.lineTo(this.mapX(hi, w), this.mapY(0, h));
        ctx.closePath();

        const area = this.numericalIntegral(lo, hi) * sign;
        ctx.fillStyle = area >= 0
            ? 'rgba(77,158,126,0.2)'
            : 'rgba(184,84,80,0.2)';
        ctx.fill();

        // Boundary lines
        ctx.strokeStyle = 'rgba(255,255,255,0.2)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 3]);
        [lo, hi].forEach(bx => {
            const px = this.mapX(bx, w);
            ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, h); ctx.stroke();
        });
        ctx.setLineDash([]);

        // Area label
        const midX = this.mapX((lo + hi) / 2, w);
        const midY = this.mapY(0, h) - 20;
        ctx.fillStyle = area >= 0 ? '#4d9e7e' : '#b85450';
        ctx.font = 'bold 13px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(`∫ = ${area.toFixed(4)}`, midX, midY);
    },

    updateInfo() {
        const x = this.param;
        const y = this.evaluate(x);
        let text = '';
        if (this.mode === 'derivative') {
            const slope = this.derivative(x);
            text = `f(${x.toFixed(2)}) = ${isNaN(y) ? '—' : y.toFixed(4)}   |   f'(${x.toFixed(2)}) = ${isNaN(slope) ? '—' : slope.toFixed(4)}`;
        } else {
            const area = this.numericalIntegral(0, x);
            text = `f(${x.toFixed(2)}) = ${isNaN(y) ? '—' : y.toFixed(4)}   |   ∫₀^${x.toFixed(1)} f(t)dt = ${isNaN(area) ? '—' : area.toFixed(4)}`;
        }
        this.setInfo(text);
    },

    setInfo(text) {
        const el = document.getElementById('calc-info');
        if (el) el.textContent = text;
    },

    setMode(mode) {
        this.mode = mode;
        document.querySelectorAll('.calc-mode-btn').forEach(b => {
            b.classList.remove('active');
            if (b.textContent.trim().toLowerCase().includes(mode === 'derivative' ? '导' : mode === 'integral' ? '积' : '极')) b.classList.add('active');
        });
        this.draw();
    },

    setPreset(name) {
        const presets = {
            'sin(x)': { expr: 'sin(x)', xmin: -8, xmax: 8, ymin: -2, ymax: 2 },
            'x^2': { expr: 'x^2', xmin: -4, xmax: 4, ymin: -1, ymax: 8 },
            'x^3-3*x': { expr: 'x^3-3*x', xmin: -3, xmax: 3, ymin: -5, ymax: 5 },
            'exp(-x^2)': { expr: 'exp(-x^2)', xmin: -4, xmax: 4, ymin: -0.5, ymax: 1.5 },
            '1/(1+x^2)': { expr: '1/(1+x^2)', xmin: -6, xmax: 6, ymin: -0.5, ymax: 1.5 },
            'cos(x)*x': { expr: 'cos(x)*x', xmin: -10, xmax: 10, ymin: -8, ymax: 8 }
        };
        const p = presets[name];
        if (!p) return;
        this.expr = p.expr;
        this.xmin = p.xmin; this.xmax = p.xmax;
        this.ymin = p.ymin; this.ymax = p.ymax;
        const exprInput = document.getElementById('calc-expr');
        if (exprInput) exprInput.value = p.expr;
        this.compileExpr();
        this.param = 0;
        const slider = document.getElementById('calc-param');
        if (slider) slider.value = 0;
        const lbl = document.getElementById('calc-param-value');
        if (lbl) lbl.textContent = '0.00';
        // Update active button
        document.querySelectorAll('.calc-presets .btn--ghost').forEach(b => {
            b.classList.remove('active');
            if (b.textContent.trim().includes(name)) b.classList.add('active');
        });
        this.draw();
    },

    animate() {
        if (this.animating) { this.stopAnimate(); return; }
        this.animating = true;
        let t = this.xmin;
        const animBtn = document.getElementById('calc-animate-btn');
        if (animBtn) animBtn.textContent = '⏸ 暂停';

        const step = () => {
            if (!this.animating) return;
            t += 0.05;
            if (t > this.xmax) t = this.xmin;
            this.param = Math.round(t * 100) / 100;
            const slider = document.getElementById('calc-param');
            if (slider) slider.value = this.param;
            const lbl = document.getElementById('calc-param-value');
            if (lbl) lbl.textContent = this.param.toFixed(2);
            this.draw();
            this.animId = requestAnimationFrame(step);
        };
        this.animId = requestAnimationFrame(step);
    },

    stopAnimate() {
        this.animating = false;
        if (this.animId) cancelAnimationFrame(this.animId);
        this.animId = null;
        const animBtn = document.getElementById('calc-animate-btn');
        if (animBtn) animBtn.textContent = '▶ 动画';
    },

    niceStep(range) {
        const rough = range / 8;
        const mag = Math.pow(10, Math.floor(Math.log10(rough)));
        const norm = rough / mag;
        if (norm < 1.5) return mag;
        if (norm < 3.5) return 2 * mag;
        if (norm < 7.5) return 5 * mag;
        return 10 * mag;
    },

    fmt(n) {
        return Math.abs(n) >= 1000 || (Math.abs(n) < 0.01 && n !== 0)
            ? n.toExponential(1) : parseFloat(n.toPrecision(4)).toString();
    }
};

// ── 初始化 ──
function initCalculus() {
    Calculus.init();
    let resizeT;
    window.addEventListener('resize', () => {
        clearTimeout(resizeT);
        resizeT = setTimeout(() => Calculus.draw(), 200);
    });
}

window.Calculus = Calculus;
window.initCalculus = initCalculus;

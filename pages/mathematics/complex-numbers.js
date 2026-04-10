// ===== Complex Numbers Visualization =====
const ComplexVis = {
    canvas: null,
    ctx: null,
    // Two complex numbers: z1 and z2
    z1: { re: 2, im: 1 },
    z2: { re: -1, im: 2 },
    operation: 'add', // add, sub, mul, div, pow, euler
    dragging: null, // 'z1' | 'z2' | null
    eulerTheta: 0,
    eulerAnimId: null,
    viewRange: 6, // ±6

    init() {
        this.canvas = document.getElementById('complex-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        this.bindControls();
        this.draw();
        window.addEventListener('resize', () => { this.resize(); this.draw(); });
    },

    resize() {
        const wrap = this.canvas.parentElement;
        const w = wrap.clientWidth;
        const h = Math.min(w, 520);
        this.canvas.width = w * devicePixelRatio;
        this.canvas.height = h * devicePixelRatio;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
        this.W = w;
        this.H = h;
    },

    bindControls() {
        // Operation buttons
        document.querySelectorAll('.cx-op-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.cx-op-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.operation = btn.dataset.op;
                this.toggleEulerPanel();
                this.draw();
                this.updateInfo();
            });
        });

        // Input fields
        ['z1-re', 'z1-im', 'z2-re', 'z2-im'].forEach(id => {
            const el = document.getElementById('cx-' + id);
            if (el) el.addEventListener('input', () => {
                const v = parseFloat(el.value);
                if (isNaN(v)) return;
                if (id === 'z1-re') this.z1.re = v;
                else if (id === 'z1-im') this.z1.im = v;
                else if (id === 'z2-re') this.z2.re = v;
                else if (id === 'z2-im') this.z2.im = v;
                this.draw();
                this.updateInfo();
            });
        });

        // Euler theta slider
        const thetaSlider = document.getElementById('cx-theta');
        if (thetaSlider) {
            thetaSlider.addEventListener('input', () => {
                this.eulerTheta = parseFloat(thetaSlider.value);
                document.getElementById('cx-theta-val').textContent = (this.eulerTheta * 180 / Math.PI).toFixed(0);
                this.draw();
                this.updateInfo();
            });
        }

        // Canvas drag interaction
        this.canvas.addEventListener('mousedown', e => this.onPointerDown(e));
        this.canvas.addEventListener('mousemove', e => this.onPointerMove(e));
        this.canvas.addEventListener('mouseup', () => this.dragging = null);
        this.canvas.addEventListener('mouseleave', () => this.dragging = null);
        this.canvas.addEventListener('touchstart', e => { e.preventDefault(); this.onPointerDown(e.touches[0]); }, { passive: false });
        this.canvas.addEventListener('touchmove', e => { e.preventDefault(); this.onPointerMove(e.touches[0]); }, { passive: false });
        this.canvas.addEventListener('touchend', () => this.dragging = null);

        // Presets
        document.querySelectorAll('.cx-preset-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const p = btn.dataset.preset;
                this.loadPreset(p);
            });
        });

        // Euler animate button
        const animBtn = document.getElementById('cx-euler-anim');
        if (animBtn) animBtn.addEventListener('click', () => this.animateEuler());
    },

    toggleEulerPanel() {
        const eulerPanel = document.getElementById('cx-euler-panel');
        const inputsPanel = document.querySelector('.cx-inputs');
        const presetsPanel = document.querySelector('.cx-presets');
        if (this.operation === 'euler') {
            if (eulerPanel) eulerPanel.style.display = 'flex';
            if (inputsPanel) inputsPanel.style.display = 'none';
            if (presetsPanel) presetsPanel.style.display = 'none';
        } else {
            if (eulerPanel) eulerPanel.style.display = 'none';
            if (inputsPanel) inputsPanel.style.display = '';
            if (presetsPanel) presetsPanel.style.display = '';
        }
    },

    screenToComplex(px, py) {
        const r = this.viewRange;
        return {
            re: (px / this.W - 0.5) * 2 * r,
            im: -(py / this.H - 0.5) * 2 * r * (this.H / this.W)
        };
    },

    complexToScreen(re, im) {
        const r = this.viewRange;
        return {
            x: (re / (2 * r) + 0.5) * this.W,
            y: (-im / (2 * r * (this.H / this.W)) + 0.5) * this.H
        };
    },

    onPointerDown(e) {
        const rect = this.canvas.getBoundingClientRect();
        const px = e.clientX - rect.left;
        const py = e.clientY - rect.top;
        const c = this.screenToComplex(px, py);

        // Check proximity to z1 or z2
        const d1 = Math.hypot(c.re - this.z1.re, c.im - this.z1.im);
        const d2 = Math.hypot(c.re - this.z2.re, c.im - this.z2.im);
        const threshold = this.viewRange * 0.08;
        if (d1 < threshold && d1 <= d2) this.dragging = 'z1';
        else if (d2 < threshold) this.dragging = 'z2';
    },

    onPointerMove(e) {
        if (!this.dragging) return;
        const rect = this.canvas.getBoundingClientRect();
        const px = e.clientX - rect.left;
        const py = e.clientY - rect.top;
        const c = this.screenToComplex(px, py);
        // Snap to 0.5 grid
        const snap = v => Math.round(v * 2) / 2;
        if (this.dragging === 'z1') {
            this.z1.re = snap(c.re);
            this.z1.im = snap(c.im);
            this.syncInputs();
        } else if (this.dragging === 'z2') {
            this.z2.re = snap(c.re);
            this.z2.im = snap(c.im);
            this.syncInputs();
        }
        this.draw();
        this.updateInfo();
    },

    syncInputs() {
        const set = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
        set('cx-z1-re', this.z1.re);
        set('cx-z1-im', this.z1.im);
        set('cx-z2-re', this.z2.re);
        set('cx-z2-im', this.z2.im);
    },

    compute() {
        const { re: a, im: b } = this.z1;
        const { re: c, im: d } = this.z2;
        switch (this.operation) {
            case 'add': return { re: a + c, im: b + d };
            case 'sub': return { re: a - c, im: b - d };
            case 'mul': return { re: a * c - b * d, im: a * d + b * c };
            case 'div': {
                const denom = c * c + d * d;
                if (denom < 1e-12) return { re: NaN, im: NaN };
                return { re: (a * c + b * d) / denom, im: (b * c - a * d) / denom };
            }
            case 'pow': {
                // z1^z2 using exp(z2 * ln(z1))
                const r = Math.hypot(a, b);
                if (r < 1e-12) return { re: 0, im: 0 };
                const theta = Math.atan2(b, a);
                // ln(z1) = ln|z1| + i*arg(z1)
                const lnR = Math.log(r);
                // z2 * ln(z1) = (c + di)(lnR + i*theta)
                const wRe = c * lnR - d * theta;
                const wIm = d * lnR + c * theta;
                const eW = Math.exp(wRe);
                return { re: eW * Math.cos(wIm), im: eW * Math.sin(wIm) };
            }
            case 'euler': {
                const t = this.eulerTheta;
                return { re: Math.cos(t), im: Math.sin(t) };
            }
            default: return { re: 0, im: 0 };
        }
    },

    loadPreset(name) {
        switch (name) {
            case 'unit-roots':
                this.z1 = { re: 1, im: 0 };
                this.z2 = { re: -0.5, im: 0.866 };
                this.operation = 'mul';
                break;
            case 'conjugate':
                this.z1 = { re: 3, im: 2 };
                this.z2 = { re: 3, im: -2 };
                this.operation = 'mul';
                break;
            case 'rotation':
                this.z1 = { re: 2, im: 1 };
                this.z2 = { re: 0, im: 1 };
                this.operation = 'mul';
                break;
            case 'inverse':
                this.z1 = { re: 1, im: 0 };
                this.z2 = { re: 2, im: 1 };
                this.operation = 'div';
                break;
        }
        this.syncInputs();
        // Update active operation button
        document.querySelectorAll('.cx-op-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.op === this.operation);
        });
        this.draw();
        this.updateInfo();
    },

    animateEuler() {
        if (this.eulerAnimId) {
            cancelAnimationFrame(this.eulerAnimId);
            this.eulerAnimId = null;
            const btn = document.getElementById('cx-euler-anim');
            if (btn) btn.textContent = '旋转动画';
            return;
        }
        const btn = document.getElementById('cx-euler-anim');
        if (btn) btn.textContent = '停止';
        // Switch to euler mode
        this.operation = 'euler';
        document.querySelectorAll('.cx-op-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.op === 'euler');
        });
        const startTime = performance.now();
        const loop = (now) => {
            const t = ((now - startTime) / 3000) * 2 * Math.PI; // full rotation in 3s
            this.eulerTheta = t % (2 * Math.PI);
            const slider = document.getElementById('cx-theta');
            if (slider) slider.value = this.eulerTheta;
            document.getElementById('cx-theta-val').textContent = (this.eulerTheta * 180 / Math.PI).toFixed(0);
            this.draw();
            this.updateInfo();
            this.eulerAnimId = requestAnimationFrame(loop);
        };
        this.eulerAnimId = requestAnimationFrame(loop);
    },

    draw() {
        const { ctx, W, H } = this;
        const r = this.viewRange;
        ctx.clearRect(0, 0, W, H);

        // Background
        ctx.fillStyle = '#0d1017';
        ctx.fillRect(0, 0, W, H);

        // Grid
        ctx.strokeStyle = 'rgba(255,255,255,0.06)';
        ctx.lineWidth = 1;
        for (let i = -r; i <= r; i++) {
            const { x } = this.complexToScreen(i, 0);
            const { y } = this.complexToScreen(0, i);
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
        }

        // Axes
        const origin = this.complexToScreen(0, 0);
        ctx.strokeStyle = 'rgba(255,255,255,0.25)';
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(0, origin.y); ctx.lineTo(W, origin.y); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(origin.x, 0); ctx.lineTo(origin.x, H); ctx.stroke();

        // Axis labels
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.font = '12px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        for (let i = -r + 1; i <= r - 1; i++) {
            if (i === 0) continue;
            const { x } = this.complexToScreen(i, 0);
            ctx.fillText(i, x, origin.y + 14);
        }
        ctx.textAlign = 'right';
        for (let i = -r + 1; i <= r - 1; i++) {
            if (i === 0) continue;
            const { y } = this.complexToScreen(0, i);
            ctx.fillText(i + 'i', origin.x - 6, y + 4);
        }
        ctx.fillText('Re', W - 8, origin.y - 6);
        ctx.textAlign = 'left';
        ctx.fillText('Im', origin.x + 6, 14);

        // Unit circle (light reference)
        const uc = this.complexToScreen(1, 0);
        const ucRadius = uc.x - origin.x;
        ctx.strokeStyle = 'rgba(255,255,255,0.08)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);
        ctx.beginPath(); ctx.arc(origin.x, origin.y, ucRadius, 0, Math.PI * 2); ctx.stroke();
        ctx.setLineDash([]);

        if (this.operation === 'euler') {
            this.drawEuler(origin, ucRadius);
        } else {
            this.drawVectors();
        }
    },

    drawVectors() {
        const result = this.compute();
        // Draw z1
        this.drawArrow(0, 0, this.z1.re, this.z1.im, '#5b8dce', 'z₁');
        // Draw z2
        this.drawArrow(0, 0, this.z2.re, this.z2.im, '#8b6fc0', 'z₂');
        // Draw result
        if (!isNaN(result.re) && !isNaN(result.im)) {
            this.drawArrow(0, 0, result.re, result.im, '#4d9e7e', 'w');
        }

        // For add/sub, show parallelogram
        if (this.operation === 'add') {
            this.drawDashed(this.z1.re, this.z1.im, result.re, result.im, '#4d9e7e');
            this.drawDashed(this.z2.re, this.z2.im, result.re, result.im, '#4d9e7e');
        } else if (this.operation === 'sub') {
            this.drawDashed(this.z2.re, this.z2.im, this.z1.re, this.z1.im, '#c4793a');
        }

        // For mul, show angle arc
        if (this.operation === 'mul' || this.operation === 'div') {
            this.drawAngleArc();
        }

        // Point labels at tip
        this.drawPointLabel(this.z1, '#5b8dce', 'z₁');
        this.drawPointLabel(this.z2, '#8b6fc0', 'z₂');
        if (!isNaN(result.re) && !isNaN(result.im)) {
            this.drawPointLabel(result, '#4d9e7e', 'w');
        }
    },

    drawEuler(origin, unitR) {
        const { ctx } = this;
        const t = this.eulerTheta;
        const px = Math.cos(t);
        const py = Math.sin(t);
        const pt = this.complexToScreen(px, py);

        // Highlight unit circle
        ctx.strokeStyle = 'rgba(91,141,206,0.3)';
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(origin.x, origin.y, unitR, 0, Math.PI * 2); ctx.stroke();

        // Angle arc
        ctx.strokeStyle = '#c4793a';
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(origin.x, origin.y, unitR * 0.3, 0, -t, t < 0); ctx.stroke();

        // Angle label
        const labelAngle = t / 2;
        const lx = origin.x + unitR * 0.38 * Math.cos(-labelAngle);
        const ly = origin.y + unitR * 0.38 * Math.sin(-labelAngle);
        ctx.fillStyle = '#c4793a';
        ctx.font = '13px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('θ', lx, ly);

        // Vector from origin to point
        this.drawArrow(0, 0, px, py, '#4d9e7e', 'e^(iθ)');

        // Projection lines (cos and sin)
        const cosP = this.complexToScreen(px, 0);
        ctx.setLineDash([4, 3]);
        ctx.strokeStyle = '#5b8dce';
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(origin.x, origin.y); ctx.lineTo(cosP.x, cosP.y); ctx.stroke();
        ctx.strokeStyle = '#8b6fc0';
        ctx.beginPath(); ctx.moveTo(pt.x, pt.y); ctx.lineTo(cosP.x, cosP.y); ctx.stroke();
        ctx.setLineDash([]);

        // Labels for cos and sin
        ctx.font = '11px "JetBrains Mono", monospace';
        ctx.fillStyle = '#5b8dce';
        ctx.textAlign = 'center';
        ctx.fillText('cos θ = ' + px.toFixed(2), (origin.x + cosP.x) / 2, origin.y + 18);
        ctx.fillStyle = '#8b6fc0';
        ctx.textAlign = 'left';
        ctx.fillText('sin θ = ' + py.toFixed(2), pt.x + 6, (pt.y + cosP.y) / 2);

        // Point dot
        ctx.fillStyle = '#4d9e7e';
        ctx.beginPath(); ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.font = '12px "Inter", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText(`(${px.toFixed(2)}, ${py.toFixed(2)}i)`, pt.x + 10, pt.y - 8);
    },

    drawArrow(fromRe, fromIm, toRe, toIm, color) {
        const { ctx } = this;
        const from = this.complexToScreen(fromRe, fromIm);
        const to = this.complexToScreen(toRe, toIm);
        const dx = to.x - from.x;
        const dy = to.y - from.y;
        const len = Math.hypot(dx, dy);
        if (len < 2) return;

        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(from.x, from.y);
        ctx.lineTo(to.x, to.y);
        ctx.stroke();

        // Arrowhead
        const headLen = Math.min(12, len * 0.3);
        const angle = Math.atan2(dy, dx);
        ctx.fillStyle = color;
        ctx.beginPath();
        ctx.moveTo(to.x, to.y);
        ctx.lineTo(to.x - headLen * Math.cos(angle - 0.3), to.y - headLen * Math.sin(angle - 0.3));
        ctx.lineTo(to.x - headLen * Math.cos(angle + 0.3), to.y - headLen * Math.sin(angle + 0.3));
        ctx.closePath();
        ctx.fill();
    },

    drawDashed(fromRe, fromIm, toRe, toIm, color) {
        const { ctx } = this;
        const from = this.complexToScreen(fromRe, fromIm);
        const to = this.complexToScreen(toRe, toIm);
        ctx.setLineDash([5, 4]);
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.globalAlpha = 0.5;
        ctx.beginPath(); ctx.moveTo(from.x, from.y); ctx.lineTo(to.x, to.y); ctx.stroke();
        ctx.setLineDash([]);
        ctx.globalAlpha = 1;
    },

    drawAngleArc() {
        const { ctx } = this;
        const origin = this.complexToScreen(0, 0);
        const a1 = Math.atan2(this.z1.im, this.z1.re);
        const a2 = Math.atan2(this.z2.im, this.z2.re);
        const result = this.compute();
        const aR = Math.atan2(result.im, result.re);

        const arcR = 25;
        // z1 angle
        ctx.strokeStyle = 'rgba(91,141,206,0.4)';
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.arc(origin.x, origin.y, arcR, 0, -a1, a1 > 0); ctx.stroke();
        // z2 angle
        ctx.strokeStyle = 'rgba(139,111,192,0.4)';
        ctx.beginPath(); ctx.arc(origin.x, origin.y, arcR + 6, 0, -a2, a2 > 0); ctx.stroke();
        // result angle
        ctx.strokeStyle = 'rgba(77,158,126,0.6)';
        ctx.lineWidth = 2;
        ctx.beginPath(); ctx.arc(origin.x, origin.y, arcR + 12, 0, -aR, aR > 0); ctx.stroke();
    },

    drawPointLabel(z, color, label) {
        const { ctx } = this;
        const pt = this.complexToScreen(z.re, z.im);
        // Dot
        ctx.fillStyle = color;
        ctx.beginPath(); ctx.arc(pt.x, pt.y, 5, 0, Math.PI * 2); ctx.fill();
        // Glow
        ctx.shadowColor = color;
        ctx.shadowBlur = 8;
        ctx.beginPath(); ctx.arc(pt.x, pt.y, 3, 0, Math.PI * 2); ctx.fill();
        ctx.shadowBlur = 0;
    },

    fmtComplex(z) {
        const re = z.re.toFixed(2);
        const im = Math.abs(z.im).toFixed(2);
        const sign = z.im >= 0 ? '+' : '−';
        return `${re} ${sign} ${im}i`;
    },

    fmtPolar(z) {
        const r = Math.hypot(z.re, z.im).toFixed(2);
        const theta = (Math.atan2(z.im, z.re) * 180 / Math.PI).toFixed(1);
        return `${r}∠${theta}°`;
    },

    updateInfo() {
        const el = document.getElementById('cx-info');
        if (!el) return;

        if (this.operation === 'euler') {
            const t = this.eulerTheta;
            const deg = (t * 180 / Math.PI).toFixed(1);
            el.innerHTML = `
                <div class="cx-info-row"><span class="cx-label">θ</span><span>= ${t.toFixed(3)} rad (${deg}°)</span></div>
                <div class="cx-info-row"><span class="cx-label">e<sup>iθ</sup></span><span>= ${Math.cos(t).toFixed(4)} + ${Math.sin(t).toFixed(4)}i</span></div>
                <div class="cx-info-row"><span class="cx-label">cos θ</span><span>= ${Math.cos(t).toFixed(4)}</span></div>
                <div class="cx-info-row"><span class="cx-label">sin θ</span><span>= ${Math.sin(t).toFixed(4)}</span></div>
                <div class="cx-formula">e<sup>iθ</sup> = cos θ + i sin θ</div>
            `;
            return;
        }

        const result = this.compute();
        const opSymbols = { add: '+', sub: '−', mul: '×', div: '÷', pow: '^' };
        const opSym = opSymbols[this.operation] || '?';

        let html = `
            <div class="cx-info-row"><span class="cx-label">z₁</span><span>= ${this.fmtComplex(this.z1)} &nbsp; (${this.fmtPolar(this.z1)})</span></div>
            <div class="cx-info-row"><span class="cx-label">z₂</span><span>= ${this.fmtComplex(this.z2)} &nbsp; (${this.fmtPolar(this.z2)})</span></div>
            <div class="cx-info-row cx-result"><span class="cx-label">z₁ ${opSym} z₂</span><span>= ${isNaN(result.re) ? '未定义' : this.fmtComplex(result)} &nbsp; (${isNaN(result.re) ? '—' : this.fmtPolar(result)})</span></div>
        `;

        // Modulus info
        html += `<div class="cx-info-row"><span class="cx-label">|z₁|</span><span>= ${Math.hypot(this.z1.re, this.z1.im).toFixed(3)}</span></div>`;
        html += `<div class="cx-info-row"><span class="cx-label">|z₂|</span><span>= ${Math.hypot(this.z2.re, this.z2.im).toFixed(3)}</span></div>`;
        if (!isNaN(result.re)) {
            html += `<div class="cx-info-row"><span class="cx-label">|w|</span><span>= ${Math.hypot(result.re, result.im).toFixed(3)}</span></div>`;
        }

        if (this.operation === 'mul') {
            html += `<div class="cx-formula">|z₁·z₂| = |z₁|·|z₂|, &nbsp; arg(z₁·z₂) = arg(z₁) + arg(z₂)</div>`;
        } else if (this.operation === 'div') {
            html += `<div class="cx-formula">|z₁/z₂| = |z₁|/|z₂|, &nbsp; arg(z₁/z₂) = arg(z₁) − arg(z₂)</div>`;
        }

        el.innerHTML = html;
    }
};

function initComplexVis() {
    ComplexVis.init();
    ComplexVis.updateInfo();
}

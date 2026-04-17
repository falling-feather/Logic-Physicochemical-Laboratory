/* ═══════════════════════════════════════════════════
   Oxidation-Reduction – Electron Transfer Visualization  v2
   ResizeObserver · DPR · Easing · Trail · Education Panel
   ═══════════════════════════════════════════════════ */
const Redox = {
    _listeners: [],
    _resizeObs: null,
    canvas: null, ctx: null, animId: null,
    W: 0, H: 0,
    running: false,
    paused: false,
    speed: 1.0,
    currentIdx: 0,
    electrons: [],
    completionPulse: 0,
    lastTs: 0,

    reactions: [
        {
            name: 'Fe + CuSO\u2084 \u2192 FeSO\u2084 + Cu',
            type: '\u7f6e\u6362\u53cd\u5e94',
            reducer: { sym: 'Fe', color: '#b0b0b0', afterSym: 'Fe\u00b2\u207a', afterColor: '#5eaaff' },
            oxidizer: { sym: 'Cu\u00b2\u207a', color: '#c87832', afterSym: 'Cu', afterColor: '#d4a050' },
            eCount: 2,
            oxLine: 'Fe: 0 \u2192 +2\u00a0(\u5931\u53bb2e\u207b, \u88ab\u6c27\u5316)',
            redLine: 'Cu\u00b2\u207a: +2 \u2192 0\u00a0(\u5f97\u52302e\u207b, \u88ab\u8fd8\u539f)',
            halfOx: 'Fe \u2212 2e\u207b \u2192 Fe\u00b2\u207a',
            halfRed: 'Cu\u00b2\u207a + 2e\u207b \u2192 Cu',
            note: '\u8f83\u6d3b\u6cfc\u91d1\u5c5e\u7f6e\u6362\u4e0d\u6d3b\u6cfc\u91d1\u5c5e\uff0c\u94c1\u5c06\u94dc\u4ece\u786b\u9178\u94dc\u6eb6\u6db2\u4e2d\u7f6e\u6362\u51fa\u6765'
        },
        {
            name: 'Zn + 2HCl \u2192 ZnCl\u2082 + H\u2082\u2191',
            type: '\u7f6e\u6362\u53cd\u5e94',
            reducer: { sym: 'Zn', color: '#a0a0c8', afterSym: 'Zn\u00b2\u207a', afterColor: '#5e96ff' },
            oxidizer: { sym: 'H\u207a', color: '#ffc832', afterSym: 'H\u2082', afterColor: '#c8c8c8' },
            eCount: 2,
            oxLine: 'Zn: 0 \u2192 +2\u00a0(\u5931\u53bb2e\u207b, \u88ab\u6c27\u5316)',
            redLine: '2H\u207a: +1 \u2192 0\u00a0(\u5f97\u52302e\u207b, \u88ab\u8fd8\u539f)',
            halfOx: 'Zn \u2212 2e\u207b \u2192 Zn\u00b2\u207a',
            halfRed: '2H\u207a + 2e\u207b \u2192 H\u2082\u2191',
            note: '\u6d3b\u6cfc\u91d1\u5c5e\u4e0e\u9178\u53cd\u5e94\u4ea7\u751f\u6c22\u6c14\uff0c\u9524\u4f4d\u4e8e\u6c22\u4e4b\u524d\uff08\u91d1\u5c5e\u6d3b\u52a8\u6027\u5e8f\u5217\uff09'
        },
        {
            name: '2Na + Cl\u2082 \u2192 2NaCl',
            type: '\u5316\u5408\u53cd\u5e94',
            reducer: { sym: 'Na', color: '#ffb464', afterSym: 'Na\u207a', afterColor: '#ffcc88' },
            oxidizer: { sym: 'Cl\u2082', color: '#5eff96', afterSym: 'Cl\u207b', afterColor: '#88ffaa' },
            eCount: 1,
            oxLine: 'Na: 0 \u2192 +1\u00a0(\u5931\u53bb1e\u207b, \u88ab\u6c27\u5316)',
            redLine: 'Cl: 0 \u2192 \u22121\u00a0(\u5f97\u52301e\u207b, \u88ab\u8fd8\u539f)',
            halfOx: 'Na \u2212 e\u207b \u2192 Na\u207a',
            halfRed: 'Cl\u2082 + 2e\u207b \u2192 2Cl\u207b',
            note: '\u5178\u578b\u79bb\u5b50\u5316\u5408\u7269\u751f\u6210\u53cd\u5e94\uff0c\u94a0\u7684\u5916\u5c42 1 \u4e2a\u7535\u5b50\u8f6c\u79fb\u7ed9\u6c2f'
        },
        {
            name: '2Mg + O\u2082 \u2192 2MgO',
            type: '\u5316\u5408\u53cd\u5e94',
            reducer: { sym: 'Mg', color: '#c8dcdc', afterSym: 'Mg\u00b2\u207a', afterColor: '#88c8ff' },
            oxidizer: { sym: 'O\u2082', color: '#ff6464', afterSym: 'O\u00b2\u207b', afterColor: '#ff9696' },
            eCount: 2,
            oxLine: 'Mg: 0 \u2192 +2\u00a0(\u5931\u53bb2e\u207b, \u88ab\u6c27\u5316)',
            redLine: 'O: 0 \u2192 \u22122\u00a0(\u5f97\u52302e\u207b, \u88ab\u8fd8\u539f)',
            halfOx: 'Mg \u2212 2e\u207b \u2192 Mg\u00b2\u207a',
            halfRed: 'O\u2082 + 4e\u207b \u2192 2O\u00b2\u207b',
            note: '\u9541\u5728\u6c27\u6c14\u4e2d\u71c3\u70e7\u53d1\u51fa\u8000\u773c\u767d\u5149\uff0c\u662f\u7ecf\u5178\u6c27\u5316\u8fd8\u539f\u6f14\u793a\u5b9e\u9a8c'
        },
        {
            name: 'H\u2082 + CuO \u2192 Cu + H\u2082O',
            type: '\u7f6e\u6362\u53cd\u5e94',
            reducer: { sym: 'H\u2082', color: '#b8b8e0', afterSym: 'H\u207a', afterColor: '#5e96ff' },
            oxidizer: { sym: 'Cu\u00b2\u207a', color: '#646464', afterSym: 'Cu', afterColor: '#d4a050' },
            eCount: 2,
            oxLine: 'H: 0 \u2192 +1\u00a0(\u5931\u53bb2e\u207b, \u88ab\u6c27\u5316)',
            redLine: 'Cu\u00b2\u207a: +2 \u2192 0\u00a0(\u5f97\u52302e\u207b, \u88ab\u8fd8\u539f)',
            halfOx: 'H\u2082 \u2212 2e\u207b \u2192 2H\u207a',
            halfRed: 'Cu\u00b2\u207a + 2e\u207b \u2192 Cu',
            note: '\u6c22\u6c14\u8fd8\u539f\u6c27\u5316\u94dc\u662f\u7ecf\u5178\u5b9e\u9a8c\uff0c\u9ed1\u8272 CuO \u53d8\u7ea2\u8272 Cu\uff0c\u8bd5\u7ba1\u53e3\u51fa\u73b0\u6c34\u73e0'
        }
    ],

    /* ── helpers ── */
    _on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts);
        this._listeners.push({ el, evt, fn, opts });
    },
    _ease(t) {
        return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
    },

    /* ── lifecycle ── */
    init() {
        this.canvas = document.getElementById('redox-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.running = true;
        this.paused = false;
        this.speed = 1.0;
        this.currentIdx = 0;
        this.completionPulse = 0;
        this.lastTs = 0;
        this._resize();
        this._buildControls();
        this._resetElectrons();
        this._bindEvents();
        this._updateInfo();
        this.animId = requestAnimationFrame(ts => this._loop(ts));
    },

    destroy() {
        this.running = false;
        if (this.animId) { cancelAnimationFrame(this.animId); this.animId = null; }
        for (const l of this._listeners) l.el.removeEventListener(l.evt, l.fn, l.opts);
        this._listeners = [];
        if (this._resizeObs) { this._resizeObs.disconnect(); this._resizeObs = null; }
        const ctrl = document.getElementById('redox-controls');
        if (ctrl) ctrl.innerHTML = '';
        const info = document.getElementById('redox-info');
        if (info) info.innerHTML = '';
    },

    /* ── resize ── */
    _resize() {
        const wrap = this.canvas.parentElement;
        if (!wrap) return;
        const dpr = window.devicePixelRatio || 1;
        const w = wrap.clientWidth;
        const h = Math.min(w * 0.58, 440);
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w;
        this.H = h;
    },

    _bindEvents() {
        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => this._resize());
            this._resizeObs.observe(this.canvas.parentElement);
        }
    },

    /* ── controls ── */
    _buildControls() {
        const ctrl = document.getElementById('redox-controls');
        if (!ctrl) return;
        ctrl.innerHTML = '';

        // reaction select
        const sel = document.createElement('select');
        sel.className = 'redox-select';
        sel.setAttribute('aria-label', '\u9009\u62e9\u53cd\u5e94');
        this.reactions.forEach((r, i) => {
            const opt = document.createElement('option');
            opt.value = i;
            opt.textContent = r.name;
            sel.appendChild(opt);
        });
        this._on(sel, 'change', () => {
            this.currentIdx = parseInt(sel.value);
            this._resetElectrons();
            this._updateInfo();
        });
        ctrl.appendChild(sel);

        // speed slider
        const speedWrap = document.createElement('label');
        speedWrap.className = 'redox-slider-wrap';
        const speedLabel = document.createElement('span');
        speedLabel.className = 'redox-slider-label';
        speedLabel.textContent = '\u901f\u5ea6';
        const speedSlider = document.createElement('input');
        speedSlider.type = 'range';
        speedSlider.min = '0.3';
        speedSlider.max = '3';
        speedSlider.step = '0.1';
        speedSlider.value = '1';
        speedSlider.className = 'redox-slider';
        speedSlider.setAttribute('aria-label', '\u52a8\u753b\u901f\u5ea6');
        const speedVal = document.createElement('span');
        speedVal.className = 'redox-slider-val';
        speedVal.textContent = '1.0x';
        this._on(speedSlider, 'input', () => {
            this.speed = parseFloat(speedSlider.value);
            speedVal.textContent = this.speed.toFixed(1) + 'x';
        });
        speedWrap.appendChild(speedLabel);
        speedWrap.appendChild(speedSlider);
        speedWrap.appendChild(speedVal);
        ctrl.appendChild(speedWrap);

        // pause button
        const pauseBtn = document.createElement('button');
        pauseBtn.className = 'redox-btn';
        pauseBtn.textContent = '\u6682\u505c';
        pauseBtn.setAttribute('aria-label', '\u6682\u505c/\u7ee7\u7eed');
        this._on(pauseBtn, 'click', () => {
            this.paused = !this.paused;
            pauseBtn.textContent = this.paused ? '\u7ee7\u7eed' : '\u6682\u505c';
        });
        ctrl.appendChild(pauseBtn);

        // replay button
        const replayBtn = document.createElement('button');
        replayBtn.className = 'redox-btn';
        replayBtn.textContent = '\u91cd\u64ad';
        replayBtn.setAttribute('aria-label', '\u91cd\u64ad\u52a8\u753b');
        this._on(replayBtn, 'click', () => this._resetElectrons());
        ctrl.appendChild(replayBtn);
    },

    /* ── state ── */
    _resetElectrons() {
        const rxn = this.reactions[this.currentIdx];
        this.electrons = [];
        this.completionPulse = 0;
        for (let i = 0; i < rxn.eCount; i++) {
            this.electrons.push({ progress: -i * 0.25, trail: [], arrived: false });
        }
    },

    _updateInfo() {
        const info = document.getElementById('redox-info');
        if (!info) return;
        const rxn = this.reactions[this.currentIdx];
        info.innerHTML =
            '<div class="redox-info__row">' +
                '<span class="redox-info__tag">' + rxn.type + '</span>' +
                '<span class="redox-info__equation">' + rxn.name + '</span>' +
            '</div>' +
            '<div class="redox-info__half">' +
                '<div class="redox-info__half-ox">' +
                    '<span class="redox-info__label">\u6c27\u5316\uff08\u5931\u7535\u5b50\uff09</span>' +
                    '<code>' + rxn.halfOx + '</code>' +
                    '<small>' + rxn.oxLine + '</small>' +
                '</div>' +
                '<div class="redox-info__half-red">' +
                    '<span class="redox-info__label">\u8fd8\u539f\uff08\u5f97\u7535\u5b50\uff09</span>' +
                    '<code>' + rxn.halfRed + '</code>' +
                    '<small>' + rxn.redLine + '</small>' +
                '</div>' +
            '</div>' +
            '<p class="redox-info__note">\ud83d\udca1 ' + rxn.note + '</p>';
    },

    /* ── animation loop ── */
    _loop(ts) {
        if (!this.running) return;
        this.animId = requestAnimationFrame(t => this._loop(t));
        if (this.paused) { this.lastTs = ts; return; }

        const dt = this.lastTs ? Math.min((ts - this.lastTs) / 1000, 0.05) : 0.016;
        this.lastTs = ts;

        const allDone = this.electrons.every(e => e.arrived);
        if (!allDone) {
            this.electrons.forEach(e => {
                if (!e.arrived) {
                    e.progress += dt * 0.55 * this.speed;
                    if (e.progress >= 1) { e.progress = 1; e.arrived = true; }
                }
            });
        } else {
            this.completionPulse += dt * 3;
        }

        this._draw();
    },

    /* ── drawing ── */
    _draw() {
        const ctx = this.ctx, W = this.W, H = this.H;
        if (!W || !H) return;
        ctx.clearRect(0, 0, W, H);

        const rxn = this.reactions[this.currentIdx];
        const cy = H * 0.44;
        const redX = W * 0.28, oxX = W * 0.72;
        const R = Math.max(24, Math.min(36, W * 0.05));
        const allDone = this.electrons.every(e => e.arrived);
        const fs = Math.max(10, W * 0.019);

        // ── background glow zones ──
        const lg = ctx.createRadialGradient(redX, cy, 0, redX, cy, R * 4);
        lg.addColorStop(0, 'rgba(255,100,100,0.05)');
        lg.addColorStop(1, 'rgba(255,100,100,0)');
        ctx.fillStyle = lg;
        ctx.fillRect(0, 0, W / 2, H);
        const rg = ctx.createRadialGradient(oxX, cy, 0, oxX, cy, R * 4);
        rg.addColorStop(0, 'rgba(100,150,255,0.05)');
        rg.addColorStop(1, 'rgba(100,150,255,0)');
        ctx.fillStyle = rg;
        ctx.fillRect(W / 2, 0, W / 2, H);

        // ── title ──
        ctx.font = `bold ${Math.max(13, W * 0.024)}px ${CF.sans}`;
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(77,158,126,0.9)';
        ctx.fillText(rxn.name, W / 2, 26);

        // ── transfer bridge arcs ──
        const arcH = R * 3.2;
        ctx.save();
        ctx.setLineDash([6, 4]);
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.moveTo(redX, cy - R);
        ctx.quadraticCurveTo(W / 2, cy - R - arcH, oxX, cy - R);
        ctx.strokeStyle = 'rgba(255,120,80,0.22)';
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(oxX, cy + R);
        ctx.quadraticCurveTo(W / 2, cy + R + arcH, redX, cy + R);
        ctx.strokeStyle = 'rgba(80,140,255,0.22)';
        ctx.stroke();
        ctx.restore();

        // arc labels + arrow
        ctx.font = `${fs}px ${CF.sans}`;
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(255,120,80,0.6)';
        ctx.fillText('\u5931\u53bbe\u207b (\u6c27\u5316)', W / 2, cy - R - arcH * 0.62);
        ctx.fillStyle = 'rgba(80,140,255,0.6)';
        ctx.fillText('\u5f97\u5230e\u207b (\u8fd8\u539f)', W / 2, cy + R + arcH * 0.72);

        const arrY = cy - R - arcH * 0.38;
        ctx.fillStyle = 'rgba(255,120,80,0.45)';
        ctx.beginPath();
        ctx.moveTo(W / 2 + 6, arrY - 4);
        ctx.lineTo(W / 2 + 14, arrY);
        ctx.lineTo(W / 2 + 6, arrY + 4);
        ctx.fill();

        // ── atom renderer ──
        const drawAtom = (x, y, color, sym, label, labelCol, pulse) => {
            if (pulse > 0) {
                const pr = R + 8 + Math.sin(pulse) * 5;
                ctx.beginPath();
                ctx.arc(x, y, pr, 0, Math.PI * 2);
                ctx.strokeStyle = `rgba(100,255,180,${(0.35 * Math.abs(Math.sin(pulse))).toFixed(2)})`;
                ctx.lineWidth = 2;
                ctx.stroke();
            }
            ctx.save();
            ctx.setLineDash([3, 3]);
            ctx.beginPath();
            ctx.arc(x, y, R + 10, 0, Math.PI * 2);
            ctx.strokeStyle = 'rgba(200,200,200,0.12)';
            ctx.lineWidth = 1;
            ctx.stroke();
            ctx.restore();
            const g = ctx.createRadialGradient(x - R * 0.3, y - R * 0.3, R * 0.08, x, y, R);
            g.addColorStop(0, '#ffffff');
            g.addColorStop(0.35, color);
            g.addColorStop(1, 'rgba(0,0,0,0.28)');
            ctx.beginPath();
            ctx.arc(x, y, R, 0, Math.PI * 2);
            ctx.fillStyle = g;
            ctx.fill();
            ctx.font = `bold ${Math.max(12, R * 0.65)}px ${CF.mono}`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#fff';
            ctx.fillText(sym, x, y);
            ctx.textBaseline = 'alphabetic';
            ctx.font = `${fs}px ${CF.sans}`;
            ctx.fillStyle = labelCol;
            ctx.fillText(label, x, y + R + 20);
        };

        const pulse = allDone ? this.completionPulse : 0;
        drawAtom(redX, cy,
            allDone ? rxn.reducer.afterColor : rxn.reducer.color,
            allDone ? rxn.reducer.afterSym : rxn.reducer.sym,
            '\u8fd8\u539f\u5242', 'rgba(255,120,80,0.7)', pulse);
        drawAtom(oxX, cy,
            allDone ? rxn.oxidizer.afterColor : rxn.oxidizer.color,
            allDone ? rxn.oxidizer.afterSym : rxn.oxidizer.sym,
            '\u6c27\u5316\u5242', 'rgba(80,140,255,0.7)', pulse);

        // ── electrons ──
        const cpY = cy - R - arcH;
        this.electrons.forEach(e => {
            if (e.progress <= 0) return;
            const p = this._ease(Math.min(1, Math.max(0, e.progress)));
            const sx = redX, sy = cy - R;
            const ex = oxX, ey = cy - R;
            const bx = (1 - p) * (1 - p) * sx + 2 * (1 - p) * p * (W / 2) + p * p * ex;
            const by = (1 - p) * (1 - p) * sy + 2 * (1 - p) * p * cpY + p * p * ey;

            e.trail.push({ x: bx, y: by });
            if (e.trail.length > 20) e.trail.shift();
            for (let i = 0; i < e.trail.length - 1; i++) {
                const a = (i / e.trail.length) * 0.35;
                const r = 1.5 + (i / e.trail.length) * 2;
                ctx.beginPath();
                ctx.arc(e.trail[i].x, e.trail[i].y, r, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(100,200,255,${a.toFixed(2)})`;
                ctx.fill();
            }

            ctx.beginPath();
            ctx.arc(bx, by, 10, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(100,200,255,0.1)';
            ctx.fill();

            const eg = ctx.createRadialGradient(bx - 1, by - 1, 0, bx, by, 6);
            eg.addColorStop(0, 'rgba(200,235,255,0.95)');
            eg.addColorStop(1, 'rgba(60,160,255,0.8)');
            ctx.beginPath();
            ctx.arc(bx, by, 6, 0, Math.PI * 2);
            ctx.fillStyle = eg;
            ctx.fill();

            ctx.font = 'bold 8px ' + CF.mono;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillStyle = '#fff';
            ctx.fillText('e\u207b', bx, by);
            ctx.textBaseline = 'alphabetic';
        });

        // ── status ──
        ctx.font = `bold ${Math.max(11, W * 0.02)}px ${CF.mono}`;
        ctx.textAlign = 'center';
        if (!allDone) {
            ctx.fillStyle = 'rgba(255,200,50,0.75)';
            ctx.fillText('\u2193 \u7535\u5b50\u8f6c\u79fb\u4e2d\u2026', W / 2, cy - R * 1.4);
        } else {
            ctx.fillStyle = 'rgba(100,255,180,0.8)';
            ctx.fillText('\u2713 \u7535\u5b50\u8f6c\u79fb\u5b8c\u6210', W / 2, cy - R * 1.4);
        }

        // ── bottom: oxidation state summary ──
        ctx.font = `${fs}px ${CF.sans}`;
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(255,180,100,0.8)';
        ctx.fillText(rxn.oxLine, W / 2, H * 0.79);
        ctx.fillStyle = 'rgba(100,180,255,0.8)';
        ctx.fillText(rxn.redLine, W / 2, H * 0.86);

        if (H > 280) {
            ctx.font = `${Math.max(9, fs - 1)}px ${CF.mono}`;
            ctx.fillStyle = 'rgba(200,200,200,0.45)';
            ctx.fillText(rxn.halfOx + '  |  ' + rxn.halfRed, W / 2, H * 0.94);
        }
    }
};

function initRedox() { Redox.init(); }
window.Redox = Redox;

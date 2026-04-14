// ===== String Matching Visualization =====
// KMP algorithm step-by-step animation

const StringMatch = {
    canvas: null, ctx: null, W: 0, H: 0,
    _listeners: [],
    _resizeObs: null,
    _raf: null,
    running: true,

    text: 'ABABDABACDABABCABAB',
    pattern: 'ABABCABAB',
    algo: 'kmp', // 'brute' or 'kmp'
    steps: [],
    currentStep: 0,
    playing: false,
    speed: 1,
    lps: [], // KMP failure function

    _on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts);
        this._listeners.push({ el, evt, fn, opts });
    },

    init() {
        this.canvas = document.getElementById('strmatch-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.running = true;
        this.resize();
        this.computeSteps();
        this.bindEvents();
        this.draw();
    },

    destroy() {
        this.running = false;
        this.playing = false;
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
        const h = Math.min(w * 0.55, 380);
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w;
        this.H = h;
    },

    computeLPS() {
        const p = this.pattern;
        const lps = new Array(p.length).fill(0);
        let len = 0, i = 1;
        while (i < p.length) {
            if (p[i] === p[len]) {
                len++;
                lps[i] = len;
                i++;
            } else {
                if (len !== 0) len = lps[len - 1];
                else { lps[i] = 0; i++; }
            }
        }
        this.lps = lps;
        return lps;
    },

    computeSteps() {
        this.steps = [];
        this.currentStep = 0;
        const t = this.text, p = this.pattern;

        if (this.algo === 'kmp') {
            const lps = this.computeLPS();
            let i = 0, j = 0;
            while (i < t.length) {
                this.steps.push({
                    ti: i, pj: j, pOffset: i - j,
                    match: t[i] === p[j],
                    found: false,
                    comparing: true
                });
                if (t[i] === p[j]) {
                    i++; j++;
                    if (j === p.length) {
                        this.steps.push({
                            ti: i - 1, pj: j - 1, pOffset: i - j,
                            match: true, found: true, comparing: false
                        });
                        j = lps[j - 1];
                    }
                } else {
                    if (j !== 0) {
                        j = lps[j - 1];
                    } else {
                        i++;
                    }
                }
            }
        } else {
            // Brute force
            for (let i = 0; i <= t.length - p.length; i++) {
                let found = true;
                for (let j = 0; j < p.length; j++) {
                    this.steps.push({
                        ti: i + j, pj: j, pOffset: i,
                        match: t[i + j] === p[j],
                        found: false,
                        comparing: true
                    });
                    if (t[i + j] !== p[j]) {
                        found = false;
                        break;
                    }
                }
                if (found) {
                    this.steps.push({
                        ti: i + p.length - 1, pj: p.length - 1, pOffset: i,
                        match: true, found: true, comparing: false
                    });
                }
            }
        }
        if (this.steps.length === 0) {
            this.steps.push({ ti: 0, pj: 0, pOffset: 0, match: false, found: false, comparing: false });
        }
    },

    bindEvents() {
        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => this.resize());
            this._resizeObs.observe(this.canvas.parentElement);
        }
        document.querySelectorAll('.strmatch-algo-btn').forEach(btn => {
            this._on(btn, 'click', () => {
                document.querySelectorAll('.strmatch-algo-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.algo = btn.dataset.algo;
                this.playing = false;
                this.computeSteps();
                this.draw();
            });
        });
        const playBtn = document.getElementById('strmatch-play');
        if (playBtn) {
            this._on(playBtn, 'click', () => {
                if (this.currentStep >= this.steps.length - 1) {
                    this.currentStep = 0;
                }
                this.playing = !this.playing;
                if (this.playing) this.autoPlay();
            });
        }
        const stepBtn = document.getElementById('strmatch-step');
        if (stepBtn) {
            this._on(stepBtn, 'click', () => {
                this.playing = false;
                if (this.currentStep < this.steps.length - 1) {
                    this.currentStep++;
                    this.draw();
                }
            });
        }
        const resetBtn = document.getElementById('strmatch-reset');
        if (resetBtn) {
            this._on(resetBtn, 'click', () => {
                this.playing = false;
                this.currentStep = 0;
                this.draw();
            });
        }
        const speedS = document.getElementById('strmatch-speed');
        if (speedS) {
            this._on(speedS, 'input', () => { this.speed = parseFloat(speedS.value); });
        }
    },

    autoPlay() {
        if (!this.playing || !this.running) return;
        if (this.currentStep < this.steps.length - 1) {
            this.currentStep++;
            this.draw();
            setTimeout(() => this.autoPlay(), 400 / this.speed);
        } else {
            this.playing = false;
        }
    },

    draw() {
        const { ctx, W, H, text, pattern, steps, currentStep } = this;
        if (!ctx || W === 0) return;
        ctx.clearRect(0, 0, W, H);

        const step = steps[currentStep] || steps[0];
        const cellW = Math.min(28, (W - 40) / Math.max(text.length, 10));
        const cellH = 30;
        const startX = 20;

        // Title
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '10px var(--font-sans)';
        ctx.textAlign = 'left';
        ctx.fillText(this.algo === 'kmp' ? 'KMP \u7b97\u6cd5' : '\u66b4\u529b\u5339\u914d', 10, 18);
        ctx.fillStyle = 'rgba(255,255,255,0.2)';
        ctx.font = '9px var(--font-mono)';
        ctx.fillText('\u6b65\u9aa4 ' + (currentStep + 1) + '/' + steps.length, 10, 32);

        // Text row
        const textY = 60;
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.font = '9px var(--font-mono)';
        ctx.textAlign = 'left';
        ctx.fillText('\u6587\u672c:', startX, textY - 8);

        for (let i = 0; i < text.length; i++) {
            const x = startX + i * cellW;
            // Highlight matched positions from found steps
            let bg = 'rgba(255,255,255,0.03)';
            if (step.found && i >= step.pOffset && i < step.pOffset + pattern.length) {
                bg = 'rgba(77,158,126,0.2)';
            } else if (i === step.ti && step.comparing) {
                bg = step.match ? 'rgba(77,158,126,0.15)' : 'rgba(224,108,117,0.15)';
            }
            ctx.fillStyle = bg;
            ctx.fillRect(x, textY, cellW - 1, cellH);

            ctx.fillStyle = 'rgba(255,255,255,0.5)';
            ctx.font = '12px var(--font-mono)';
            ctx.textAlign = 'center';
            ctx.fillText(text[i], x + cellW / 2, textY + cellH / 2 + 4);

            // Index
            ctx.fillStyle = 'rgba(255,255,255,0.15)';
            ctx.font = '7px var(--font-mono)';
            ctx.fillText(i, x + cellW / 2, textY + cellH + 10);
        }

        // Pattern row (shifted by pOffset)
        const patY = textY + cellH + 22;
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.font = '9px var(--font-mono)';
        ctx.textAlign = 'left';
        ctx.fillText('\u6a21\u5f0f:', startX, patY - 8);

        for (let j = 0; j < pattern.length; j++) {
            const x = startX + (step.pOffset + j) * cellW;
            let bg = 'rgba(196,121,58,0.05)';
            if (step.found) {
                bg = 'rgba(77,158,126,0.2)';
            } else if (j === step.pj && step.comparing) {
                bg = step.match ? 'rgba(77,158,126,0.15)' : 'rgba(224,108,117,0.15)';
            } else if (j < step.pj) {
                bg = 'rgba(77,158,126,0.08)';
            }
            ctx.fillStyle = bg;
            ctx.fillRect(x, patY, cellW - 1, cellH);

            ctx.fillStyle = 'rgba(196,121,58,0.6)';
            ctx.font = '12px var(--font-mono)';
            ctx.textAlign = 'center';
            ctx.fillText(pattern[j], x + cellW / 2, patY + cellH / 2 + 4);
        }

        // Comparison arrow
        if (step.comparing) {
            const arrowX = startX + step.ti * cellW + cellW / 2;
            ctx.strokeStyle = step.match ? 'rgba(77,158,126,0.4)' : 'rgba(224,108,117,0.4)';
            ctx.lineWidth = 1.5;
            ctx.beginPath();
            ctx.moveTo(arrowX, textY + cellH + 2);
            ctx.lineTo(arrowX, patY - 2);
            ctx.stroke();
            // Arrow head
            ctx.fillStyle = ctx.strokeStyle;
            ctx.beginPath();
            ctx.moveTo(arrowX - 3, patY - 5);
            ctx.lineTo(arrowX + 3, patY - 5);
            ctx.lineTo(arrowX, patY - 1);
            ctx.fill();
        }

        // Status message
        const statusY = patY + cellH + 30;
        ctx.font = '10px var(--font-sans)';
        ctx.textAlign = 'left';
        if (step.found) {
            ctx.fillStyle = 'rgba(77,158,126,0.5)';
            ctx.fillText('\u2705 \u5339\u914d\u6210\u529f! \u4f4d\u7f6e: ' + step.pOffset, startX, statusY);
        } else if (step.comparing) {
            ctx.fillStyle = step.match ? 'rgba(77,158,126,0.4)' : 'rgba(224,108,117,0.4)';
            ctx.fillText(step.match ? '\u2714 \u5b57\u7b26\u5339\u914d' : '\u2718 \u5b57\u7b26\u4e0d\u5339\u914d, ' + (this.algo === 'kmp' ? '\u67e5\u627e LPS \u8df3\u8f6c' : '\u6a21\u5f0f\u53f3\u79fb'), startX, statusY);
        }

        // KMP LPS table
        if (this.algo === 'kmp') {
            this.drawLPSTable(statusY + 25);
        }
    },

    drawLPSTable(y) {
        const { ctx, W, pattern, lps } = this;
        const cellW = Math.min(22, (W - 80) / pattern.length);
        const startX = 20;

        ctx.fillStyle = 'rgba(196,121,58,0.3)';
        ctx.font = '10px var(--font-sans)';
        ctx.textAlign = 'left';
        ctx.fillText('LPS \u8868 (\u524d\u7f00\u51fd\u6570):', startX, y);

        // Pattern chars
        for (let i = 0; i < pattern.length; i++) {
            const x = startX + i * cellW;
            ctx.fillStyle = 'rgba(196,121,58,0.08)';
            ctx.fillRect(x, y + 5, cellW - 1, 18);
            ctx.fillStyle = 'rgba(196,121,58,0.5)';
            ctx.font = '10px var(--font-mono)';
            ctx.textAlign = 'center';
            ctx.fillText(pattern[i], x + cellW / 2, y + 18);
        }
        // LPS values
        for (let i = 0; i < lps.length; i++) {
            const x = startX + i * cellW;
            ctx.fillStyle = 'rgba(255,255,255,0.05)';
            ctx.fillRect(x, y + 24, cellW - 1, 18);
            ctx.fillStyle = 'rgba(229,192,123,0.5)';
            ctx.font = '10px var(--font-mono)';
            ctx.textAlign = 'center';
            ctx.fillText(lps[i], x + cellW / 2, y + 37);
        }
    }
};

function initStringMatch() {
    StringMatch.init();
}

window.StringMatch = StringMatch;
window.initStringMatch = initStringMatch;
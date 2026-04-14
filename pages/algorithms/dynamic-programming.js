// ===== Dynamic Programming Visualization =====
// 0/1 Knapsack problem: DP table filling animation

const DPVis = {
    canvas: null, ctx: null, W: 0, H: 0,
    _listeners: [],
    _resizeObs: null,
    _raf: null,
    time: 0,
    running: true,

    // Knapsack problem
    items: [
        { w: 2, v: 3, name: 'A' },
        { w: 3, v: 4, name: 'B' },
        { w: 4, v: 5, name: 'C' },
        { w: 5, v: 7, name: 'D' }
    ],
    capacity: 8,
    dp: [],
    step: 0,
    maxStep: 0,
    playing: false,
    speed: 1,
    activeCell: null,
    selectedItems: [],

    _on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts);
        this._listeners.push({ el, evt, fn, opts });
    },

    init() {
        this.canvas = document.getElementById('dp-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.running = true;
        this.resize();
        this.buildDP();
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
        const h = Math.min(w * 0.6, 400);
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w;
        this.H = h;
    },

    buildDP() {
        const n = this.items.length;
        const W = this.capacity;
        this.dp = [];
        this.step = 0;
        this.activeCell = null;
        this.selectedItems = [];

        // Initialize DP table with steps
        const table = Array.from({ length: n + 1 }, () => new Array(W + 1).fill(0));
        const steps = [];

        for (let i = 1; i <= n; i++) {
            for (let j = 0; j <= W; j++) {
                if (this.items[i - 1].w <= j) {
                    const take = table[i - 1][j - this.items[i - 1].w] + this.items[i - 1].v;
                    const skip = table[i - 1][j];
                    table[i][j] = Math.max(take, skip);
                    steps.push({
                        i, j,
                        val: table[i][j],
                        took: take > skip,
                        from: take > skip ? [i - 1, j - this.items[i - 1].w] : [i - 1, j]
                    });
                } else {
                    table[i][j] = table[i - 1][j];
                    steps.push({ i, j, val: table[i][j], took: false, from: [i - 1, j] });
                }
            }
        }

        this.dp = table;
        this.steps = steps;
        this.maxStep = steps.length;
        this.visibleTable = Array.from({ length: n + 1 }, () => new Array(W + 1).fill(null));
        // Row 0 is all 0
        for (let j = 0; j <= W; j++) this.visibleTable[0][j] = 0;

        // Traceback for optimal solution
        this.selectedItems = [];
        let rem = W;
        for (let i = n; i > 0; i--) {
            if (table[i][rem] !== table[i - 1][rem]) {
                this.selectedItems.push(i - 1);
                rem -= this.items[i - 1].w;
            }
        }
    },

    bindEvents() {
        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => this.resize());
            this._resizeObs.observe(this.canvas.parentElement);
        }

        const playBtn = document.getElementById('dp-play');
        if (playBtn) {
            this._on(playBtn, 'click', () => {
                this.playing = !this.playing;
                playBtn.textContent = this.playing ? '\u23f8 \u6682\u505c' : '\u25b6 \u64ad\u653e';
                if (this.playing) this.animate();
            });
        }

        const stepBtn = document.getElementById('dp-step');
        if (stepBtn) {
            this._on(stepBtn, 'click', () => {
                this.playing = false;
                if (playBtn) playBtn.textContent = '\u25b6 \u64ad\u653e';
                this.advanceStep();
                this.draw();
            });
        }

        const resetBtn = document.getElementById('dp-reset');
        if (resetBtn) {
            this._on(resetBtn, 'click', () => {
                this.playing = false;
                if (playBtn) playBtn.textContent = '\u25b6 \u64ad\u653e';
                this.buildDP();
                this.draw();
            });
        }

        const speedEl = document.getElementById('dp-speed');
        if (speedEl) {
            this._on(speedEl, 'input', () => {
                this.speed = parseFloat(speedEl.value);
            });
        }
    },

    advanceStep() {
        if (this.step >= this.maxStep) return;
        const s = this.steps[this.step];
        this.visibleTable[s.i][s.j] = s.val;
        this.activeCell = { i: s.i, j: s.j, from: s.from, took: s.took };
        this.step++;
    },

    animate() {
        if (!this.playing || !this.running) return;
        this.time += 0.016;

        if (this.time > 0.3 / this.speed) {
            this.time = 0;
            this.advanceStep();
            if (this.step >= this.maxStep) {
                this.playing = false;
                const playBtn = document.getElementById('dp-play');
                if (playBtn) playBtn.textContent = '\u25b6 \u64ad\u653e';
            }
        }

        this.draw();
        this._raf = requestAnimationFrame(() => this.animate());
    },

    draw() {
        const { ctx, W, H } = this;
        if (!ctx || W === 0) return;
        ctx.clearRect(0, 0, W, H);

        this.drawTable();
        this.drawItems();
    },

    drawTable() {
        const { ctx, W, H, items, capacity, visibleTable, activeCell, step, maxStep } = this;
        const n = items.length;
        const cols = capacity + 1;
        const rows = n + 1;

        const tableX = 80;
        const tableY = 10;
        const cellW = Math.min((W - tableX - 20) / cols, 36);
        const cellH = Math.min((H - tableY - 60) / rows, 32);

        // Header row (capacity)
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '10px var(--font-mono)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        for (let j = 0; j < cols; j++) {
            ctx.fillText(j.toString(), tableX + j * cellW + cellW / 2, tableY + cellH / 2);
        }

        // Header col (items)
        ctx.fillText('\u5bb9\u91cf\u2192', tableX - 30, tableY + cellH / 2);
        ctx.fillText('0', tableX - 15, tableY + cellH + cellH / 2);
        for (let i = 0; i < n; i++) {
            ctx.fillText(items[i].name, tableX - 15, tableY + (i + 2) * cellH + cellH / 2);
        }

        // Cells
        for (let i = 0; i <= n; i++) {
            for (let j = 0; j < cols; j++) {
                const x = tableX + j * cellW;
                const y = tableY + (i + 1) * cellH;

                // Cell background
                let bg = 'rgba(255,255,255,0.03)';
                if (activeCell && activeCell.i === i && activeCell.j === j) {
                    bg = 'rgba(229,192,123,0.25)';
                } else if (activeCell && activeCell.from && activeCell.from[0] === i && activeCell.from[1] === j) {
                    bg = 'rgba(139,111,192,0.15)';
                } else if (step >= maxStep && this.selectedItems.includes(i - 1) && j === capacity) {
                    bg = 'rgba(77,158,126,0.15)';
                }

                ctx.fillStyle = bg;
                ctx.fillRect(x, y, cellW, cellH);
                ctx.strokeStyle = 'rgba(255,255,255,0.06)';
                ctx.lineWidth = 0.5;
                ctx.strokeRect(x, y, cellW, cellH);

                // Value
                if (visibleTable[i][j] !== null) {
                    ctx.fillStyle = activeCell && activeCell.i === i && activeCell.j === j
                        ? '#e5c07b'
                        : 'rgba(255,255,255,0.5)';
                    ctx.font = '11px var(--font-mono)';
                    ctx.textAlign = 'center';
                    ctx.textBaseline = 'middle';
                    ctx.fillText(visibleTable[i][j].toString(), x + cellW / 2, y + cellH / 2);
                }
            }
        }

        // Progress label
        ctx.fillStyle = 'rgba(255,255,255,0.2)';
        ctx.font = '10px var(--font-sans)';
        ctx.textAlign = 'left';
        ctx.fillText('\u6b65\u9aa4: ' + step + '/' + maxStep, tableX, tableY + (n + 2) * cellH + 14);

        if (step >= maxStep) {
            const optVal = this.dp[n][capacity];
            ctx.fillStyle = 'rgba(77,158,126,0.6)';
            ctx.fillText('\u6700\u4f18\u89e3: ' + optVal + ' (\u9009\u53d6: ' + this.selectedItems.map(i => items[i].name).join(',') + ')', tableX + 100, tableY + (n + 2) * cellH + 14);
        }
    },

    drawItems() {
        const { ctx, W, H, items, step, maxStep } = this;
        const x = W - 100;
        const y = 20;

        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = 'bold 10px var(--font-sans)';
        ctx.textAlign = 'left';
        ctx.fillText('\u7269\u54c1\u5217\u8868', x, y);

        items.forEach((item, i) => {
            const iy = y + 18 + i * 22;
            const selected = step >= maxStep && this.selectedItems.includes(i);
            ctx.fillStyle = selected ? 'rgba(77,158,126,0.6)' : 'rgba(255,255,255,0.2)';
            ctx.font = '10px var(--font-mono)';
            ctx.fillText(item.name + ': w=' + item.w + ' v=' + item.v, x, iy);
            if (selected) {
                ctx.fillStyle = 'rgba(77,158,126,0.3)';
                ctx.fillText('\u2713', x - 12, iy);
            }
        });

        ctx.fillStyle = 'rgba(255,255,255,0.2)';
        ctx.font = '10px var(--font-mono)';
        ctx.fillText('\u5bb9\u91cf W=' + this.capacity, x, y + 18 + items.length * 22 + 10);
    }
};

function initDPVis() {
    DPVis.init();
}

window.DPVis = DPVis;
window.initDPVis = initDPVis;
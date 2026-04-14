// ===== Chemical Bond Visualization =====
// Ionic, Covalent, Metallic bonds

const ChemBond = {
    canvas: null, ctx: null, W: 0, H: 0,
    _listeners: [],
    _resizeObs: null,
    _raf: null,

    mode: 'ionic', // 'ionic', 'covalent', 'metallic'
    time: 0,
    running: true,

    bondInfo: {
        ionic: {
            name: '\u79bb\u5b50\u952e',
            desc: '\u7531\u9634\u9633\u79bb\u5b50\u4e4b\u95f4\u7684\u9759\u7535\u5f15\u529b\u5f62\u6210\uff0c\u5982 NaCl',
            example: 'Na\u207a + Cl\u207b \u2192 NaCl'
        },
        covalent: {
            name: '\u5171\u4ef7\u952e',
            desc: '\u539f\u5b50\u95f4\u901a\u8fc7\u5171\u7528\u7535\u5b50\u5bf9\u5f62\u6210\uff0c\u5982 H\u2082O',
            example: 'H\u2012O\u2012H (\u5171\u7528\u7535\u5b50\u5bf9)'
        },
        metallic: {
            name: '\u91d1\u5c5e\u952e',
            desc: '\u81ea\u7531\u7535\u5b50\u6d77\u4e0e\u91d1\u5c5e\u9633\u79bb\u5b50\u4e4b\u95f4\u7684\u4f5c\u7528\u529b',
            example: '\u91d1\u5c5e\u9633\u79bb\u5b50 + \u81ea\u7531\u7535\u5b50\u6d77'
        }
    },

    _on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts);
        this._listeners.push({ el, evt, fn, opts });
    },

    init() {
        this.canvas = document.getElementById('chembond-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.time = 0;
        this.running = true;
        this.resize();
        this.bindEvents();
        this.loop();
        this.updateInfo();
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
        const h = Math.min(w * 0.55, 360);
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
            this._resizeObs = new ResizeObserver(() => { this.resize(); });
            this._resizeObs.observe(this.canvas.parentElement);
        }

        document.querySelectorAll('.chembond-mode-btn').forEach(btn => {
            this._on(btn, 'click', () => {
                document.querySelectorAll('.chembond-mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.mode = btn.dataset.mode;
                this.time = 0;
                this.updateInfo();
            });
        });
    },

    updateInfo() {
        const info = this.bondInfo[this.mode];
        const el = document.getElementById('chembond-info');
        if (el) el.innerHTML = '<strong>' + info.name + '</strong> \u2014 ' + info.desc + '<br><code>' + info.example + '</code>';
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

        if (mode === 'ionic') this.drawIonic();
        else if (mode === 'covalent') this.drawCovalent();
        else this.drawMetallic();
    },

    drawIonic() {
        const { ctx, W, H, time } = this;
        const cx = W / 2, cy = H / 2;

        // Na+ and Cl- attracting
        const sep = 50 + 30 * Math.cos(time * 1.5); // breathing

        // Na+
        const naX = cx - sep;
        ctx.fillStyle = '#7a8fc2';
        ctx.beginPath();
        ctx.arc(naX, cy, 22, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 13px var(--font-sans)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('Na\u207a', naX, cy);

        // Cl-
        const clX = cx + sep;
        ctx.fillStyle = '#4d9e7e';
        ctx.beginPath();
        ctx.arc(clX, cy, 28, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.fillText('Cl\u207b', clX, cy);

        // Electrostatic force arrows
        const arrowColor = 'rgba(229,192,123,0.5)';
        ctx.strokeStyle = arrowColor;
        ctx.lineWidth = 1.5;
        ctx.setLineDash([3, 3]);
        ctx.beginPath();
        ctx.moveTo(naX + 24, cy);
        ctx.lineTo(clX - 30, cy);
        ctx.stroke();
        ctx.setLineDash([]);

        // Force label
        ctx.fillStyle = 'rgba(229,192,123,0.6)';
        ctx.font = '10px var(--font-mono)';
        ctx.fillText('\u9759\u7535\u5f15\u529b', cx, cy - 20);

        // Electron shells hint
        this.drawElectronShell(naX, cy, 30, 2, time, '#7a8fc2');
        this.drawElectronShell(clX, cy, 38, 8, time, '#4d9e7e');

        // Crystal lattice preview (right side)
        const lx = W * 0.8, ly = H * 0.3;
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '10px var(--font-sans)';
        ctx.textAlign = 'center';
        ctx.fillText('\u6676\u4f53\u7ed3\u6784', lx, ly - 20);

        const gridSize = 22;
        for (let r = 0; r < 3; r++) {
            for (let c = 0; c < 3; c++) {
                const gx = lx - gridSize + c * gridSize;
                const gy = ly + r * gridSize;
                const isNa = (r + c) % 2 === 0;
                ctx.fillStyle = isNa ? '#7a8fc2' : '#4d9e7e';
                ctx.globalAlpha = 0.5;
                ctx.beginPath();
                ctx.arc(gx, gy, isNa ? 6 : 8, 0, Math.PI * 2);
                ctx.fill();
                ctx.globalAlpha = 1;
            }
        }
    },

    drawElectronShell(cx, cy, r, nElectrons, time, color) {
        const ctx = this.ctx;
        ctx.strokeStyle = color;
        ctx.globalAlpha = 0.15;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.stroke();
        ctx.globalAlpha = 1;

        for (let i = 0; i < nElectrons; i++) {
            const angle = (i / nElectrons) * Math.PI * 2 + time * 0.8;
            const ex = cx + r * Math.cos(angle);
            const ey = cy + r * Math.sin(angle);
            ctx.fillStyle = '#e5c07b';
            ctx.beginPath();
            ctx.arc(ex, ey, 2.5, 0, Math.PI * 2);
            ctx.fill();
        }
    },

    drawCovalent() {
        const { ctx, W, H, time } = this;
        const cx = W / 2, cy = H / 2;

        // Water molecule H-O-H
        const angle = 52.25 * Math.PI / 180; // half of 104.5 degree
        const bondLen = 55;
        const oX = cx, oY = cy;
        const h1X = cx - bondLen * Math.sin(angle);
        const h1Y = cy - bondLen * Math.cos(angle);
        const h2X = cx + bondLen * Math.sin(angle);
        const h2Y = cy - bondLen * Math.cos(angle);

        // Bonds
        ctx.strokeStyle = 'rgba(255,255,255,0.2)';
        ctx.lineWidth = 3;
        ctx.beginPath();
        ctx.moveTo(h1X, h1Y);
        ctx.lineTo(oX, oY);
        ctx.lineTo(h2X, h2Y);
        ctx.stroke();

        // Oxygen
        ctx.fillStyle = '#e06c75';
        ctx.beginPath();
        ctx.arc(oX, oY, 25, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 14px var(--font-sans)';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('O', oX, oY);

        // Hydrogens
        [{ x: h1X, y: h1Y }, { x: h2X, y: h2Y }].forEach(h => {
            ctx.fillStyle = '#5b8dce';
            ctx.beginPath();
            ctx.arc(h.x, h.y, 16, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 12px var(--font-sans)';
            ctx.fillText('H', h.x, h.y);
        });

        // Shared electron pairs (animated orbit)
        [{ x: h1X, y: h1Y }, { x: h2X, y: h2Y }].forEach((h, idx) => {
            const midX = (h.x + oX) / 2;
            const midY = (h.y + oY) / 2;
            for (let e = 0; e < 2; e++) {
                const phase = time * 1.2 + idx * Math.PI + e * Math.PI;
                const perpX = -(h.y - oY);
                const perpY = h.x - oX;
                const len = Math.hypot(perpX, perpY);
                const offX = perpX / len * 6 * Math.sin(phase);
                const offY = perpY / len * 6 * Math.sin(phase);
                const along = Math.cos(phase) * 15;
                const dx = (h.x - oX) / Math.hypot(h.x - oX, h.y - oY);
                const dy = (h.y - oY) / Math.hypot(h.x - oX, h.y - oY);
                const ex = midX + dx * along + offX;
                const ey = midY + dy * along + offY;
                ctx.fillStyle = '#e5c07b';
                ctx.beginPath();
                ctx.arc(ex, ey, 3, 0, Math.PI * 2);
                ctx.fill();
            }
        });

        // Angle label
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 1;
        const arcR = 25;
        ctx.beginPath();
        const aStart = -Math.PI / 2 - angle;
        const aEnd = -Math.PI / 2 + angle;
        ctx.arc(oX, oY, arcR, aStart, aEnd);
        ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.font = '10px var(--font-mono)';
        ctx.fillText('104.5\u00b0', oX, oY + 35);

        // Electronegativity hint
        ctx.fillStyle = 'rgba(255,255,255,0.25)';
        ctx.font = '10px var(--font-sans)';
        ctx.fillText('\u03b4\u207b', oX, oY - 30);
        ctx.fillText('\u03b4\u207a', h1X, h1Y - 20);
        ctx.fillText('\u03b4\u207a', h2X, h2Y - 20);
    },

    drawMetallic() {
        const { ctx, W, H, time } = this;

        // Grid of cations + free electron sea
        const cols = Math.floor(W / 45);
        const rows = Math.floor(H / 45);
        const gapX = W / (cols + 1);
        const gapY = H / (rows + 1);

        // Metal cations (fixed grid)
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const x = gapX * (c + 1);
                const y = gapY * (r + 1);
                ctx.fillStyle = 'rgba(196,149,102,0.5)';
                ctx.beginPath();
                ctx.arc(x, y, 12, 0, Math.PI * 2);
                ctx.fill();
                ctx.fillStyle = 'rgba(255,255,255,0.4)';
                ctx.font = '9px var(--font-sans)';
                ctx.textAlign = 'center';
                ctx.textBaseline = 'middle';
                ctx.fillText('M\u207a', x, y);
            }
        }

        // Free electrons (random-ish movement)
        const nElectrons = cols * rows * 2;
        for (let i = 0; i < nElectrons; i++) {
            const seed = i * 137.508;
            const x = ((seed * 0.618 + time * 25 * (0.3 + (i % 5) * 0.15)) % W + W) % W;
            const y = ((seed * 0.414 + time * 18 * (0.2 + (i % 7) * 0.1)) % H + H) % H;
            ctx.fillStyle = 'rgba(91,141,206,0.5)';
            ctx.beginPath();
            ctx.arc(x, y, 2, 0, Math.PI * 2);
            ctx.fill();
        }

        // Label
        ctx.fillStyle = 'rgba(91,141,206,0.4)';
        ctx.font = '10px var(--font-sans)';
        ctx.textAlign = 'center';
        ctx.fillText('\u81ea\u7531\u7535\u5b50\u6d77 (e\u207b)', W / 2, H - 10);
    }
};

function initChemBond() {
    ChemBond.init();
}

window.ChemBond = ChemBond;
window.initChemBond = initChemBond;
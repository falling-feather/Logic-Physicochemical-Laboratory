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
        if (!el) return;
        let h = '';
        if (this.mode === 'ionic') {
            h = `<div class="chem-hd"><span class="chem-tag">离子键</span>化学键知识点</div>
<div class="chem-row"><span class="chem-key">定义</span>${info.desc}，本质是阴阳离子间的静电引力</div>
<div class="chem-row"><span class="chem-key chem-key--purple">形成条件</span>活泼金属 + 活泼非金属（电负性差 > 1.7），如 ${info.example}</div>
<div class="chem-row"><span class="chem-key chem-key--amber">特征</span>无方向性、无饱和性 — 离子晶体中每个离子周围吸引尽可能多的异号离子</div>
<div class="chem-row"><span class="chem-key">性质影响</span>离子键强 → 熔沸点高、硬度大；熔融/溶于水可导电（自由移动离子）</div>
<div class="chem-note">💡 人教版必修2：判断离子键——看是否由阴阳离子构成。NH₄Cl 虽无金属但含 NH₄⁺ 与 Cl⁻ 的离子键</div>`;
        } else if (this.mode === 'covalent') {
            h = `<div class="chem-hd"><span class="chem-tag">共价键</span>化学键知识点</div>
<div class="chem-row"><span class="chem-key">定义</span>${info.desc}，本质是共用电子对的静电作用</div>
<div class="chem-row"><span class="chem-key chem-key--purple">分类</span>极性共价键（共用电子对偏移，如 H-Cl）vs 非极性共价键（电子对不偏移，如 H-H）</div>
<div class="chem-row"><span class="chem-key chem-key--amber">特征</span>有方向性（最大重叠原理）、有饱和性（成键电子数有限）</div>
<div class="chem-row"><span class="chem-key">键参数</span>键能↑ → 稳定性↑；键长↓ → 键越强；键角决定分子空间构型</div>
<div class="chem-note">💡 人教版必修2：σ 键（头碰头重叠）可绕轴旋转，π 键（肩并肩重叠）不可旋转。双键 = 1σ + 1π</div>`;
        } else {
            h = `<div class="chem-hd"><span class="chem-tag">金属键</span>化学键知识点</div>
<div class="chem-row"><span class="chem-key">定义</span>${info.desc}</div>
<div class="chem-row"><span class="chem-key chem-key--purple">自由电子模型</span>金属阳离子规则排列，自由电子在整个晶体中运动（"电子海洋"）</div>
<div class="chem-row"><span class="chem-key chem-key--amber">特征</span>无方向性、无饱和性 — 金属晶体中原子倾向密堆积</div>
<div class="chem-row"><span class="chem-key">性质解释</span>导电导热（自由电子）、延展性（离子层滑动后仍被电子海粘合）、金属光泽（电子吸收后再辐射光）</div>
<div class="chem-note">💡 人教版选择性必修2：金属键强度影响熔沸点——原子半径↓、价电子数↑ → 金属键越强 → 熔点越高</div>`;
        }
        el.innerHTML = h;
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
        ctx.font = 'bold 18px ' + CF.sans;
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
        ctx.font = '15px ' + CF.mono;
        ctx.fillText('\u9759\u7535\u5f15\u529b', cx, cy - 20);

        // Electron shells hint
        this.drawElectronShell(naX, cy, 30, 2, time, '#7a8fc2');
        this.drawElectronShell(clX, cy, 38, 8, time, '#4d9e7e');

        // Crystal lattice preview (right side)
        const lx = W * 0.8, ly = H * 0.3;
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '15px ' + CF.sans;
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
        ctx.font = 'bold 19px ' + CF.sans;
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
            ctx.font = 'bold 17px ' + CF.sans;
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
        ctx.font = '15px ' + CF.mono;
        ctx.fillText('104.5\u00b0', oX, oY + 35);

        // Electronegativity hint
        ctx.fillStyle = 'rgba(255,255,255,0.25)';
        ctx.font = '15px ' + CF.sans;
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
                ctx.font = '14px ' + CF.sans;
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
        ctx.font = '15px ' + CF.sans;
        ctx.textAlign = 'center';
        ctx.fillText('\u81ea\u7531\u7535\u5b50\u6d77 (e\u207b)', W / 2, H - 10);
    }
};

function initChemBond() {
    ChemBond.init();
}

window.ChemBond = ChemBond;
window.initChemBond = initChemBond;
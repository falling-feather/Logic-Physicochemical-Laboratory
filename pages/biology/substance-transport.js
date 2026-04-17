/* ═══════════════════════════════════════════════════
   Substance Transport – Membrane Transport Modes
   ═══════════════════════════════════════════════════ */
const SubstanceTransport = {
    _listeners: [],
    _on(el, evt, fn, opts) { el.addEventListener(evt, fn, opts); this._listeners.push({ el, evt, fn, opts }); },
    canvas: null, ctx: null, animId: null,
    mode: 0, // 0=free diffusion, 1=facilitated, 2=active, 3=endo/exocytosis
    modes: [
        { name: '\u81EA\u7531\u6269\u6563', desc: '\u5C0F\u5206\u5B50/\u975E\u6781\u6027\u5206\u5B50\u987A\u6D53\u5EA6\u68AF\u5EA6\u901A\u8FC7\u78F7\u8102\u53CC\u5206\u5B50\u5C42', color: 'rgba(100,200,150,0.8)', energy: false },
        { name: '\u534F\u52A9\u6269\u6563', desc: '\u9700\u8F7D\u4F53\u86CB\u767D\u534F\u52A9\uFF0C\u987A\u6D53\u5EA6\u68AF\u5EA6\uFF0C\u4E0D\u8017\u80FD', color: 'rgba(100,150,255,0.8)', energy: false },
        { name: '\u4E3B\u52A8\u8F90\u8FD0', desc: '\u9700\u8F7D\u4F53\u86CB\u767D + ATP\uFF0C\u9006\u6D53\u5EA6\u68AF\u5EA6', color: 'rgba(255,150,50,0.8)', energy: true },
        { name: '\u80DE\u541E/\u80DE\u5410', desc: '\u5927\u5206\u5B50\u7269\u8D28\u901A\u8FC7\u56CA\u6CE1\u8FDB\u51FA\u7EC6\u80DE', color: 'rgba(200,100,200,0.8)', energy: true }
    ],
    molecules: [],
    speed: 1,

    init() {
        this.canvas = document.getElementById('substance-transport-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this._resize();
        this._on(window, 'resize', () => this._resize());
        this._buildControls();
        this._injectInfoPanel();
        this._initMolecules();
        this._loop();
    },
    destroy() {
        if (this.animId) { cancelAnimationFrame(this.animId); this.animId = null; }
        this._listeners.forEach(l => l.el.removeEventListener(l.evt, l.fn, l.opts));
        this._listeners.length = 0;
        const c = document.getElementById('substance-transport-controls');
        if (c) c.innerHTML = '';
    },
    _resize() {
        const p = this.canvas.parentElement;
        const dpr = window.devicePixelRatio || 1;
        const w = p.clientWidth;
        const h = p.clientHeight || 420;
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w;
        this.H = h;
        this._initMolecules();
    },
    _buildControls() {
        const ctrl = document.getElementById('substance-transport-controls');
        if (!ctrl) return;
        ctrl.innerHTML = '';
        const wrap = document.createElement('div');
        wrap.className = 'strans-mode-btns';
        this.modes.forEach((m, i) => {
            const b = document.createElement('button');
            b.className = 'strans-btn' + (i === this.mode ? ' active' : '');
            b.textContent = m.name;
            this._on(b, 'click', () => {
                this.mode = i;
                this._initMolecules();
                wrap.querySelectorAll('.strans-btn').forEach(x => x.classList.remove('active'));
                b.classList.add('active');
                this._updateInfo();
            });
            wrap.appendChild(b);
        });
        ctrl.appendChild(wrap);
        const label = document.createElement('label');
        label.className = 'strans-speed';
        label.innerHTML = '<span>\u901F\u5EA6</span>';
        const inp = document.createElement('input');
        inp.type = 'range'; inp.min = 0.3; inp.max = 3; inp.step = 0.1; inp.value = 1;
        this._on(inp, 'input', () => { this.speed = parseFloat(inp.value); });
        label.appendChild(inp);
        ctrl.appendChild(label);
    },
    _initMolecules() {
        this.molecules = [];
        const W = this.W, H = this.H;
        // put molecules on left (high concentration) side
        for (let i = 0; i < 12; i++) {
            this.molecules.push({
                x: Math.random() * W * 0.35 + W * 0.05,
                y: Math.random() * (H - 120) + 60,
                vx: (Math.random() - 0.5) * 0.8,
                vy: (Math.random() - 0.5) * 0.8,
                r: 5 + Math.random() * 3,
                phase: Math.random() * Math.PI * 2,
                crossed: false
            });
        }
    },
    _drawMembrane(t) {
        const ctx = this.ctx, W = this.W, H = this.H;
        const mx = W * 0.5;
        // phospholipid bilayer
        ctx.strokeStyle = 'rgba(200,180,120,0.4)';
        ctx.lineWidth = 20;
        ctx.beginPath();
        ctx.moveTo(mx, 50);
        ctx.lineTo(mx, H - 30);
        ctx.stroke();
        // inner lighter
        ctx.strokeStyle = 'rgba(220,200,140,0.2)';
        ctx.lineWidth = 14;
        ctx.beginPath();
        ctx.moveTo(mx, 50);
        ctx.lineTo(mx, H - 30);
        ctx.stroke();
        // phospholipid heads circles
        for (let y = 55; y < H - 25; y += 15) {
            ctx.beginPath();
            ctx.arc(mx - 10, y + Math.sin(t + y * 0.1) * 1.5, 4, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(200,180,120,0.5)';
            ctx.fill();
            ctx.beginPath();
            ctx.arc(mx + 10, y + Math.sin(t + y * 0.1 + 1) * 1.5, 4, 0, Math.PI * 2);
            ctx.fill();
        }
        // labels
        ctx.font = '15px ' + CF.sans;
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(200,200,200,0.4)';
        ctx.fillText('\u7EC6\u80DE\u5916 (\u9AD8\u6D53\u5EA6)', W * 0.25, 42);
        ctx.fillText('\u7EC6\u80DE\u5185 (\u4F4E\u6D53\u5EA6)', W * 0.75, 42);
    },
    _drawChannel(t) {
        const ctx = this.ctx, W = this.W, H = this.H;
        const mx = W * 0.5;
        // channel protein
        ctx.fillStyle = 'rgba(100,150,255,0.3)';
        ctx.beginPath();
        ctx.moveTo(mx - 15, H * 0.35);
        ctx.lineTo(mx - 8, H * 0.4);
        ctx.lineTo(mx - 8, H * 0.6);
        ctx.lineTo(mx - 15, H * 0.65);
        ctx.closePath();
        ctx.fill();
        ctx.beginPath();
        ctx.moveTo(mx + 15, H * 0.35);
        ctx.lineTo(mx + 8, H * 0.4);
        ctx.lineTo(mx + 8, H * 0.6);
        ctx.lineTo(mx + 15, H * 0.65);
        ctx.closePath();
        ctx.fill();
        ctx.font = '14px ' + CF.sans;
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(100,150,255,0.6)';
        ctx.fillText('\u8F7D\u4F53\u86CB\u767D', mx, H * 0.32);
    },
    _drawATP(t) {
        const ctx = this.ctx, W = this.W, H = this.H;
        const mx = W * 0.5;
        // pump protein (active transport)
        ctx.fillStyle = 'rgba(255,150,50,0.3)';
        ctx.beginPath();
        ctx.ellipse(mx, H * 0.5, 18, 45, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.strokeStyle = 'rgba(255,150,50,0.5)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.font = '14px ' + CF.sans;
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(255,150,50,0.7)';
        ctx.fillText('\u8F7D\u4F53\u86CB\u767D', mx, H * 0.5);
        // ATP icon
        const ap = (t * 0.5) % 1;
        ctx.beginPath();
        ctx.arc(mx + 25, H * 0.5 + 20, 8, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,200,50,' + (0.4 + ap * 0.3) + ')';
        ctx.fill();
        ctx.font = 'bold 14px ' + CF.mono;
        ctx.fillStyle = '#fff';
        ctx.fillText('ATP', mx + 25, H * 0.5 + 22);
        // direction arrow (reversed - low to high)
        ctx.fillStyle = 'rgba(200,200,200,0.3)';
        ctx.fillText('\u2190 \u9006\u6D53\u5EA6\u68AF\u5EA6', mx, H - 15);
    },
    _drawVesicle(t) {
        const ctx = this.ctx, W = this.W, H = this.H;
        const mx = W * 0.5;
        // endocytosis on top
        const ep = ((t * 0.3) % 1);
        const ey = H * 0.35;
        // membrane invagination
        ctx.beginPath();
        ctx.arc(mx, ey, 12 + ep * 8, 0, Math.PI * 2);
        ctx.strokeStyle = 'rgba(200,180,120,0.5)';
        ctx.lineWidth = 2;
        ctx.stroke();
        if (ep > 0.6) {
            ctx.beginPath();
            ctx.arc(mx + 25 * (ep - 0.6) * 2.5, ey, 10, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(200,100,200,0.3)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(200,180,120,0.4)';
            ctx.stroke();
        }
        ctx.font = '14px ' + CF.sans;
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(200,100,200,0.6)';
        ctx.fillText('\u80DE\u541E', mx, ey - 25);
        // exocytosis on bottom
        const ey2 = H * 0.65;
        const ep2 = ((t * 0.3 + 0.5) % 1);
        ctx.beginPath();
        ctx.arc(mx - 25 * ep2, ey2, 10, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(200,100,200,0.3)';
        ctx.fill();
        ctx.strokeStyle = 'rgba(200,180,120,0.4)';
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = 'rgba(200,100,200,0.6)';
        ctx.fillText('\u80DE\u5410', mx, ey2 + 30);
    },
    _draw(t) {
        const ctx = this.ctx, W = this.W, H = this.H;
        ctx.clearRect(0, 0, W, H);
        const m = this.modes[this.mode];
        ctx.font = 'bold 21px ' + CF.sans;
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(58,158,143,0.9)';
        ctx.fillText('\u7269\u8D28\u8F90\u8FD0 - ' + m.name, W / 2, 25);
        ctx.font = '17px ' + CF.sans;
        ctx.fillStyle = 'rgba(200,200,200,0.5)';
        ctx.fillText(m.desc, W / 2, H - 8);

        this._drawMembrane(t);
        if (this.mode === 1 || this.mode === 2) this._drawChannel(t);
        if (this.mode === 2) this._drawATP(t);
        if (this.mode === 3) this._drawVesicle(t);

        // molecules movement
        const mx = W * 0.5;
        const modeData = this.modes[this.mode];
        this.molecules.forEach(mol => {
            mol.phase += 0.02 * this.speed;
            mol.x += mol.vx * this.speed;
            mol.y += mol.vy * this.speed;
            // boundary bounce
            if (mol.x < 10) { mol.x = 10; mol.vx *= -1; }
            if (mol.y < 55) { mol.y = 55; mol.vy *= -1; }
            if (mol.y > H - 35) { mol.y = H - 35; mol.vy *= -1; }
            if (this.mode === 3) {
                if (mol.x > W - 10) { mol.x = W - 10; mol.vx *= -1; }
                return; // vesicle mode: no crossing
            }
            // membrane crossing logic
            if (!mol.crossed) {
                if (this.mode === 0) {
                    // free diffusion: cross anywhere
                    if (mol.x > mx - 5 && mol.x < mx + 5) {
                        if (Math.random() < 0.02 * this.speed) {
                            mol.crossed = true;
                            mol.x = mx + 15;
                        } else { mol.vx *= -1; }
                    }
                } else if (this.mode === 1) {
                    // facilitated: cross only through channel
                    if (mol.x > mx - 10 && mol.y > H * 0.35 && mol.y < H * 0.65) {
                        if (Math.random() < 0.03 * this.speed) {
                            mol.crossed = true;
                            mol.x = mx + 15;
                        }
                    } else if (mol.x > mx - 12) { mol.vx *= -1; }
                } else if (this.mode === 2) {
                    // active: reversed, molecules go high->low but with pump; particles are on LEFT (high) side and need to go RIGHT
                    // Actually active transport goes from low to high, so flip logic: molecules start right and go left
                    if (mol.x > mx - 15 && mol.x < mx + 15 && mol.y > H * 0.35 && mol.y < H * 0.65) {
                        if (Math.random() < 0.02 * this.speed) {
                            mol.crossed = true;
                            mol.x = mx + 20;
                        }
                    } else if (mol.x > mx - 15) { mol.vx *= -1; }
                }
                if (mol.x > W - 10) { mol.x = W - 10; mol.vx *= -1; }
            } else {
                if (mol.x > W - 10) { mol.x = W - 10; mol.vx *= -1; }
                if (mol.x < mx + 12) { mol.x = mx + 12; mol.vx = Math.abs(mol.vx); }
            }
            // draw molecule
            ctx.beginPath();
            ctx.arc(mol.x, mol.y, mol.r, 0, Math.PI * 2);
            ctx.fillStyle = modeData.color;
            ctx.fill();
        });
    },
    _injectInfoPanel() {
        const el = document.getElementById('strans-info');
        if (!el) return;
        el.innerHTML = `
            <div class="strans-info__hd">📘 物质运输知识点</div>
            <div class="strans-info__grid">
                <div class="strans-info__block">
                    <div class="strans-info__sub">当前方式</div>
                    <div id="strans-mode-display" class="strans-info__val">自由扩散</div>
                    <div id="strans-mode-desc" class="strans-info__desc">小分子/非极性分子顺浓度梯度通过磷脂双分子层</div>
                </div>
                <div class="strans-info__block">
                    <div class="strans-info__sub">四种运输方式</div>
                    <div class="strans-info__row"><span class="strans-info__key" style="--c:#64c896">自由扩散</span> 顺浓度，不耗能，不需载体（如O₂、CO₂、H₂O）</div>
                    <div class="strans-info__row"><span class="strans-info__key" style="--c:#6496ff">协助扩散</span> 顺浓度，不耗能，需载体蛋白（如葡萄糖进红细胞）</div>
                    <div class="strans-info__row"><span class="strans-info__key" style="--c:#ff9632">主动运输</span> 逆浓度，耗ATP，需载体蛋白（如Na⁺-K⁺泵）</div>
                    <div class="strans-info__row"><span class="strans-info__key" style="--c:#c864c8">胞吞/胞吐</span> 大分子通过囊泡进出细胞</div>
                </div>
                <div class="strans-info__block">
                    <div class="strans-info__sub">💡 知识要点</div>
                    <div class="strans-info__note">自由扩散和协助扩散统称被动运输（顺浓度梯度）。主动运输消耗细胞代谢产生的ATP，可逆浓度梯度运输。胞吞胞吐需要膜的流动性。</div>
                </div>
            </div>
        `;
    },

    _updateInfo() {
        const m = this.modes[this.mode];
        const nameEl = document.getElementById('strans-mode-display');
        const descEl = document.getElementById('strans-mode-desc');
        if (nameEl) nameEl.textContent = m.name;
        if (descEl) descEl.textContent = m.desc;
    },

    _loop() {
        const t = performance.now() / 1000;
        this._draw(t);
        this.animId = requestAnimationFrame(() => this._loop());
    }
};

function initSubstanceTransport() { SubstanceTransport.init(); }
window.SubstanceTransport = SubstanceTransport;
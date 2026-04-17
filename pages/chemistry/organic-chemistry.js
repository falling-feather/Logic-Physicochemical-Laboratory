// ===== Organic Chemistry Visualization v2 =====
// 3D molecular viewer · drag-rotate · functional-group highlighting · education panel

const OrganicChem = {
    canvas: null, ctx: null, W: 0, H: 0,
    _listeners: [], _resizeObs: null, _raf: null, _lastT: 0,
    molecule: 'methane', time: 0, running: true, paused: false,
    rotX: -0.3, rotY: 0.5, autoRot: true,
    _drag: false, _dx0: 0, _dy0: 0, _rx0: 0, _ry0: 0,
    _mx: -999, _my: -999, _hitIdx: -1,

    /* ── Molecule database (3-D coordinates) ── */
    molecules: {
        methane: {
            name: '甲烷 CH₄', formula: 'CH₄', mw: 16.04, iupac: 'Methane',
            desc: '最简单的烷烃，正四面体构型，键角 109.5°',
            fg: '—（烷烃）', angle: '正四面体 109.5°',
            rxns: ['取代：CH₄ + Cl₂ →(光照) CH₃Cl + HCl', '燃烧：CH₄ + 2O₂ → CO₂ + 2H₂O'],
            atoms: [
                { el: 'C', x: 0, y: 0, z: 0, r: 22, c: '#555' },
                { el: 'H', x: 42, y: 42, z: 42, r: 14, c: '#5b8dce' },
                { el: 'H', x: 42, y: -42, z: -42, r: 14, c: '#5b8dce' },
                { el: 'H', x: -42, y: 42, z: -42, r: 14, c: '#5b8dce' },
                { el: 'H', x: -42, y: -42, z: 42, r: 14, c: '#5b8dce' }
            ],
            bonds: [[0,1,1],[0,2,1],[0,3,1],[0,4,1]]
        },
        ethanol: {
            name: '乙醇 C₂H₅OH', formula: 'C₂H₅OH', mw: 46.07, iupac: 'Ethanol',
            desc: '含羟基(-OH)的醇类化合物，可与钠反应放出 H₂',
            fg: '羟基 -OH', angle: '碳链 ~109.5°(sp³)',
            rxns: [
                '与Na：2C₂H₅OH + 2Na → 2C₂H₅ONa + H₂↑',
                '催化氧化：2C₂H₅OH + O₂ →(Cu/△) 2CH₃CHO + 2H₂O',
                '消去：C₂H₅OH →(浓H₂SO₄/170°C) CH₂=CH₂ + H₂O'
            ],
            atoms: [
                { el: 'C', x: -35, y: 0, z: 0, r: 22, c: '#555' },
                { el: 'C', x: 35, y: 0, z: 0, r: 22, c: '#555' },
                { el: 'O', x: 90, y: 2, z: 12, r: 18, c: '#e06c75', g: 'OH' },
                { el: 'H', x: 122, y: -10, z: 20, r: 12, c: '#5b8dce', g: 'OH' },
                { el: 'H', x: -35, y: -36, z: -22, r: 12, c: '#5b8dce' },
                { el: 'H', x: -72, y: 5, z: 12, r: 12, c: '#5b8dce' },
                { el: 'H', x: -35, y: 36, z: 22, r: 12, c: '#5b8dce' },
                { el: 'H', x: 35, y: -36, z: -16, r: 12, c: '#5b8dce' },
                { el: 'H', x: 35, y: 36, z: 16, r: 12, c: '#5b8dce' }
            ],
            bonds: [[0,1,1],[1,2,1],[2,3,1],[0,4,1],[0,5,1],[0,6,1],[1,7,1],[1,8,1]]
        },
        'acetic-acid': {
            name: '乙酸 CH₃COOH', formula: 'CH₃COOH', mw: 60.05, iupac: 'Acetic acid',
            desc: '含羧基(-COOH)的羧酸类化合物，弱酸',
            fg: '羧基 -COOH', angle: '羰基 C=O ~120°(sp²)',
            rxns: [
                '电离：CH₃COOH ⇌ CH₃COO⁻ + H⁺',
                '酯化：CH₃COOH + C₂H₅OH ⇌ CH₃COOC₂H₅ + H₂O',
                '与碱：CH₃COOH + NaOH → CH₃COONa + H₂O'
            ],
            atoms: [
                { el: 'C', x: -42, y: 0, z: 0, r: 22, c: '#555' },
                { el: 'C', x: 42, y: 0, z: 0, r: 22, c: '#555', g: 'COOH' },
                { el: 'O', x: 42, y: -50, z: 8, r: 16, c: '#e06c75', g: 'COOH' },
                { el: 'O', x: 96, y: 2, z: -5, r: 16, c: '#e06c75', g: 'COOH' },
                { el: 'H', x: 128, y: 8, z: -10, r: 12, c: '#5b8dce', g: 'COOH' },
                { el: 'H', x: -42, y: -36, z: -22, r: 12, c: '#5b8dce' },
                { el: 'H', x: -78, y: 5, z: 12, r: 12, c: '#5b8dce' },
                { el: 'H', x: -42, y: 36, z: 22, r: 12, c: '#5b8dce' }
            ],
            bonds: [[0,1,1],[1,2,2],[1,3,1],[3,4,1],[0,5,1],[0,6,1],[0,7,1]]
        },
        benzene: {
            name: '苯 C₆H₆', formula: 'C₆H₆', mw: 78.11, iupac: 'Benzene',
            desc: '典型芳香族化合物，六元环离域共轭，π 电子离域',
            fg: '苯环（芳香环）', angle: '平面正六边形 120°',
            rxns: [
                '取代：C₆H₆ + Br₂ →(FeBr₃) C₆H₅Br + HBr',
                '硝化：C₆H₆ + HNO₃ →(浓H₂SO₄/△) C₆H₅NO₂ + H₂O',
                '加成：C₆H₆ + 3H₂ →(Ni/△) C₆H₁₂'
            ],
            isRing: true, atoms: [], bonds: []
        },
        propene: {
            name: '丙烯 CH₂=CH–CH₃', formula: 'C₃H₆', mw: 42.08, iupac: 'Propene',
            desc: '含碳碳双键(C=C)的烯烃，可发生加成反应',
            fg: '碳碳双键 C=C', angle: 'C=C ~120°(sp²)，C–C ~109.5°(sp³)',
            rxns: [
                '加成：CH₃CH=CH₂ + HBr → CH₃CHBrCH₃（马氏规则）',
                '加聚：nCH₃CH=CH₂ → [–CH(CH₃)–CH₂–]ₙ',
                '氧化检验：使溴水 / KMnO₄(酸性)褪色'
            ],
            atoms: [
                { el: 'C', x: -56, y: 0, z: 0, r: 22, c: '#555', g: 'C=C' },
                { el: 'C', x: 0, y: 0, z: 0, r: 22, c: '#555', g: 'C=C' },
                { el: 'C', x: 62, y: 0, z: 0, r: 22, c: '#555' },
                { el: 'H', x: -56, y: -40, z: 10, r: 12, c: '#5b8dce' },
                { el: 'H', x: -92, y: 15, z: -10, r: 12, c: '#5b8dce' },
                { el: 'H', x: 0, y: -40, z: -12, r: 12, c: '#5b8dce' },
                { el: 'H', x: 62, y: -32, z: -26, r: 12, c: '#5b8dce' },
                { el: 'H', x: 98, y: 5, z: 10, r: 12, c: '#5b8dce' },
                { el: 'H', x: 62, y: 32, z: 26, r: 12, c: '#5b8dce' }
            ],
            bonds: [[0,1,2],[1,2,1],[0,3,1],[0,4,1],[1,5,1],[2,6,1],[2,7,1],[2,8,1]]
        },
        acetone: {
            name: '丙酮 CH₃COCH₃', formula: 'C₃H₆O', mw: 58.08, iupac: 'Propan-2-one',
            desc: '含羰基(C=O)的酮类化合物，重要有机溶剂',
            fg: '羰基 C=O', angle: '羰基 C=O ~120°(sp²)',
            rxns: [
                '亲核加成：CH₃COCH₃ + HCN → (CH₃)₂C(OH)CN',
                '还原：CH₃COCH₃ + H₂ →(Ni/△) CH₃CH(OH)CH₃',
                '酮不能被银氨溶液氧化（区别于醛）'
            ],
            atoms: [
                { el: 'C', x: -56, y: 0, z: 0, r: 22, c: '#555' },
                { el: 'C', x: 0, y: 0, z: 0, r: 22, c: '#555', g: 'C=O' },
                { el: 'C', x: 56, y: 0, z: 0, r: 22, c: '#555' },
                { el: 'O', x: 0, y: -52, z: 8, r: 17, c: '#e06c75', g: 'C=O' },
                { el: 'H', x: -56, y: -32, z: -26, r: 12, c: '#5b8dce' },
                { el: 'H', x: -92, y: 5, z: 10, r: 12, c: '#5b8dce' },
                { el: 'H', x: -56, y: 32, z: 26, r: 12, c: '#5b8dce' },
                { el: 'H', x: 56, y: -32, z: 26, r: 12, c: '#5b8dce' },
                { el: 'H', x: 92, y: 5, z: -10, r: 12, c: '#5b8dce' },
                { el: 'H', x: 56, y: 32, z: -26, r: 12, c: '#5b8dce' }
            ],
            bonds: [[0,1,1],[1,2,1],[1,3,2],[0,4,1],[0,5,1],[0,6,1],[2,7,1],[2,8,1],[2,9,1]]
        }
    },

    /* ── Utility ── */
    _on(el, ev, fn, o) { el.addEventListener(ev, fn, o); this._listeners.push({ el, ev, fn, o }); },
    _rotY(x, y, z, a) { const c = Math.cos(a), s = Math.sin(a); return [c * x + s * z, y, -s * x + c * z]; },
    _rotX(x, y, z, a) { const c = Math.cos(a), s = Math.sin(a); return [x, c * y - s * z, s * y + c * z]; },
    proj(ox, oy, oz) {
        let [x, y, z] = this._rotY(ox, oy, oz, this.rotY);
        [x, y, z] = this._rotX(x, y, z, this.rotX);
        const s = 280 / (280 + z);
        return { x: x * s, y: y * s, z, s };
    },
    _lit(hex, n) {
        let r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
        r = Math.min(255, r + n); g = Math.min(255, g + n); b = Math.min(255, b + n);
        return '#' + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
    },
    _drk(hex, n) {
        let r = parseInt(hex.slice(1, 3), 16), g = parseInt(hex.slice(3, 5), 16), b = parseInt(hex.slice(5, 7), 16);
        r = Math.max(0, r - n); g = Math.max(0, g - n); b = Math.max(0, b - n);
        return '#' + ((1 << 24) | (r << 16) | (g << 8) | b).toString(16).slice(1);
    },

    /* ── Lifecycle ── */
    init() {
        this.canvas = document.getElementById('organic-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.time = 0; this.running = true; this.paused = false;
        this.autoRot = true; this.rotX = -0.3; this.rotY = 0.5;
        this._lastT = 0; this._hitIdx = -1;
        this._mx = -999; this._my = -999;
        this.buildBenzene();
        this.resize();
        this.bindEvents();
        this._lastT = performance.now();
        this.loop();
        this.updateInfo();
    },

    destroy() {
        this.running = false;
        if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
        for (const l of this._listeners) l.el.removeEventListener(l.ev, l.fn, l.o);
        this._listeners = [];
        if (this._resizeObs) { this._resizeObs.disconnect(); this._resizeObs = null; }
    },

    buildBenzene() {
        const b = this.molecules.benzene;
        b.atoms = []; b.bonds = [];
        const R = 50;
        for (let i = 0; i < 6; i++) {
            const a = (i / 6) * Math.PI * 2 - Math.PI / 2;
            b.atoms.push({ el: 'C', x: R * Math.cos(a), y: R * Math.sin(a), z: 0, r: 16, c: '#555', g: '苯环' });
        }
        for (let i = 0; i < 6; i++) {
            const a = (i / 6) * Math.PI * 2 - Math.PI / 2;
            b.atoms.push({ el: 'H', x: (R + 34) * Math.cos(a), y: (R + 34) * Math.sin(a), z: 0, r: 11, c: '#5b8dce' });
        }
        for (let i = 0; i < 6; i++) {
            b.bonds.push([i, (i + 1) % 6, i % 2 === 0 ? 2 : 1]);
            b.bonds.push([i, i + 6, 1]);
        }
    },

    resize() {
        const p = this.canvas.parentElement;
        if (!p) return;
        const dpr = window.devicePixelRatio || 1;
        const w = p.getBoundingClientRect().width;
        const h = Math.min(Math.max(w * 0.5, 300), 420);
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w; this.H = h;
    },

    bindEvents() {
        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => this.resize());
            this._resizeObs.observe(this.canvas.parentElement);
        }
        document.querySelectorAll('.organic-mol-btn').forEach(btn => {
            if (!btn.dataset.mol) return;
            this._on(btn, 'click', () => {
                document.querySelectorAll('.organic-mol-btn[data-mol]').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.molecule = btn.dataset.mol;
                this.time = 0; this.rotX = -0.3; this.rotY = 0.5; this.autoRot = true;
                this.updateInfo();
            });
        });
        const pauseBtn = document.getElementById('organic-pause');
        if (pauseBtn) {
            this._on(pauseBtn, 'click', () => {
                this.paused = !this.paused;
                pauseBtn.textContent = this.paused ? '▶ 继续' : '⏸ 暂停';
                pauseBtn.setAttribute('aria-pressed', String(this.paused));
            });
        }
        // Mouse drag rotation
        this._on(this.canvas, 'mousedown', e => {
            this._drag = true;
            this._dx0 = e.clientX; this._dy0 = e.clientY;
            this._rx0 = this.rotX; this._ry0 = this.rotY;
            this.autoRot = false;
            this.canvas.style.cursor = 'grabbing';
        });
        this._on(window, 'mousemove', e => {
            const r = this.canvas.getBoundingClientRect();
            this._mx = e.clientX - r.left; this._my = e.clientY - r.top;
            if (this._drag) {
                this.rotY = this._ry0 + (e.clientX - this._dx0) * 0.008;
                this.rotX = Math.max(-1.4, Math.min(1.4, this._rx0 + (e.clientY - this._dy0) * 0.008));
            }
        });
        this._on(window, 'mouseup', () => {
            if (this._drag) { this._drag = false; this.canvas.style.cursor = 'grab'; }
        });
        this._on(this.canvas, 'mouseleave', () => {
            this._mx = -999; this._my = -999; this._hitIdx = -1;
        });
        // Touch
        const tp = { passive: false };
        this._on(this.canvas, 'touchstart', e => {
            if (e.touches.length !== 1) return; e.preventDefault();
            const t = e.touches[0];
            this._drag = true; this._dx0 = t.clientX; this._dy0 = t.clientY;
            this._rx0 = this.rotX; this._ry0 = this.rotY; this.autoRot = false;
        }, tp);
        this._on(this.canvas, 'touchmove', e => {
            if (!this._drag || e.touches.length !== 1) return; e.preventDefault();
            const t = e.touches[0];
            this.rotY = this._ry0 + (t.clientX - this._dx0) * 0.008;
            this.rotX = Math.max(-1.4, Math.min(1.4, this._rx0 + (t.clientY - this._dy0) * 0.008));
        }, tp);
        this._on(this.canvas, 'touchend', () => { this._drag = false; });
        this.canvas.style.cursor = 'grab';
        this.canvas.setAttribute('role', 'img');
        this.canvas.setAttribute('aria-label', '有机分子三维结构可视化，可拖拽旋转');
    },

    updateInfo() {
        const m = this.molecules[this.molecule];
        const el = document.getElementById('organic-info');
        if (!el) return;
        el.innerHTML =
            '<div class="oc-hd">' +
                '<span class="oc-name">' + m.name + '</span>' +
                '<span class="oc-badge">' + m.iupac + '</span>' +
                '<span class="oc-badge oc-badge--mw">M = ' + m.mw + '</span>' +
            '</div>' +
            '<div class="oc-row"><span class="oc-tag">官能团</span>' + m.fg + '</div>' +
            '<div class="oc-row"><span class="oc-tag oc-tag--blue">键角</span>' + m.angle + '</div>' +
            '<div class="oc-row"><span class="oc-tag oc-tag--amber">描述</span>' + m.desc + '</div>' +
            '<div class="oc-rxns"><span class="oc-tag oc-tag--red">反应</span><ul>' +
                m.rxns.map(r => '<li>' + r + '</li>').join('') +
            '</ul></div>';
    },

    /* ── Animation ── */
    loop() {
        if (!this.running) return;
        const now = performance.now();
        const dt = Math.min((now - this._lastT) / 1000, 0.05);
        this._lastT = now;
        if (!this.paused) {
            this.time += dt;
            if (this.autoRot) this.rotY += dt * 0.3;
        }
        this.draw();
        this._raf = requestAnimationFrame(() => this.loop());
    },

    draw() {
        const { ctx, W, H } = this;
        if (!ctx || W === 0) return;
        ctx.clearRect(0, 0, W, H);
        const mol = this.molecules[this.molecule];
        if (!mol) return;
        const cx = W / 2, cy = H / 2;

        // Project all atoms
        const proj = mol.atoms.map((a, i) => {
            const p = this.proj(a.x, a.y, a.z);
            return { ...a, px: cx + p.x, py: cy + p.y, pz: p.z, ps: p.s, idx: i };
        });

        // Hover detection
        this._hitIdx = -1;
        let hitGroup = null;
        if (this._mx > 0 && this._my > 0 && !this._drag) {
            let best = 999;
            proj.forEach((a, i) => {
                const d = Math.hypot(a.px - this._mx, a.py - this._my);
                if (d < a.r * a.ps + 8 && d < best) { best = d; this._hitIdx = i; hitGroup = a.g || null; }
            });
        }
        const hl = new Set();
        if (hitGroup) proj.forEach(a => { if (a.g === hitGroup) hl.add(a.idx); });
        else if (this._hitIdx >= 0) hl.add(this._hitIdx);

        // Bonds sorted by depth
        const bonds = mol.bonds.map(([i, j, o]) => ({ i, j, o, z: (proj[i].pz + proj[j].pz) / 2 }));
        bonds.sort((a, b) => a.z - b.z);
        bonds.forEach(b => {
            const a1 = proj[b.i], a2 = proj[b.j];
            this._drawBond(a1.px, a1.py, a2.px, a2.py, b.o, hl.has(b.i) && hl.has(b.j));
        });

        // Benzene delocalized ring
        if (mol.isRing) {
            const rc = this.proj(0, 0, 0);
            const pulse = 0.2 + Math.sin(this.time * 2) * 0.15;
            ctx.strokeStyle = 'rgba(229,192,123,' + pulse.toFixed(2) + ')';
            ctx.lineWidth = 2; ctx.setLineDash([5, 4]);
            ctx.beginPath(); ctx.arc(cx + rc.x, cy + rc.y, 30 * rc.s, 0, Math.PI * 2); ctx.stroke();
            ctx.setLineDash([]);
        }

        // Atoms sorted back-to-front
        const sorted = [...proj].sort((a, b) => a.pz - b.pz);
        sorted.forEach(a => this._drawAtom(a.px, a.py, a.r * a.ps, a.c, a.el, hl.has(a.idx), a.idx === this._hitIdx));

        // Tooltip
        if (this._hitIdx >= 0) {
            const a = proj[this._hitIdx];
            this._drawTip(a.px, a.py - a.r * a.ps - 12, [a.el + (a.g ? '  (' + a.g + ')' : '')]);
        }

        // Hint
        if (this.autoRot && !this.paused) {
            ctx.fillStyle = 'rgba(255,255,255,0.13)';
            ctx.font = '11px ' + CF.sans; ctx.textAlign = 'center';
            ctx.fillText('🖱 拖拽旋转分子 · 悬停查看原子', cx, H - 10);
        }
    },

    /* ── Render helpers ── */
    _drawBond(x1, y1, x2, y2, order, glow) {
        const ctx = this.ctx;
        const dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy);
        if (len < 1) return;
        const nx = -dy / len, ny = dx / len;
        ctx.lineWidth = glow ? 3 : 2.5;
        ctx.strokeStyle = glow ? 'rgba(229,192,123,0.55)' : 'rgba(255,255,255,0.18)';
        if (order >= 2) {
            const off = 3.5;
            ctx.beginPath(); ctx.moveTo(x1 + nx * off, y1 + ny * off); ctx.lineTo(x2 + nx * off, y2 + ny * off); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(x1 - nx * off, y1 - ny * off); ctx.lineTo(x2 - nx * off, y2 - ny * off); ctx.stroke();
            if (order === 3) { ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke(); }
        } else {
            ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
        }
        if (glow) {
            ctx.save();
            ctx.shadowColor = 'rgba(229,192,123,0.45)'; ctx.shadowBlur = 8;
            ctx.strokeStyle = 'rgba(229,192,123,0.15)'; ctx.lineWidth = 5;
            ctx.beginPath(); ctx.moveTo(x1, y1); ctx.lineTo(x2, y2); ctx.stroke();
            ctx.restore();
        }
    },

    _drawAtom(x, y, r, color, el, highlight, hovered) {
        const ctx = this.ctx;
        if (highlight || hovered) {
            ctx.save();
            ctx.shadowColor = hovered ? 'rgba(229,192,123,0.7)' : 'rgba(229,192,123,0.35)';
            ctx.shadowBlur = hovered ? 14 : 8;
            ctx.beginPath(); ctx.arc(x, y, r + 2, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(229,192,123,0.12)'; ctx.fill();
            ctx.restore();
        }
        const g = ctx.createRadialGradient(x - r * 0.3, y - r * 0.3, r * 0.08, x, y, r);
        g.addColorStop(0, this._lit(color, 55));
        g.addColorStop(0.5, color);
        g.addColorStop(1, this._drk(color, 35));
        ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2);
        ctx.fillStyle = g; ctx.fill();
        // Specular highlight
        ctx.beginPath(); ctx.arc(x - r * 0.25, y - r * 0.25, r * 0.32, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255,0.22)'; ctx.fill();
        // Label
        ctx.fillStyle = '#fff';
        ctx.font = (el.length === 1 ? 'bold ' : '') + Math.round(r * 0.82) + 'px ' + CF.sans;
        ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
        ctx.fillText(el, x, y + 1);
    },

    _drawTip(x, y, lines) {
        const ctx = this.ctx;
        ctx.font = '11px ' + CF.sans;
        const w = Math.max(...lines.map(l => ctx.measureText(l).width)) + 16;
        const h = lines.length * 16 + 8;
        const tx = Math.max(4, Math.min(x - w / 2, this.W - w - 4));
        const ty = Math.max(4, y - h);
        ctx.fillStyle = 'rgba(25,25,35,0.88)';
        ctx.beginPath();
        if (ctx.roundRect) ctx.roundRect(tx, ty, w, h, 5); else ctx.rect(tx, ty, w, h);
        ctx.fill();
        ctx.strokeStyle = 'rgba(229,192,123,0.35)'; ctx.lineWidth = 1; ctx.stroke();
        ctx.fillStyle = 'rgba(255,255,255,0.9)';
        ctx.textAlign = 'left'; ctx.textBaseline = 'top';
        lines.forEach((l, i) => ctx.fillText(l, tx + 8, ty + 4 + i * 16));
    }
};

function initOrganicChem() { OrganicChem.init(); }
window.OrganicChem = OrganicChem;
window.initOrganicChem = initOrganicChem;
/* ═══════════════════════════════════════════════════
   Gene Expression – Transcription & Translation
   ═══════════════════════════════════════════════════ */
const GeneExpression = {
    _listeners: [],
    _on(el, evt, fn, opts) { el.addEventListener(evt, fn, opts); this._listeners.push({ el, evt, fn, opts }); },
    canvas: null, ctx: null, animId: null,
    mode: 'transcription', // transcription | translation
    progress: 0,
    autoPlay: true,
    speed: 1,
    // DNA template strand
    dnaTemplate: ['T','A','C','G','A','T','C','C','A','T','A','G','G','C','T','A','C','T'],
    // codon table (simplified)
    codonTable: {
        'AUG': 'Met(\u8D77\u59CB)', 'GCU': 'Ala', 'GCC': 'Ala', 'GAU': 'Asp',
        'UUU': 'Phe', 'UUC': 'Phe', 'CCA': 'Pro', 'GGU': 'Gly',
        'UAC': 'Tyr', 'CUA': 'Leu', 'GUA': 'Val', 'AGA': 'Arg',
        'UAA': 'Stop', 'UAG': 'Stop', 'UGA': 'Stop'
    },

    init() {
        this.canvas = document.getElementById('gene-expression-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this._resize();
        this._on(window, 'resize', () => this._resize());
        this._buildControls();
        this._injectInfoPanel();
        this._loop();
    },
    destroy() {
        if (this.animId) { cancelAnimationFrame(this.animId); this.animId = null; }
        this._listeners.forEach(l => l.el.removeEventListener(l.evt, l.fn, l.opts));
        this._listeners.length = 0;
        this.autoPlay = true;
        const c = document.getElementById('gene-expression-controls');
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
    },
    _buildControls() {
        const ctrl = document.getElementById('gene-expression-controls');
        if (!ctrl) return;
        ctrl.innerHTML = '';
        const modes = [
            { id: 'transcription', label: '\u8F6C\u5F55 (DNA\u2192mRNA)' },
            { id: 'translation', label: '\u7FFB\u8BD1 (mRNA\u2192\u86CB\u767D\u8D28)' }
        ];
        const btnWrap = document.createElement('div');
        btnWrap.className = 'genexp-mode-btns';
        modes.forEach(m => {
            const b = document.createElement('button');
            b.className = 'genexp-mode-btn' + (m.id === this.mode ? ' active' : '');
            b.textContent = m.label;
            this._on(b, 'click', () => {
                this.mode = m.id;
                this.progress = 0;
                btnWrap.querySelectorAll('.genexp-mode-btn').forEach(x => x.classList.remove('active'));
                b.classList.add('active');
                this._updateInfo();
            });
            btnWrap.appendChild(b);
        });
        ctrl.appendChild(btnWrap);
        // speed
        const label = document.createElement('label');
        label.className = 'genexp-speed';
        label.innerHTML = '<span>\u901F\u5EA6</span>';
        const inp = document.createElement('input');
        inp.type = 'range'; inp.min = 0.3; inp.max = 3; inp.step = 0.1; inp.value = 1;
        this._on(inp, 'input', () => { this.speed = parseFloat(inp.value); });
        label.appendChild(inp);
        ctrl.appendChild(label);
        // replay
        const btn = document.createElement('button');
        btn.className = 'genexp-mode-btn';
        btn.textContent = '\u91CD\u64AD';
        this._on(btn, 'click', () => { this.progress = 0; });
        ctrl.appendChild(btn);
    },
    _complement(base) {
        return { 'A': 'U', 'T': 'A', 'C': 'G', 'G': 'C' }[base] || '?';
    },
    _dnaComplement(base) {
        return { 'A': 'T', 'T': 'A', 'C': 'G', 'G': 'C' }[base] || '?';
    },
    _baseColor(base) {
        return { 'A': 'rgba(100,200,100,0.8)', 'T': 'rgba(220,80,80,0.8)', 'U': 'rgba(255,150,50,0.8)', 'C': 'rgba(100,150,255,0.8)', 'G': 'rgba(255,200,50,0.8)' }[base] || 'rgba(200,200,200,0.5)';
    },

    _drawTranscription(t) {
        const ctx = this.ctx, W = this.W, H = this.H;
        const dna = this.dnaTemplate;
        const n = dna.length;
        const bw = Math.min(36, (W - 80) / n);
        const startX = (W - n * bw) / 2;
        const dnaY = H * 0.3;
        const mrnaY = H * 0.6;

        // title
        ctx.font = 'bold 14px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(58,158,143,0.9)';
        ctx.fillText('\u8F6C\u5F55\u8FC7\u7A0B: DNA \u2192 mRNA', W / 2, 24);

        // labels
        ctx.font = '12px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillStyle = 'rgba(200,200,200,0.6)';
        ctx.fillText('DNA \u6A21\u677F\u94FE (3\u2032\u21925\u2032)', startX - 8, dnaY + 5);
        ctx.fillText('DNA \u7F16\u7801\u94FE (5\u2032\u21923\u2032)', startX - 8, dnaY - 25);
        ctx.fillText('mRNA (5\u2032\u21923\u2032)', startX - 8, mrnaY + 5);

        // RNA polymerase position
        const polyPos = Math.floor(this.progress * n);

        // draw DNA double strand
        for (let i = 0; i < n; i++) {
            const x = startX + i * bw;
            const base = dna[i];
            const comp = this._dnaComplement(base);

            // coding strand (top)
            ctx.fillStyle = i < polyPos ? 'rgba(200,200,200,0.2)' : this._baseColor(comp);
            ctx.fillRect(x + 1, dnaY - 30, bw - 2, 18);
            ctx.font = 'bold 11px monospace';
            ctx.textAlign = 'center';
            ctx.fillStyle = i < polyPos ? 'rgba(200,200,200,0.3)' : 'rgba(255,255,255,0.9)';
            ctx.fillText(comp, x + bw / 2, dnaY - 18);

            // template strand (bottom)
            const isUnwound = (i >= polyPos - 2 && i <= polyPos + 2);
            const templateOffsetY = isUnwound ? 10 : 0;
            ctx.fillStyle = this._baseColor(base);
            ctx.fillRect(x + 1, dnaY + templateOffsetY, bw - 2, 18);
            ctx.font = 'bold 11px monospace';
            ctx.textAlign = 'center';
            ctx.fillStyle = 'rgba(255,255,255,0.9)';
            ctx.fillText(base, x + bw / 2, dnaY + templateOffsetY + 12);

            // hydrogen bonds
            if (!isUnwound) {
                ctx.beginPath();
                ctx.moveTo(x + bw / 2, dnaY - 12);
                ctx.lineTo(x + bw / 2, dnaY);
                ctx.strokeStyle = 'rgba(200,200,200,0.15)';
                ctx.lineWidth = 1;
                ctx.setLineDash([2, 2]);
                ctx.stroke();
                ctx.setLineDash([]);
            }

            // mRNA being synthesized
            if (i < polyPos) {
                const mrnaBase = this._complement(base);
                ctx.fillStyle = this._baseColor(mrnaBase);
                ctx.fillRect(x + 1, mrnaY, bw - 2, 18);
                ctx.font = 'bold 11px monospace';
                ctx.textAlign = 'center';
                ctx.fillStyle = 'rgba(255,255,255,0.9)';
                ctx.fillText(mrnaBase, x + bw / 2, mrnaY + 12);
            }
        }

        // RNA polymerase
        if (polyPos < n) {
            const px = startX + polyPos * bw;
            ctx.beginPath();
            ctx.ellipse(px, dnaY + 5, 20, 14, 0, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(58,158,143,0.3)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(58,158,143,0.6)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            ctx.font = '9px "Noto Sans SC", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillStyle = 'rgba(58,158,143,0.9)';
            ctx.fillText('RNA\u805A\u5408\u9176', px, dnaY + 8);
        }

        // direction arrow
        ctx.beginPath();
        ctx.moveTo(startX + polyPos * bw + 25, (dnaY + mrnaY) / 2);
        ctx.lineTo(startX + polyPos * bw + 25, mrnaY - 5);
        ctx.strokeStyle = 'rgba(58,158,143,0.4)';
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // legend
        ctx.font = '10px monospace';
        ctx.textAlign = 'left';
        const bases = ['A', 'T', 'U', 'C', 'G'];
        bases.forEach((b, i) => {
            ctx.fillStyle = this._baseColor(b);
            ctx.fillRect(14 + i * 40, H - 25, 12, 12);
            ctx.fillStyle = 'rgba(200,200,200,0.6)';
            ctx.fillText(b, 28 + i * 40, H - 15);
        });
    },

    _drawTranslation(t) {
        const ctx = this.ctx, W = this.W, H = this.H;
        const dna = this.dnaTemplate;
        // generate mRNA from DNA template
        const mrna = dna.map(b => this._complement(b));
        const n = mrna.length;
        const bw = Math.min(30, (W - 80) / n);
        const startX = (W - n * bw) / 2;
        const mrnaY = H * 0.35;
        const proteinY = H * 0.72;

        ctx.font = 'bold 14px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillStyle = 'rgba(58,158,143,0.9)';
        ctx.fillText('\u7FFB\u8BD1\u8FC7\u7A0B: mRNA \u2192 \u86CB\u767D\u8D28 (\u6C28\u57FA\u9178\u94FE)', W / 2, 24);

        // draw mRNA strand
        ctx.font = '10px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillStyle = 'rgba(200,200,200,0.5)';
        ctx.fillText('mRNA', startX - 6, mrnaY + 12);

        for (let i = 0; i < n; i++) {
            const x = startX + i * bw;
            ctx.fillStyle = this._baseColor(mrna[i]);
            ctx.fillRect(x + 1, mrnaY, bw - 2, 18);
            ctx.font = 'bold 10px monospace';
            ctx.textAlign = 'center';
            ctx.fillStyle = 'rgba(255,255,255,0.9)';
            ctx.fillText(mrna[i], x + bw / 2, mrnaY + 12);
        }

        // codon grouping
        const codons = [];
        for (let i = 0; i < n - 2; i += 3) {
            codons.push(mrna[i] + mrna[i + 1] + mrna[i + 2]);
        }

        // ribosome position (codon index)
        const riboPos = Math.floor(this.progress * codons.length);

        // draw codon brackets
        for (let i = 0; i < codons.length; i++) {
            const x1 = startX + i * 3 * bw;
            const x2 = x1 + 3 * bw;
            ctx.beginPath();
            ctx.moveTo(x1 + 2, mrnaY + 20);
            ctx.lineTo(x1 + 2, mrnaY + 26);
            ctx.lineTo(x2 - 2, mrnaY + 26);
            ctx.lineTo(x2 - 2, mrnaY + 20);
            ctx.strokeStyle = i < riboPos ? 'rgba(58,158,143,0.5)' : 'rgba(200,200,200,0.15)';
            ctx.lineWidth = 1;
            ctx.stroke();
            // codon text
            ctx.font = '9px monospace';
            ctx.textAlign = 'center';
            ctx.fillStyle = i < riboPos ? 'rgba(58,158,143,0.7)' : 'rgba(200,200,200,0.3)';
            ctx.fillText(codons[i], (x1 + x2) / 2, mrnaY + 38);
        }

        // ribosome
        if (riboPos < codons.length) {
            const rx = startX + riboPos * 3 * bw + 1.5 * bw;
            // large subunit
            ctx.beginPath();
            ctx.ellipse(rx, mrnaY - 10, 22, 12, 0, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(58,158,143,0.15)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(58,158,143,0.4)';
            ctx.lineWidth = 1;
            ctx.stroke();
            // small subunit
            ctx.beginPath();
            ctx.ellipse(rx, mrnaY + 26, 20, 8, 0, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(58,158,143,0.1)';
            ctx.fill();
            ctx.strokeStyle = 'rgba(58,158,143,0.3)';
            ctx.stroke();
            ctx.font = '9px "Noto Sans SC", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillStyle = 'rgba(58,158,143,0.8)';
            ctx.fillText('\u6838\u7CD6\u4F53', rx, mrnaY - 7);
        }

        // tRNA + amino acid chain
        ctx.font = '10px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'right';
        ctx.fillStyle = 'rgba(200,200,200,0.5)';
        ctx.fillText('\u6C28\u57FA\u9178\u94FE', startX - 6, proteinY + 5);

        const aaColors = [
            'rgba(100,200,100,0.7)', 'rgba(200,100,100,0.7)', 'rgba(100,150,255,0.7)',
            'rgba(255,200,50,0.7)', 'rgba(200,100,200,0.7)', 'rgba(100,200,200,0.7)'
        ];

        for (let i = 0; i < Math.min(riboPos, codons.length); i++) {
            const codon = codons[i];
            const aa = this.codonTable[codon] || '?';
            if (aa === 'Stop') break;
            const ax = startX + i * 40 + 20;
            // amino acid circle
            ctx.beginPath();
            ctx.arc(ax, proteinY, 16, 0, Math.PI * 2);
            ctx.fillStyle = aaColors[i % aaColors.length];
            ctx.fill();
            ctx.font = 'bold 9px monospace';
            ctx.textAlign = 'center';
            ctx.fillStyle = 'rgba(255,255,255,0.9)';
            ctx.fillText(aa, ax, proteinY + 3);
            // peptide bond
            if (i > 0) {
                ctx.beginPath();
                ctx.moveTo(ax - 16, proteinY);
                ctx.lineTo(ax - 24, proteinY);
                ctx.strokeStyle = 'rgba(200,200,200,0.4)';
                ctx.lineWidth = 2;
                ctx.stroke();
            }
            // codon label
            ctx.font = '9px "JetBrains Mono", monospace';
            ctx.fillStyle = 'rgba(200,200,200,0.4)';
            ctx.fillText(codon, ax, proteinY + 26);
        }

        // tRNA delivery
        if (riboPos < codons.length) {
            const codon = codons[riboPos];
            const anticodon = codon.split('').map(b => {
                return { 'A': 'U', 'U': 'A', 'C': 'G', 'G': 'C' }[b] || '?';
            }).join('');
            const tx = startX + riboPos * 3 * bw + 1.5 * bw;
            // tRNA shape (inverted L)
            ctx.beginPath();
            ctx.moveTo(tx - 10, mrnaY + 42);
            ctx.lineTo(tx - 10, mrnaY + 55);
            ctx.lineTo(tx, mrnaY + 65);
            ctx.lineTo(tx + 10, mrnaY + 55);
            ctx.lineTo(tx + 10, mrnaY + 42);
            ctx.strokeStyle = 'rgba(255,200,100,0.5)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
            ctx.font = '9px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillStyle = 'rgba(255,200,100,0.7)';
            ctx.fillText('tRNA', tx, mrnaY + 50);
            ctx.fillText(anticodon, tx, mrnaY + 62);
        }
    },

    _draw(t) {
        const ctx = this.ctx, W = this.W, H = this.H;
        ctx.clearRect(0, 0, W, H);
        if (this.mode === 'transcription') {
            this._drawTranscription(t);
        } else {
            this._drawTranslation(t);
        }
        if (this.autoPlay) {
            this.progress += 0.002 * this.speed;
            if (this.progress > 1.1) this.progress = 0;
        }
    },
    _injectInfoPanel() {
        const el = document.getElementById('genexp-info');
        if (!el) return;
        el.innerHTML = `
            <div class="genexp-info__hd">📘 基因表达知识点</div>
            <div class="genexp-info__grid">
                <div class="genexp-info__block">
                    <div class="genexp-info__sub">当前过程</div>
                    <div id="genexp-mode-display" class="genexp-info__val">转录 (DNA→mRNA)</div>
                </div>
                <div class="genexp-info__block">
                    <div class="genexp-info__sub">中心法则</div>
                    <div class="genexp-info__row"><span class="genexp-info__key" style="--c:var(--color-teal,#3a9e8f)">转录</span> DNA → mRNA（RNA聚合酶，细胞核）</div>
                    <div class="genexp-info__row"><span class="genexp-info__key" style="--c:var(--color-purple,#8b6fc0)">翻译</span> mRNA → 蛋白质（核糖体，细胞质）</div>
                </div>
                <div class="genexp-info__block">
                    <div class="genexp-info__sub">碱基配对规则</div>
                    <div class="genexp-info__row"><span class="genexp-info__key" style="--c:#e06c75">转录</span> A-U, T-A, C-G, G-C</div>
                    <div class="genexp-info__row"><span class="genexp-info__key" style="--c:#e5c07b">翻译</span> 密码子与反密码子互补配对</div>
                </div>
                <div class="genexp-info__block">
                    <div class="genexp-info__sub">💡 知识要点</div>
                    <div class="genexp-info__note">mRNA上每3个相邻碱基构成一个密码子，编码一个氨基酸。AUG为起始密码子(Met)，UAA/UAG/UGA为终止密码子。</div>
                </div>
            </div>
        `;
    },

    _updateInfo() {
        const el = document.getElementById('genexp-mode-display');
        if (el) {
            el.textContent = this.mode === 'transcription' ? '转录 (DNA→mRNA)' : '翻译 (mRNA→蛋白质)';
        }
    },

    _loop() {
        const t = performance.now() / 1000;
        this._draw(t);
        this.animId = requestAnimationFrame(() => this._loop());
    }
};

function initGeneExpression() { GeneExpression.init(); }
window.GeneExpression = GeneExpression;
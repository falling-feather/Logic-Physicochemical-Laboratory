// ===== Genetics Visualization v3 =====
// Punnett Square + Population Genetics (Hardy-Weinberg) + Pedigree Chart + Cross Animation
// Canvas-based, DPR-aware, ResizeObserver, event-cleanup ready

const Genetics = {
    canvas: null, ctx: null, W: 0, H: 0,
    info: null, animId: null, time: 0,
    _listeners: [],

    // Mode: 'punnett' | 'population' | 'pedigree'
    mode: 'punnett',

    // ── Punnett state ──
    punnettMode: 'single',  // 'single' | 'double'
    parent1: 'Aa', parent2: 'Aa',
    crossResult: null,
    crossAnim: null, // {phase:'gamete'|'combine'|'done', t:0, gametes1:[], gametes2:[], pairs:[]}

    // ── Population state (Hardy-Weinberg) ──
    popFreqP: 0.5,         // dominant allele frequency
    popSize: 200,
    popGenerations: 0,
    popHistory: [],         // [{p, q, AA, Aa, aa}]
    popIndividuals: [],     // [{genotype, x, y, vx, vy}]
    popRunning: false,
    popSelection: 'none',   // 'none' | 'against_aa' | 'for_AA' | 'heterozygote_advantage'
    popMutation: false,
    popDrift: false,

    // ── Pedigree state ──
    pedigreePreset: 'autosomal_dominant',
    pedigreeData: null,

    /* ============ Init / Destroy ============ */

    init() {
        this.canvas = document.getElementById('genetics-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.info = document.getElementById('genetics-info');

        this.resize();
        this.bindControls();
        this.startLoop();

        if (typeof ResizeObserver !== 'undefined') {
            const ro = new ResizeObserver(() => this.resize());
            ro.observe(this.canvas.parentElement);
            this._ro = ro;
        }
        this._onResize = () => this.resize();
        window.addEventListener('resize', this._onResize);
    },

    destroy() {
        if (this.animId) { cancelAnimationFrame(this.animId); this.animId = null; }
        if (this._ro) { this._ro.disconnect(); this._ro = null; }
        if (this._onResize) { window.removeEventListener('resize', this._onResize); }
        this._listeners.forEach(([el, evt, fn, opts]) => el.removeEventListener(evt, fn, opts));
        this._listeners = [];
    },

    _on(el, evt, fn, opts) {
        if (!el) return;
        el.addEventListener(evt, fn, opts);
        this._listeners.push([el, evt, fn, opts]);
    },

    resize() {
        const wrap = this.canvas.parentElement;
        if (!wrap) return;
        const w = wrap.clientWidth;
        if (w === 0) return;
        const h = Math.min(Math.round(w * 0.72), 520);
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w; this.H = h;
    },

    bindControls() {
        // Cross button
        this._on(document.getElementById('bio-cross'), 'click', () => {
            if (this.mode !== 'punnett') { this.switchMode('punnett'); }
            this.performCross();
        });

        // Parent selects
        const s1 = document.getElementById('bio-parent1');
        const s2 = document.getElementById('bio-parent2');
        this._on(s1, 'change', () => { this.parent1 = s1.value; });
        this._on(s2, 'change', () => { this.parent2 = s2.value; });

        // Mode toggle — inject buttons if not exist
        this._injectModeButtons();

        // Punnett single/double toggle
        this._on(document.getElementById('bio-genetics-single'), 'click', () => {
            this.punnettMode = 'single';
            this._updateParentOptions();
            this.crossResult = null; this.crossAnim = null;
        });
        this._on(document.getElementById('bio-genetics-double'), 'click', () => {
            this.punnettMode = 'double';
            this._updateParentOptions();
            this.crossResult = null; this.crossAnim = null;
        });

        // Population controls
        this._on(document.getElementById('bio-pop-start'), 'click', () => {
            if (this.mode !== 'population') this.switchMode('population');
            this.popRunning = !this.popRunning;
            const btn = document.getElementById('bio-pop-start');
            if (btn) btn.textContent = this.popRunning ? '\u6682\u505c' : '\u7ee7\u7eed\u6f14\u5316';
        });
        this._on(document.getElementById('bio-pop-reset'), 'click', () => {
            this.resetPopulation();
        });
        this._on(document.getElementById('bio-pop-freq'), 'input', (e) => {
            this.popFreqP = parseFloat(e.target.value) || 0.5;
            if (!this.popRunning) this.resetPopulation();
        });
        this._on(document.getElementById('bio-pop-selection'), 'change', (e) => {
            this.popSelection = e.target.value;
        });

        // Pedigree controls
        this._on(document.getElementById('bio-pedigree-preset'), 'change', (e) => {
            this.pedigreePreset = e.target.value;
            this.buildPedigree();
        });

        // Canvas click
        this._on(this.canvas, 'click', (e) => {
            if (this.mode === 'pedigree') {
                const r = this.canvas.getBoundingClientRect();
                const mx = (e.clientX - r.left), my = (e.clientY - r.top);
                this._pedigreeClick(mx, my);
            }
        });
    },

    _injectModeButtons() {
        const controls = this.canvas.parentElement.querySelector('.viz-controls');
        if (!controls) return;

        // Check if already injected
        if (document.getElementById('bio-genetics-modes')) return;

        const wrap = document.createElement('div');
        wrap.id = 'bio-genetics-modes';
        wrap.className = 'genetics-modes';
        wrap.innerHTML = '<button class="gen-mode-btn active" data-mode="punnett">\u5b5f\u5fb7\u5c14\u6742\u4ea4</button>'
            + '<button class="gen-mode-btn" data-mode="population">\u79cd\u7fa4\u9057\u4f20</button>'
            + '<button class="gen-mode-btn" data-mode="pedigree">\u7cfb\u8c31\u56fe</button>';
        controls.parentElement.insertBefore(wrap, controls);

        wrap.querySelectorAll('.gen-mode-btn').forEach(btn => {
            this._on(btn, 'click', () => {
                this.switchMode(btn.dataset.mode);
            });
        });
    },

    switchMode(mode) {
        this.mode = mode;
        this.crossAnim = null;
        this.popRunning = false;
        const startBtn = document.getElementById('bio-pop-start');
        if (startBtn) startBtn.textContent = '\u5f00\u59cb\u6f14\u5316';

        // Update button active state
        document.querySelectorAll('.gen-mode-btn').forEach(b => {
            b.classList.toggle('active', b.dataset.mode === mode);
        });

        // Show/hide control groups
        const punnettCtrls = document.getElementById('bio-punnett-controls');
        const popCtrls = document.getElementById('bio-pop-controls');
        const pedCtrls = document.getElementById('bio-pedigree-controls');
        if (punnettCtrls) punnettCtrls.style.display = mode === 'punnett' ? '' : 'none';
        if (popCtrls) popCtrls.style.display = mode === 'population' ? '' : 'none';
        if (pedCtrls) pedCtrls.style.display = mode === 'pedigree' ? '' : 'none';

        if (mode === 'population' && this.popHistory.length === 0) {
            this.resetPopulation();
        }
        if (mode === 'pedigree' && !this.pedigreeData) {
            this.buildPedigree();
        }

        const msgs = {
            punnett: '\u9009\u62e9\u4eb2\u672c\u57fa\u56e0\u578b\uff0c\u70b9\u51fb\u6742\u4ea4\u67e5\u770b\u540e\u4ee3\u6bd4\u4f8b',
            population: '\u8bbe\u7f6e\u7b49\u4f4d\u57fa\u56e0\u9891\u7387\uff0c\u89c2\u5bdf\u79cd\u7fa4\u8fdb\u5316\u52a8\u6001',
            pedigree: '\u70b9\u51fb\u4e2a\u4f53\u67e5\u770b\u57fa\u56e0\u578b\uff0c\u5206\u6790\u9057\u4f20\u65b9\u5f0f'
        };
        if (this.info) this.info.textContent = msgs[mode] || '';
    },

    /* ============ Animation Loop ============ */

    startLoop() {
        const loop = (now) => {
            if (!now) now = performance.now();
            this.time = now / 1000;
            this.update();
            this.draw();
            this.animId = requestAnimationFrame(loop);
        };
        this.animId = requestAnimationFrame(loop);
    },

    update() {
        // Cross animation
        if (this.crossAnim && this.crossAnim.phase !== 'done') {
            this.crossAnim.t += 0.016;
            if (this.crossAnim.phase === 'gamete' && this.crossAnim.t > 1.2) {
                this.crossAnim.phase = 'combine';
                this.crossAnim.t = 0;
            }
            if (this.crossAnim.phase === 'combine' && this.crossAnim.t > 1.5) {
                this.crossAnim.phase = 'done';
            }
        }

        // Population simulation
        if (this.mode === 'population' && this.popRunning) {
            this._popStep();
        }
    },

    /* ============ Punnett Square ============ */

    _updateParentOptions() {
        const s1 = document.getElementById('bio-parent1');
        const s2 = document.getElementById('bio-parent2');
        if (!s1 || !s2) return;

        if (this.punnettMode === 'single') {
            const opts = '<option value="AA">AA (\u7eaf\u5408\u663e\u6027)</option>'
                + '<option value="Aa" selected>Aa (\u6742\u5408)</option>'
                + '<option value="aa">aa (\u7eaf\u5408\u9690\u6027)</option>';
            s1.innerHTML = opts; s2.innerHTML = opts;
            s1.value = 'Aa'; s2.value = 'Aa';
        } else {
            const opts = '<option value="AABB">AABB</option>'
                + '<option value="AaBb" selected>AaBb</option>'
                + '<option value="AABb">AABb</option>'
                + '<option value="AaBB">AaBB</option>'
                + '<option value="aaBb">aaBb</option>'
                + '<option value="Aabb">Aabb</option>'
                + '<option value="aabb">aabb</option>'
                + '<option value="AAbb">AAbb</option>'
                + '<option value="aaBB">aaBB</option>';
            s1.innerHTML = opts; s2.innerHTML = opts;
            s1.value = 'AaBb'; s2.value = 'AaBb';
        }
        this.parent1 = s1.value;
        this.parent2 = s2.value;
    },

    performCross() {
        this.parent1 = document.getElementById('bio-parent1')?.value || this.parent1;
        this.parent2 = document.getElementById('bio-parent2')?.value || this.parent2;

        const g1 = this._getGametes(this.parent1);
        const g2 = this._getGametes(this.parent2);

        const grid = [];
        const counts = {};
        for (const a of g1) {
            for (const b of g2) {
                const genotype = this._normalizeGenotype(a + b);
                grid.push(genotype);
                counts[genotype] = (counts[genotype] || 0) + 1;
            }
        }

        this.crossResult = { g1, g2, grid, counts, total: grid.length };

        // Start animation
        this.crossAnim = {
            phase: 'gamete', t: 0,
            gametes1: g1, gametes2: g2, pairs: grid
        };

        if (this.info) {
            const ratios = Object.entries(counts).map(([k, v]) => k + ':' + v).join(' , ');
            this.info.innerHTML = '<strong>\u540e\u4ee3\u57fa\u56e0\u578b\u6bd4\u4f8b</strong>\uff1a' + ratios
                + '<br><span style="opacity:0.6">\u8868\u73b0\u578b\u6bd4\u4f8b\uff1a' + this._phenotypeRatio(counts) + '</span>';
        }
    },

    _getGametes(genotype) {
        if (genotype.length === 2) {
            const a1 = genotype[0], a2 = genotype[1];
            if (a1 === a2) return [a1];
            return [a1, a2];
        }
        // Double: AaBb etc
        const a1 = genotype[0], a2 = genotype[1];
        const b1 = genotype[2], b2 = genotype[3];
        const aAlleles = a1 === a2 ? [a1] : [a1, a2];
        const bAlleles = b1 === b2 ? [b1] : [b1, b2];
        const result = [];
        for (const a of aAlleles) {
            for (const b of bAlleles) result.push(a + b);
        }
        return result;
    },

    _normalizeGenotype(g) {
        if (g.length === 2) {
            const chars = g.split('');
            if (chars[0] === chars[0].toLowerCase() && chars[1] === chars[1].toUpperCase()) {
                return chars[1] + chars[0];
            }
            return g;
        }
        // 4 chars: sort each gene pair
        let a = g.slice(0, 2), b = g.slice(2, 4);
        if (a[0] === a[0].toLowerCase() && a[1] === a[1].toUpperCase()) a = a[1] + a[0];
        if (b[0] === b[0].toLowerCase() && b[1] === b[1].toUpperCase()) b = b[1] + b[0];
        return a + b;
    },

    _genotypeType(g) {
        const upper = g.replace(/[a-z]/g, '').length;
        const lower = g.replace(/[A-Z]/g, '').length;
        if (lower === 0) return 'dominant';
        if (upper === 0) return 'recessive';
        return 'carrier';
    },

    _phenotypeRatio(counts) {
        const phenoCounts = {};
        for (const [g, c] of Object.entries(counts)) {
            const type = this._genotypeType(g);
            const label = type === 'recessive' ? '\u9690\u6027' : '\u663e\u6027';
            phenoCounts[label] = (phenoCounts[label] || 0) + c;
        }
        const values = Object.values(phenoCounts);
        const g = this._gcd(...values);
        return Object.entries(phenoCounts).map(([k, v]) => k + ':' + (v / g)).join(' : ');
    },

    _gcd(...nums) {
        const gcd2 = (a, b) => b === 0 ? a : gcd2(b, a % b);
        return nums.reduce((a, b) => gcd2(a, b));
    },

    /* ============ Population Genetics ============ */

    resetPopulation() {
        const p = this.popFreqP;
        const q = 1 - p;
        this.popGenerations = 0;
        this.popHistory = [{ p, q, AA: p * p, Aa: 2 * p * q, aa: q * q }];
        this.popRunning = false;
        const btn = document.getElementById('bio-pop-start');
        if (btn) btn.textContent = '\u5f00\u59cb\u6f14\u5316';

        // Generate individuals
        this.popIndividuals = [];
        for (let i = 0; i < this.popSize; i++) {
            const r = Math.random();
            let genotype;
            if (r < p * p) genotype = 'AA';
            else if (r < p * p + 2 * p * q) genotype = 'Aa';
            else genotype = 'aa';
            this.popIndividuals.push({
                genotype,
                x: Math.random() * this.W * 0.55 + this.W * 0.02,
                y: Math.random() * this.H * 0.65 + this.H * 0.05,
                vx: (Math.random() - 0.5) * 0.8,
                vy: (Math.random() - 0.5) * 0.8,
                alive: true
            });
        }

        if (this.info) {
            this.info.innerHTML = '<strong>Hardy-Weinberg \u5e73\u8861</strong>\uff1ap=' + p.toFixed(2) + ', q=' + q.toFixed(2)
                + ' \u2192 AA:' + (p * p * 100).toFixed(1) + '% Aa:' + (2 * p * q * 100).toFixed(1) + '% aa:' + (q * q * 100).toFixed(1) + '%';
        }
    },

    _popStep() {
        if (!this.popIndividuals.length) return;

        // Move individuals
        const pad = 4;
        const maxX = this.W * 0.57, maxY = this.H * 0.7;
        for (const ind of this.popIndividuals) {
            if (!ind.alive) continue;
            ind.x += ind.vx;
            ind.y += ind.vy;
            if (ind.x < pad || ind.x > maxX) ind.vx *= -1;
            if (ind.y < pad || ind.y > maxY) ind.vy *= -1;
            ind.x = Math.max(pad, Math.min(maxX, ind.x));
            ind.y = Math.max(pad, Math.min(maxY, ind.y));
        }

        // Every ~60 frames, do a generation step
        this._popAccum = (this._popAccum || 0) + 1;
        if (this._popAccum < 60) return;
        this._popAccum = 0;

        // Selection
        if (this.popSelection !== 'none') {
            const living = this.popIndividuals.filter(i => i.alive);
            for (const ind of living) {
                let survivalRate = 1.0;
                if (this.popSelection === 'against_aa' && ind.genotype === 'aa') survivalRate = 0.5;
                if (this.popSelection === 'for_AA' && ind.genotype !== 'AA') survivalRate = 0.7;
                if (this.popSelection === 'heterozygote_advantage') {
                    if (ind.genotype === 'AA') survivalRate = 0.8;
                    if (ind.genotype === 'aa') survivalRate = 0.6;
                }
                if (Math.random() > survivalRate) ind.alive = false;
            }
        }

        // Reproduction: sample alleles from living individuals
        const living = this.popIndividuals.filter(i => i.alive);
        if (living.length < 4) {
            this.popRunning = false;
            if (this.info) this.info.textContent = '\u79cd\u7fa4\u706d\u7edd\uff01\u4e2a\u4f53\u6570\u8fc7\u5c11\u65e0\u6cd5\u7ee7\u7eed';
            return;
        }

        // Allele pool
        const alleles = [];
        for (const ind of living) {
            if (ind.genotype === 'AA') { alleles.push('A', 'A'); }
            else if (ind.genotype === 'Aa') { alleles.push('A', 'a'); }
            else { alleles.push('a', 'a'); }
        }

        // Genetic drift: if popDrift or small population, sample with replacement
        const nextGen = [];
        const targetSize = this.popDrift ? Math.min(living.length, 50) : this.popSize;
        for (let i = 0; i < targetSize; i++) {
            const a1 = alleles[Math.floor(Math.random() * alleles.length)];
            const a2 = alleles[Math.floor(Math.random() * alleles.length)];
            let g;
            if (a1 === 'A' && a2 === 'A') g = 'AA';
            else if (a1 === 'a' && a2 === 'a') g = 'aa';
            else g = 'Aa';

            // Mutation (low rate)
            if (this.popMutation && Math.random() < 0.01) {
                if (g === 'AA') g = 'Aa';
                else if (g === 'aa') g = 'Aa';
            }

            nextGen.push({
                genotype: g,
                x: Math.random() * this.W * 0.55 + this.W * 0.02,
                y: Math.random() * this.H * 0.65 + this.H * 0.05,
                vx: (Math.random() - 0.5) * 0.8,
                vy: (Math.random() - 0.5) * 0.8,
                alive: true
            });
        }

        this.popIndividuals = nextGen;
        this.popGenerations++;

        // Calculate frequencies
        let countA = 0, total = 0;
        for (const ind of nextGen) {
            if (ind.genotype === 'AA') countA += 2;
            else if (ind.genotype === 'Aa') countA += 1;
            total += 2;
        }
        const newP = countA / total;
        const newQ = 1 - newP;
        const AA = nextGen.filter(i => i.genotype === 'AA').length / nextGen.length;
        const Aa = nextGen.filter(i => i.genotype === 'Aa').length / nextGen.length;
        const aa = nextGen.filter(i => i.genotype === 'aa').length / nextGen.length;
        this.popHistory.push({ p: newP, q: newQ, AA, Aa, aa });

        if (this.info) {
            this.info.innerHTML = '<strong>\u7b2c ' + this.popGenerations + ' \u4ee3</strong> | p=' + newP.toFixed(3)
                + ' q=' + newQ.toFixed(3) + ' | AA:' + (AA * 100).toFixed(1) + '% Aa:'
                + (Aa * 100).toFixed(1) + '% aa:' + (aa * 100).toFixed(1) + '%'
                + ' | \u4e2a\u4f53\u6570:' + nextGen.length;
        }
    },

    /* ============ Pedigree Chart ============ */

    buildPedigree() {
        const presets = {
            autosomal_dominant: {
                title: '\u5e38\u67d3\u8272\u4f53\u663e\u6027\u9057\u4f20',
                desc: '\u60a3\u8005\u81f3\u5c11\u643a\u5e26\u4e00\u4e2a\u663e\u6027\u7b49\u4f4d\u57fa\u56e0(A)\uff0c\u60a3\u75c5\u8868\u73b0\u4e3a Aa \u6216 AA',
                nodes: [
                    { id: 0, sex: 'M', genotype: 'Aa', affected: true, gen: 0, pos: 0 },
                    { id: 1, sex: 'F', genotype: 'aa', affected: false, gen: 0, pos: 1 },
                    { id: 2, sex: 'M', genotype: 'Aa', affected: true, gen: 1, pos: 0 },
                    { id: 3, sex: 'F', genotype: 'aa', affected: false, gen: 1, pos: 1 },
                    { id: 4, sex: 'M', genotype: 'aa', affected: false, gen: 1, pos: 2 },
                    { id: 5, sex: 'F', genotype: 'Aa', affected: true, gen: 1, pos: 3 },
                    { id: 6, sex: 'M', genotype: 'Aa', affected: true, gen: 2, pos: 0 },
                    { id: 7, sex: 'F', genotype: 'aa', affected: false, gen: 2, pos: 1 },
                    { id: 8, sex: 'M', genotype: 'aa', affected: false, gen: 2, pos: 2 },
                    { id: 9, sex: 'F', genotype: 'aa', affected: false, gen: 2, pos: 3 }
                ],
                unions: [[0,1],[4,5]],
                children: { '0-1': [2,3,4,5], '4-5': [6,7,8,9] }
            },
            autosomal_recessive: {
                title: '\u5e38\u67d3\u8272\u4f53\u9690\u6027\u9057\u4f20',
                desc: '\u60a3\u8005\u57fa\u56e0\u578b\u4e3a aa\uff0c\u7236\u6bcd\u5747\u4e3a\u643a\u5e26\u8005(Aa)',
                nodes: [
                    { id: 0, sex: 'M', genotype: 'Aa', affected: false, gen: 0, pos: 0 },
                    { id: 1, sex: 'F', genotype: 'Aa', affected: false, gen: 0, pos: 1 },
                    { id: 2, sex: 'F', genotype: 'AA', affected: false, gen: 1, pos: 0 },
                    { id: 3, sex: 'M', genotype: 'Aa', affected: false, gen: 1, pos: 1 },
                    { id: 4, sex: 'F', genotype: 'aa', affected: true, gen: 1, pos: 2 },
                    { id: 5, sex: 'M', genotype: 'Aa', affected: false, gen: 1, pos: 3 }
                ],
                unions: [[0,1]],
                children: { '0-1': [2,3,4,5] }
            },
            x_linked_recessive: {
                title: 'X\u8fde\u9501\u9690\u6027\u9057\u4f20',
                desc: '\u7537\u6027\u60a3\u8005\u57fa\u56e0\u578b X\u1d43Y\uff0c\u5973\u6027\u643a\u5e26\u8005 X\u1d2cX\u1d43',
                nodes: [
                    { id: 0, sex: 'M', genotype: 'XAY', affected: false, gen: 0, pos: 0 },
                    { id: 1, sex: 'F', genotype: 'XAXa', affected: false, gen: 0, pos: 1 },
                    { id: 2, sex: 'M', genotype: 'XAY', affected: false, gen: 1, pos: 0 },
                    { id: 3, sex: 'F', genotype: 'XAXa', affected: false, gen: 1, pos: 1 },
                    { id: 4, sex: 'M', genotype: 'XaY', affected: true, gen: 1, pos: 2 },
                    { id: 5, sex: 'F', genotype: 'XAXA', affected: false, gen: 1, pos: 3 }
                ],
                unions: [[0,1]],
                children: { '0-1': [2,3,4,5] }
            },
            x_linked_dominant: {
                title: 'X\u8fde\u9501\u663e\u6027\u9057\u4f20',
                desc: '\u7537\u6027\u60a3\u8005\u7684\u5973\u513f\u5168\u90e8\u60a3\u75c5\uff0c\u5973\u6027\u60a3\u8005\u540e\u4ee3\u534a\u6570\u60a3\u75c5',
                nodes: [
                    { id: 0, sex: 'M', genotype: 'XAY', affected: true, gen: 0, pos: 0 },
                    { id: 1, sex: 'F', genotype: 'XaXa', affected: false, gen: 0, pos: 1 },
                    { id: 2, sex: 'F', genotype: 'XAXa', affected: true, gen: 1, pos: 0 },
                    { id: 3, sex: 'M', genotype: 'XaY', affected: false, gen: 1, pos: 1 },
                    { id: 4, sex: 'F', genotype: 'XAXa', affected: true, gen: 1, pos: 2 },
                    { id: 5, sex: 'M', genotype: 'XaY', affected: false, gen: 1, pos: 3 }
                ],
                unions: [[0,1]],
                children: { '0-1': [2,3,4,5] }
            }
        };

        const preset = presets[this.pedigreePreset] || presets.autosomal_dominant;
        this.pedigreeData = preset;
        this._selectedPedigreeNode = null;

        if (this.info) {
            this.info.innerHTML = '<strong>' + preset.title + '</strong>\uff1a' + preset.desc;
        }
    },

    _pedigreeClick(mx, my) {
        if (!this.pedigreeData) return;
        const nodes = this.pedigreeData.nodes;
        const { W, H } = this;
        const genCount = Math.max(...nodes.map(n => n.gen)) + 1;
        const genH = H / (genCount + 1);
        const r = 18;

        for (const node of nodes) {
            const maxPos = Math.max(...nodes.filter(n => n.gen === node.gen).map(n => n.pos)) + 1;
            const colW = W * 0.7 / maxPos;
            const nx = W * 0.15 + colW * (node.pos + 0.5);
            const ny = genH * (node.gen + 1);

            if (Math.abs(mx - nx) < r + 4 && Math.abs(my - ny) < r + 4) {
                this._selectedPedigreeNode = node;
                if (this.info) {
                    const sexLabel = node.sex === 'M' ? '\u7537\u6027' : '\u5973\u6027';
                    const statusLabel = node.affected ? '\u60a3\u75c5' : '\u6b63\u5e38';
                    this.info.innerHTML = '<strong>' + sexLabel + ' (ID:' + node.id + ')</strong> | \u57fa\u56e0\u578b: '
                        + node.genotype + ' | \u72b6\u6001: ' + statusLabel;
                }
                return;
            }
        }
        this._selectedPedigreeNode = null;
    },

    /* ============ Main Draw ============ */

    draw() {
        const { ctx, W, H, mode } = this;
        if (!ctx || W === 0) return;
        ctx.clearRect(0, 0, W, H);

        switch (mode) {
            case 'punnett':    this._drawPunnett(ctx, W, H); break;
            case 'population': this._drawPopulation(ctx, W, H); break;
            case 'pedigree':   this._drawPedigree(ctx, W, H); break;
        }
    },

    /* ── Punnett Draw ── */

    _drawPunnett(ctx, W, H) {
        if (!this.crossResult) {
            // Placeholder
            ctx.fillStyle = 'rgba(58,158,143,0.08)';
            ctx.fillRect(0, 0, W, H);
            ctx.fillStyle = 'rgba(255,255,255,0.3)';
            ctx.font = '500 14px "Noto Sans SC", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('\u9009\u62e9\u4eb2\u672c\u57fa\u56e0\u578b\uff0c\u70b9\u51fb\u201c\u6742\u4ea4\u201d\u67e5\u770b\u7ed3\u679c', W / 2, H / 2);
            return;
        }

        const { g1, g2, grid, counts, total } = this.crossResult;
        const cols = g2.length, rows = g1.length;
        const isSingle = this.punnettMode === 'single';
        const cellSize = Math.min((W * 0.5) / (cols + 1), (H * 0.55) / (rows + 1), 80);
        const gridW = (cols + 1) * cellSize;
        const gridH = (rows + 1) * cellSize;
        const ox = (W * 0.55 - gridW) / 2 + cellSize;
        const oy = (H * 0.55 - gridH) / 2 + cellSize + 30;

        const animPhase = this.crossAnim ? this.crossAnim.phase : 'done';
        const animT = this.crossAnim ? this.crossAnim.t : 1;

        // Title
        ctx.fillStyle = 'rgba(58,158,143,0.7)';
        ctx.font = 'bold 13px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(isSingle ? '\u5355\u57fa\u56e0\u6742\u4ea4' : '\u53cc\u57fa\u56e0\u6742\u4ea4', W * 0.27, 20);

        // Parent labels
        ctx.fillStyle = 'rgba(58,158,143,0.6)';
        ctx.font = '600 12px "JetBrains Mono", monospace';
        ctx.textAlign = 'center';
        ctx.fillText('\u2640 ' + this.parent2, ox + gridW / 2 - cellSize / 2, oy - cellSize - 6);
        ctx.save();
        ctx.translate(ox - cellSize - 6, oy + gridH / 2 - cellSize / 2);
        ctx.rotate(-Math.PI / 2);
        ctx.fillText('\u2642 ' + this.parent1, 0, 0);
        ctx.restore();

        // Header row (gametes of parent2)
        for (let c = 0; c < cols; c++) {
            const x = ox + c * cellSize, y = oy - cellSize;
            ctx.fillStyle = 'rgba(58,158,143,0.12)';
            ctx.fillRect(x, y, cellSize - 2, cellSize - 2);
            ctx.fillStyle = '#3a9e8f';
            ctx.font = '600 13px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(g2[c], x + cellSize / 2 - 1, y + cellSize / 2 + 4);
        }

        // Header col (gametes of parent1)
        for (let r = 0; r < rows; r++) {
            const x = ox - cellSize, y = oy + r * cellSize;
            ctx.fillStyle = 'rgba(58,158,143,0.12)';
            ctx.fillRect(x, y, cellSize - 2, cellSize - 2);
            ctx.fillStyle = '#3a9e8f';
            ctx.font = '600 13px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(g1[r], x + cellSize / 2 - 1, y + cellSize / 2 + 4);
        }

        // Grid cells
        let idx = 0;
        for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
                const x = ox + c * cellSize, y = oy + r * cellSize;
                const genotype = grid[idx];
                const type = this._genotypeType(genotype);

                // Animation: fade in
                let alpha = 1;
                if (animPhase === 'gamete') alpha = 0;
                else if (animPhase === 'combine') alpha = Math.min(1, animT / 1.2);

                const colors = {
                    dominant: 'rgba(58,158,143,0.2)',
                    carrier: 'rgba(139,111,192,0.15)',
                    recessive: 'rgba(196,121,58,0.15)'
                };

                ctx.globalAlpha = alpha;
                ctx.fillStyle = colors[type] || colors.carrier;
                ctx.fillRect(x, y, cellSize - 2, cellSize - 2);
                ctx.strokeStyle = 'rgba(255,255,255,0.08)';
                ctx.lineWidth = 1;
                ctx.strokeRect(x, y, cellSize - 2, cellSize - 2);

                ctx.fillStyle = '#fff';
                ctx.font = '600 ' + Math.min(14, cellSize * 0.28) + 'px "JetBrains Mono", monospace';
                ctx.textAlign = 'center';
                ctx.fillText(genotype, x + cellSize / 2 - 1, y + cellSize / 2 + 4);
                ctx.globalAlpha = 1;

                idx++;
            }
        }

        // ── Statistics bar chart (right side) ──
        this._drawPunnettStats(ctx, W, H, counts, total);
    },

    _drawPunnettStats(ctx, W, H, counts, total) {
        const entries = Object.entries(counts).sort();
        const barArea = { x: W * 0.6, y: 50, w: W * 0.35, h: H * 0.55 };
        const barW = Math.min(barArea.w / (entries.length * 1.8), 50);
        const gap = barW * 0.6;
        const totalW = entries.length * barW + (entries.length - 1) * gap;
        const startX = barArea.x + (barArea.w - totalW) / 2;

        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '500 11px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('\u540e\u4ee3\u7edf\u8ba1', barArea.x + barArea.w / 2, barArea.y - 6);

        const maxCount = Math.max(...entries.map(e => e[1]));
        const maxBarH = barArea.h - 40;

        entries.forEach(([g, count], i) => {
            const x = startX + i * (barW + gap);
            const ratio = count / total;
            const barH = (count / maxCount) * maxBarH;
            const type = this._genotypeType(g);

            const colors = {
                dominant: '#3a9e8f',
                carrier: '#8b6fc0',
                recessive: '#c4793a'
            };
            const color = colors[type] || '#3a9e8f';

            // Bar
            ctx.fillStyle = color + '44';
            ctx.fillRect(x, barArea.y + maxBarH - barH + 20, barW, barH);
            ctx.strokeStyle = color;
            ctx.lineWidth = 1.5;
            ctx.strokeRect(x, barArea.y + maxBarH - barH + 20, barW, barH);

            // Genotype label
            ctx.fillStyle = color;
            ctx.font = '600 11px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillText(g, x + barW / 2, barArea.y + maxBarH + 36);

            // Percentage
            ctx.fillStyle = 'rgba(255,255,255,0.6)';
            ctx.font = '500 10px "JetBrains Mono", monospace';
            ctx.fillText((ratio * 100).toFixed(1) + '%', x + barW / 2, barArea.y + maxBarH - barH + 14);
        });

        // Legend
        const legendY = barArea.y + barArea.h + 30;
        const legendItems = [
            ['\u663e\u6027\u7eaf\u5408', '#3a9e8f'],
            ['\u6742\u5408', '#8b6fc0'],
            ['\u9690\u6027\u7eaf\u5408', '#c4793a']
        ];
        let lx = barArea.x;
        for (const [label, color] of legendItems) {
            ctx.fillStyle = color;
            ctx.fillRect(lx, legendY, 10, 10);
            ctx.fillStyle = 'rgba(255,255,255,0.5)';
            ctx.font = '10px "Noto Sans SC", sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(label, lx + 14, legendY + 9);
            lx += 70;
        }

        // Edu panel (bottom)
        this._drawPunnettEdu(ctx, W, H);
    },

    _drawPunnettEdu(ctx, W, H) {
        const y0 = H * 0.72;
        ctx.fillStyle = 'rgba(58,158,143,0.06)';
        ctx.fillRect(8, y0, W - 16, H - y0 - 8);
        ctx.strokeStyle = 'rgba(58,158,143,0.15)';
        ctx.lineWidth = 1;
        ctx.strokeRect(8, y0, W - 16, H - y0 - 8);

        ctx.fillStyle = 'rgba(58,158,143,0.6)';
        ctx.font = '600 11px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('\u77e5\u8bc6\u8865\u5145', 18, y0 + 16);

        ctx.fillStyle = 'rgba(255,255,255,0.45)';
        ctx.font = '11px "Noto Sans SC", sans-serif';

        const lines = this.punnettMode === 'single' ? [
            '\u2022 \u5206\u79bb\u5b9a\u5f8b\uff1a\u7b49\u4f4d\u57fa\u56e0\u5728\u5f62\u6210\u914d\u5b50\u65f6\u5f7c\u6b64\u5206\u79bb\uff0c\u5206\u522b\u8fdb\u5165\u4e0d\u540c\u914d\u5b50\u4e2d',
            '\u2022 Aa \u00d7 Aa \u2192 AA:Aa:aa = 1:2:1\uff0c\u8868\u73b0\u578b\u6bd4 3:1',
            '\u2022 \u663e\u6027\u7eaf\u5408(AA)\u4e0e\u6742\u5408(Aa)\u8868\u73b0\u578b\u76f8\u540c\uff0c\u9700\u6d4b\u4ea4\u9274\u5b9a'
        ] : [
            '\u2022 \u81ea\u7531\u7ec4\u5408\u5b9a\u5f8b\uff1a\u975e\u540c\u6e90\u67d3\u8272\u4f53\u4e0a\u7684\u57fa\u56e0\u81ea\u7531\u7ec4\u5408',
            '\u2022 AaBb \u00d7 AaBb \u2192 9:3:3:1 \u8868\u73b0\u578b\u6bd4',
            '\u2022 16\u79cd\u914d\u5b50\u7ec4\u5408\uff0c\u4ea7\u751f 9 \u79cd\u57fa\u56e0\u578b'
        ];
        lines.forEach((line, i) => {
            ctx.fillText(line, 18, y0 + 34 + i * 18);
        });
    },

    /* ── Population Draw ── */

    _drawPopulation(ctx, W, H) {
        // Draw individuals
        const genoColors = { AA: '#3a9e8f', Aa: '#8b6fc0', aa: '#c4793a' };

        for (const ind of this.popIndividuals) {
            if (!ind.alive) continue;
            ctx.beginPath();
            ctx.arc(ind.x, ind.y, 3.5, 0, Math.PI * 2);
            ctx.fillStyle = genoColors[ind.genotype] || '#fff';
            ctx.fill();
        }

        // Draw allele frequency history (right panel)
        this._drawPopGraph(ctx, W, H);

        // Draw legend + stats at bottom
        this._drawPopEdu(ctx, W, H);
    },

    _drawPopGraph(ctx, W, H) {
        const gx = W * 0.6, gy = 20, gw = W * 0.36, gh = H * 0.45;

        ctx.fillStyle = 'rgba(255,255,255,0.04)';
        ctx.fillRect(gx, gy, gw, gh);
        ctx.strokeStyle = 'rgba(255,255,255,0.1)';
        ctx.lineWidth = 1;
        ctx.strokeRect(gx, gy, gw, gh);

        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.font = '500 10px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('\u7b49\u4f4d\u57fa\u56e0\u9891\u7387\u53d8\u5316', gx + gw / 2, gy - 4);

        // Axes
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.beginPath();
        ctx.moveTo(gx, gy + gh); ctx.lineTo(gx + gw, gy + gh); // x
        ctx.moveTo(gx, gy); ctx.lineTo(gx, gy + gh); // y
        ctx.stroke();

        // Y labels (0, 0.5, 1)
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '9px "JetBrains Mono", monospace';
        ctx.textAlign = 'right';
        ctx.fillText('1.0', gx - 3, gy + 4);
        ctx.fillText('0.5', gx - 3, gy + gh / 2 + 3);
        ctx.fillText('0.0', gx - 3, gy + gh + 3);

        if (this.popHistory.length < 2) return;

        // Plot p (dominant allele) in teal
        const len = this.popHistory.length;
        const dx = gw / Math.max(len - 1, 1);

        ctx.strokeStyle = '#3a9e8f'; ctx.lineWidth = 1.5;
        ctx.beginPath();
        this.popHistory.forEach((h, i) => {
            const x = gx + i * dx;
            const y = gy + gh - h.p * gh;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Plot q (recessive allele) in orange
        ctx.strokeStyle = '#c4793a'; ctx.lineWidth = 1.5;
        ctx.beginPath();
        this.popHistory.forEach((h, i) => {
            const x = gx + i * dx;
            const y = gy + gh - h.q * gh;
            i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Graph legend
        const ly = gy + gh + 14;
        ctx.fillStyle = '#3a9e8f';
        ctx.fillRect(gx + 10, ly, 12, 3);
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.font = '9px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('p (A)', gx + 26, ly + 4);

        ctx.fillStyle = '#c4793a';
        ctx.fillRect(gx + 70, ly, 12, 3);
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.fillText('q (a)', gx + 86, ly + 4);
    },

    _drawPopEdu(ctx, W, H) {
        const y0 = H * 0.72;
        ctx.fillStyle = 'rgba(58,158,143,0.06)';
        ctx.fillRect(8, y0, W - 16, H - y0 - 8);
        ctx.strokeStyle = 'rgba(58,158,143,0.15)';
        ctx.lineWidth = 1;
        ctx.strokeRect(8, y0, W - 16, H - y0 - 8);

        ctx.fillStyle = 'rgba(58,158,143,0.6)';
        ctx.font = '600 11px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('Hardy-Weinberg \u5b9a\u5f8b', 18, y0 + 16);

        ctx.fillStyle = 'rgba(255,255,255,0.45)';
        ctx.font = '11px "Noto Sans SC", sans-serif';
        const lines = [
            '\u2022 p\u00b2 + 2pq + q\u00b2 = 1\uff0c\u5176\u4e2d p=\u663e\u6027\u7b49\u4f4d\u57fa\u56e0\u9891\u7387\uff0cq=\u9690\u6027\u7b49\u4f4d\u57fa\u56e0\u9891\u7387',
            '\u2022 \u5e73\u8861\u6761\u4ef6\uff1a\u5927\u79cd\u7fa4\u3001\u968f\u673a\u4ea4\u914d\u3001\u65e0\u9009\u62e9/\u7a81\u53d8/\u8fc1\u79fb',
            '\u2022 \u5f00\u542f\u201c\u81ea\u7136\u9009\u62e9\u201d\u89c2\u5bdf\u57fa\u56e0\u9891\u7387\u504f\u79bb\u5e73\u8861\u7684\u8fc7\u7a0b'
        ];
        lines.forEach((line, i) => {
            ctx.fillText(line, 18, y0 + 34 + i * 18);
        });

        // Genotype frequency bar (bottom strip)
        if (this.popHistory.length > 0) {
            const last = this.popHistory[this.popHistory.length - 1];
            const barY = y0 + 90, barH = 10, barW = W - 40;
            const bx = 20;

            ctx.fillStyle = '#3a9e8f';
            ctx.fillRect(bx, barY, barW * last.AA, barH);
            ctx.fillStyle = '#8b6fc0';
            ctx.fillRect(bx + barW * last.AA, barY, barW * last.Aa, barH);
            ctx.fillStyle = '#c4793a';
            ctx.fillRect(bx + barW * (last.AA + last.Aa), barY, barW * last.aa, barH);

            ctx.font = '9px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.fillStyle = 'rgba(255,255,255,0.5)';
            ctx.fillText('AA ' + (last.AA * 100).toFixed(1) + '%', bx + barW * last.AA / 2, barY + barH + 12);
            ctx.fillText('Aa ' + (last.Aa * 100).toFixed(1) + '%', bx + barW * (last.AA + last.Aa / 2), barY + barH + 12);
            ctx.fillText('aa ' + (last.aa * 100).toFixed(1) + '%', bx + barW * (last.AA + last.Aa + last.aa / 2), barY + barH + 12);
        }
    },

    /* ── Pedigree Draw ── */

    _drawPedigree(ctx, W, H) {
        if (!this.pedigreeData) {
            ctx.fillStyle = 'rgba(255,255,255,0.3)';
            ctx.font = '14px "Noto Sans SC", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('\u9009\u62e9\u9057\u4f20\u65b9\u5f0f\u67e5\u770b\u7cfb\u8c31\u56fe', W / 2, H / 2);
            return;
        }

        const { nodes, unions, children, title } = this.pedigreeData;
        const genCount = Math.max(...nodes.map(n => n.gen)) + 1;
        const genH = (H * 0.65) / (genCount + 0.5);
        const r = 18;

        // Title
        ctx.fillStyle = 'rgba(58,158,143,0.6)';
        ctx.font = 'bold 13px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(title, W / 2, 22);

        // Compute positions
        const positions = {};
        for (const node of nodes) {
            const sameGen = nodes.filter(n => n.gen === node.gen);
            const maxPos = Math.max(...sameGen.map(n => n.pos)) + 1;
            const colW = W * 0.7 / maxPos;
            positions[node.id] = {
                x: W * 0.15 + colW * (node.pos + 0.5),
                y: genH * (node.gen + 1) + 20
            };
        }

        // Draw union lines
        ctx.strokeStyle = 'rgba(255,255,255,0.2)';
        ctx.lineWidth = 1.5;
        for (const [id1, id2] of unions) {
            const p1 = positions[id1], p2 = positions[id2];
            ctx.beginPath();
            ctx.moveTo(p1.x + r + 2, p1.y);
            ctx.lineTo(p2.x - r - 2, p2.y);
            ctx.stroke();
        }

        // Draw parent-child lines
        for (const [key, childIds] of Object.entries(children)) {
            const [pid1, pid2] = key.split('-').map(Number);
            const pp1 = positions[pid1], pp2 = positions[pid2];
            const midX = (pp1.x + pp2.x) / 2;
            const midY = pp1.y;

            // Vertical line down from union
            const childY = positions[childIds[0]].y;
            const lineY = midY + r + 5;
            const childLineY = childY - r - 5;
            const branchY = (lineY + childLineY) / 2;

            ctx.strokeStyle = 'rgba(255,255,255,0.15)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(midX, lineY);
            ctx.lineTo(midX, branchY);
            ctx.stroke();

            // Horizontal line across children
            const childXs = childIds.map(id => positions[id].x);
            const minCX = Math.min(...childXs), maxCX = Math.max(...childXs);
            ctx.beginPath();
            ctx.moveTo(minCX, branchY);
            ctx.lineTo(maxCX, branchY);
            ctx.stroke();

            // Vertical lines to each child
            for (const cid of childIds) {
                const cp = positions[cid];
                ctx.beginPath();
                ctx.moveTo(cp.x, branchY);
                ctx.lineTo(cp.x, childLineY);
                ctx.stroke();
            }
        }

        // Draw nodes
        for (const node of nodes) {
            const { x, y } = positions[node.id];
            const selected = this._selectedPedigreeNode === node;

            if (node.sex === 'M') {
                // Male = square
                ctx.fillStyle = node.affected ? '#3a9e8f' : 'rgba(255,255,255,0.04)';
                ctx.fillRect(x - r, y - r, r * 2, r * 2);
                ctx.strokeStyle = selected ? '#fff' : 'rgba(58,158,143,0.5)';
                ctx.lineWidth = selected ? 2.5 : 1.5;
                ctx.strokeRect(x - r, y - r, r * 2, r * 2);
            } else {
                // Female = circle
                ctx.beginPath();
                ctx.arc(x, y, r, 0, Math.PI * 2);
                ctx.fillStyle = node.affected ? '#3a9e8f' : 'rgba(255,255,255,0.04)';
                ctx.fill();
                ctx.strokeStyle = selected ? '#fff' : 'rgba(58,158,143,0.5)';
                ctx.lineWidth = selected ? 2.5 : 1.5;
                ctx.stroke();
            }

            // Carrier dot (for autosomal recessive carriers)
            if (!node.affected && node.genotype.includes('a') && !node.genotype.startsWith('aa')) {
                ctx.beginPath();
                ctx.arc(x, y, 4, 0, Math.PI * 2);
                ctx.fillStyle = 'rgba(58,158,143,0.5)';
                ctx.fill();
            }

            // Generation label
            if (node.pos === 0) {
                ctx.fillStyle = 'rgba(255,255,255,0.2)';
                ctx.font = '10px "Noto Sans SC", sans-serif';
                ctx.textAlign = 'right';
                const genLabels = ['I', 'II', 'III', 'IV'];
                ctx.fillText(genLabels[node.gen] || '', W * 0.1, y + 4);
            }
        }

        // Legend
        const ly = H * 0.72;
        ctx.fillStyle = 'rgba(58,158,143,0.06)';
        ctx.fillRect(8, ly, W - 16, H - ly - 8);
        ctx.strokeStyle = 'rgba(58,158,143,0.15)';
        ctx.lineWidth = 1;
        ctx.strokeRect(8, ly, W - 16, H - ly - 8);

        ctx.fillStyle = 'rgba(58,158,143,0.6)';
        ctx.font = '600 11px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('\u7cfb\u8c31\u56fe\u56fe\u4f8b', 18, ly + 16);

        // Legend items
        const items = [
            { draw: (x, y) => { ctx.strokeStyle = 'rgba(58,158,143,0.5)'; ctx.lineWidth = 1.5; ctx.strokeRect(x, y - 7, 14, 14); }, label: '\u6b63\u5e38\u7537\u6027' },
            { draw: (x, y) => { ctx.beginPath(); ctx.arc(x + 7, y, 7, 0, Math.PI * 2); ctx.strokeStyle = 'rgba(58,158,143,0.5)'; ctx.lineWidth = 1.5; ctx.stroke(); }, label: '\u6b63\u5e38\u5973\u6027' },
            { draw: (x, y) => { ctx.fillStyle = '#3a9e8f'; ctx.fillRect(x, y - 7, 14, 14); }, label: '\u60a3\u75c5\u7537\u6027' },
            { draw: (x, y) => { ctx.beginPath(); ctx.arc(x + 7, y, 7, 0, Math.PI * 2); ctx.fillStyle = '#3a9e8f'; ctx.fill(); }, label: '\u60a3\u75c5\u5973\u6027' },
            { draw: (x, y) => { ctx.beginPath(); ctx.arc(x + 7, y, 3, 0, Math.PI * 2); ctx.fillStyle = 'rgba(58,158,143,0.5)'; ctx.fill(); }, label: '\u643a\u5e26\u8005' }
        ];

        let lx = 18;
        items.forEach(item => {
            item.draw(lx, ly + 38);
            ctx.fillStyle = 'rgba(255,255,255,0.45)';
            ctx.font = '10px "Noto Sans SC", sans-serif';
            ctx.textAlign = 'left';
            ctx.fillText(item.label, lx + 18, ly + 42);
            lx += 80;
        });

        // Edu info
        ctx.fillStyle = 'rgba(255,255,255,0.35)';
        ctx.font = '10px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'left';
        ctx.fillText('\u70b9\u51fb\u4e2a\u4f53\u67e5\u770b\u57fa\u56e0\u578b\u4fe1\u606f\uff0c\u9009\u62e9\u4e0d\u540c\u9057\u4f20\u65b9\u5f0f\u89c2\u5bdf\u7cfb\u8c31\u56fe\u7279\u5f81', 18, ly + 60);
    }
};

function initGenetics() {
    Genetics.init();
}
// ===== Inequality & Linear Programming Visualization =====
// Feasible region, objective function optimization

const Inequality = {
    canvas: null, ctx: null, W: 0, H: 0,
    _listeners: [],
    _resizeObs: null,

    scale: 30, // px per unit
    origin: { x: 40, y: 0 },

    // Constraints: ax + by <= c  (or >=, =)
    constraints: [
        { a: 1, b: 1, op: '<=', c: 8, color: '#5b8dce' },
        { a: 2, b: 1, op: '<=', c: 12, color: '#c678dd' },
        { a: 0, b: 1, op: '<=', c: 5, color: '#e5c07b' }
    ],
    // x >= 0, y >= 0 implicit

    objectiveC: [3, 2], // maximize 3x + 2y
    showObjective: true,
    objSlider: 0,

    _on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts);
        this._listeners.push({ el, evt, fn, opts });
    },

    init() {
        this.canvas = document.getElementById('ineq-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        this.bindEvents();
        this.draw();
    },

    destroy() {
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
        const h = Math.min(w * 0.7, 480);
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w;
        this.H = h;
        this.origin = { x: 40, y: h - 40 };
    },

    bindEvents() {
        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => { this.resize(); this.draw(); });
            this._resizeObs.observe(this.canvas.parentElement);
        }

        // Constraint sliders
        for (let i = 0; i < 3; i++) {
            const el = document.getElementById('ineq-c' + i);
            if (el) this._on(el, 'input', () => {
                this.constraints[i].c = parseFloat(el.value);
                this.draw();
                this.updateInfo();
            });
        }

        // Objective slider
        const objS = document.getElementById('ineq-obj');
        if (objS) this._on(objS, 'input', () => {
            this.objSlider = parseFloat(objS.value);
            this.draw();
        });

        // Toggle objective
        const chk = document.getElementById('ineq-show-obj');
        if (chk) this._on(chk, 'change', () => {
            this.showObjective = chk.checked;
            this.draw();
        });
    },

    worldToScreen(wx, wy) {
        return {
            x: this.origin.x + wx * this.scale,
            y: this.origin.y - wy * this.scale
        };
    },

    draw() {
        const { ctx, W, H } = this;
        if (!ctx || W === 0) return;
        ctx.clearRect(0, 0, W, H);

        this.drawGrid();
        this.drawFeasibleRegion();
        this.drawConstraintLines();
        if (this.showObjective) this.drawObjective();
        this.drawVertices();
        this.updateInfo();
    },

    drawGrid() {
        const { ctx, W, H, origin, scale } = this;
        ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 0.5;
        for (let x = origin.x; x < W; x += scale) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, H); ctx.stroke();
        }
        for (let y = origin.y; y > 0; y -= scale) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
        }

        // Axes
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(origin.x, 0); ctx.lineTo(origin.x, H); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(0, origin.y); ctx.lineTo(W, origin.y); ctx.stroke();

        // Labels
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '10px var(--font-sans)';
        ctx.textAlign = 'center';
        for (let i = 2; i <= 14; i += 2) {
            const p = this.worldToScreen(i, 0);
            if (p.x < W - 10) ctx.fillText(i, p.x, p.y + 14);
        }
        ctx.textAlign = 'right';
        for (let i = 2; i <= 10; i += 2) {
            const p = this.worldToScreen(0, i);
            if (p.y > 10) ctx.fillText(i, p.x - 6, p.y + 4);
        }
        ctx.fillText('x', W - 10, origin.y + 14);
        const top = this.worldToScreen(0, (H - 10) / scale);
        ctx.textAlign = 'left';
        ctx.fillText('y', origin.x + 6, 14);
    },

    getVertices() {
        // Compute all intersection points of constraint boundaries + axes
        const lines = [];
        this.constraints.forEach(c => lines.push(c));
        // x=0, y=0
        lines.push({ a: 1, b: 0, op: '>=', c: 0 }); // x >= 0
        lines.push({ a: 0, b: 1, op: '>=', c: 0 }); // y >= 0

        const pts = [];
        for (let i = 0; i < lines.length; i++) {
            for (let j = i + 1; j < lines.length; j++) {
                const l1 = lines[i], l2 = lines[j];
                const det = l1.a * l2.b - l2.a * l1.b;
                if (Math.abs(det) < 1e-10) continue;
                const x = (l1.c * l2.b - l2.c * l1.b) / det;
                const y = (l1.a * l2.c - l2.a * l1.c) / det;
                if (x < -0.001 || y < -0.001) continue;
                // Check feasibility
                let feasible = true;
                for (const c of this.constraints) {
                    const val = c.a * x + c.b * y;
                    if (c.op === '<=' && val > c.c + 0.01) { feasible = false; break; }
                    if (c.op === '>=' && val < c.c - 0.01) { feasible = false; break; }
                }
                if (feasible) pts.push({ x, y });
            }
        }
        return pts;
    },

    drawFeasibleRegion() {
        const { ctx } = this;
        const pts = this.getVertices();
        if (pts.length < 3) return;

        // Sort by angle from centroid
        const cx = pts.reduce((s, p) => s + p.x, 0) / pts.length;
        const cy = pts.reduce((s, p) => s + p.y, 0) / pts.length;
        pts.sort((a, b) => Math.atan2(a.y - cy, a.x - cx) - Math.atan2(b.y - cy, b.x - cx));

        ctx.fillStyle = 'rgba(91,141,206,0.1)';
        ctx.beginPath();
        pts.forEach((p, i) => {
            const s = this.worldToScreen(p.x, p.y);
            if (i === 0) ctx.moveTo(s.x, s.y);
            else ctx.lineTo(s.x, s.y);
        });
        ctx.closePath();
        ctx.fill();
    },

    drawConstraintLines() {
        const { ctx, W, H, scale } = this;
        const maxX = (W - this.origin.x) / scale + 1;
        const maxY = this.origin.y / scale + 1;

        this.constraints.forEach((c, i) => {
            ctx.strokeStyle = c.color;
            ctx.lineWidth = 1.5;
            ctx.beginPath();

            if (Math.abs(c.b) < 1e-10) {
                // Vertical line: ax = c -> x = c/a
                const x = c.c / c.a;
                const s1 = this.worldToScreen(x, 0);
                const s2 = this.worldToScreen(x, maxY);
                ctx.moveTo(s1.x, s1.y);
                ctx.lineTo(s2.x, s2.y);
            } else {
                // y = (c - ax) / b
                const y0 = c.c / c.b;
                const x0 = c.c / c.a;
                const s1 = this.worldToScreen(0, y0);
                const s2 = this.worldToScreen(x0, 0);
                ctx.moveTo(s1.x, s1.y);
                ctx.lineTo(s2.x, s2.y);
            }
            ctx.stroke();

            // Label
            let lx, ly;
            if (Math.abs(c.b) < 1e-10) {
                lx = c.c / c.a; ly = maxY * 0.7;
            } else {
                lx = 0.5; ly = (c.c - c.a * 0.5) / c.b;
            }
            const ls = this.worldToScreen(lx, ly);
            ctx.fillStyle = c.color;
            ctx.font = '11px var(--font-mono)';
            ctx.textAlign = 'left';
            const label = (c.a !== 0 ? (c.a === 1 ? 'x' : c.a + 'x') : '') +
                          (c.b !== 0 ? (c.a !== 0 ? '+' : '') + (c.b === 1 ? 'y' : c.b + 'y') : '') +
                          ' ' + c.op + ' ' + c.c;
            ctx.fillText(label, ls.x + 4, ls.y - 4);
        });
    },

    drawObjective() {
        const { ctx, W, scale } = this;
        const [cx, cy] = this.objectiveC;
        // z = cx*x + cy*y = k  =>  y = (k - cx*x) / cy
        // Draw line for z slider value and optimal
        const pts = this.getVertices();
        let maxZ = -Infinity, optPt = null;
        pts.forEach(p => {
            const z = cx * p.x + cy * p.y;
            if (z > maxZ) { maxZ = z; optPt = p; }
        });

        // Value line from slider
        const zRange = maxZ * 1.2;
        const z = this.objSlider * zRange;

        // y = (z - cx*x) / cy
        if (Math.abs(cy) > 0.001) {
            const maxX = (W - this.origin.x) / scale;
            const y0 = z / cy;
            const xEnd = z / cx;
            ctx.strokeStyle = 'rgba(152,195,121,0.4)';
            ctx.lineWidth = 1.5;
            ctx.setLineDash([5, 5]);
            ctx.beginPath();
            const s1 = this.worldToScreen(0, y0);
            const s2 = this.worldToScreen(xEnd, 0);
            ctx.moveTo(s1.x, s1.y);
            ctx.lineTo(s2.x, s2.y);
            ctx.stroke();
            ctx.setLineDash([]);

            // z label
            ctx.fillStyle = 'rgba(152,195,121,0.6)';
            ctx.font = '10px var(--font-mono)';
            ctx.textAlign = 'left';
            ctx.fillText('z=' + z.toFixed(1), s1.x + 4, s1.y - 4);
        }

        // Optimal point
        if (optPt) {
            const s = this.worldToScreen(optPt.x, optPt.y);
            ctx.fillStyle = '#98c379';
            ctx.beginPath();
            ctx.arc(s.x, s.y, 6, 0, Math.PI * 2);
            ctx.fill();
            ctx.fillStyle = '#98c379';
            ctx.font = 'bold 11px var(--font-mono)';
            ctx.textAlign = 'left';
            ctx.fillText('max z=' + maxZ.toFixed(1) + ' (' + optPt.x.toFixed(1) + ',' + optPt.y.toFixed(1) + ')', s.x + 10, s.y - 4);
        }
    },

    drawVertices() {
        const { ctx } = this;
        const pts = this.getVertices();
        pts.forEach(p => {
            const s = this.worldToScreen(p.x, p.y);
            ctx.fillStyle = 'rgba(255,255,255,0.3)';
            ctx.beginPath();
            ctx.arc(s.x, s.y, 3.5, 0, Math.PI * 2);
            ctx.fill();
        });
    },

    updateInfo() {
        const el = document.getElementById('ineq-info');
        if (!el) return;
        const pts = this.getVertices();
        const [cx, cy] = this.objectiveC;
        let maxZ = -Infinity, optPt = null;
        pts.forEach(p => {
            const z = cx * p.x + cy * p.y;
            if (z > maxZ) { maxZ = z; optPt = p; }
        });
        const vtxStr = pts.map(p => '(' + p.x.toFixed(1) + ',' + p.y.toFixed(1) + ')').join('  ');
        let text = '\u9876\u70b9: ' + vtxStr;
        if (optPt) {
            text += '    \u6700\u4f18\u89e3: (' + optPt.x.toFixed(1) + ',' + optPt.y.toFixed(1) + ')  z=' + maxZ.toFixed(1);
        }
        el.textContent = text;
    }
};

function initInequality() {
    Inequality.init();
}

window.Inequality = Inequality;
window.initInequality = initInequality;
// ===== 几何变换可视化 =====

const GeoTransform = {
    canvas: null,
    ctx: null,

    // Original shape — unit square centered at origin
    shape: [
        [-1, -1],
        [ 1, -1],
        [ 1,  1],
        [-1,  1]
    ],

    // Transform parameters
    tx: 0, ty: 0,       // translate
    angle: 0,            // rotate (degrees)
    sx: 1, sy: 1,        // scale
    shx: 0,              // shear X
    mirror: 'none',      // 'none' | 'x' | 'y'

    // Viewport
    viewRange: 6,        // -6 to 6

    // Animation
    animating: false,
    animId: null,
    animTime: 0,

    init() {
        this.canvas = document.getElementById('geo-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.bindControls();
        this.draw();
    },

    bindControls() {
        const sliders = {
            'geo-tx': (v) => { this.tx = v; },
            'geo-ty': (v) => { this.ty = v; },
            'geo-angle': (v) => { this.angle = v; },
            'geo-sx': (v) => { this.sx = v; },
            'geo-sy': (v) => { this.sy = v; },
            'geo-shx': (v) => { this.shx = v; }
        };

        for (const [id, setter] of Object.entries(sliders)) {
            const el = document.getElementById(id);
            if (el) {
                el.addEventListener('input', (e) => {
                    setter(parseFloat(e.target.value));
                    const lbl = document.getElementById(id + '-val');
                    if (lbl) lbl.textContent = parseFloat(e.target.value).toFixed(id === 'geo-angle' ? 0 : 2);
                    this.draw();
                });
            }
        }
    },

    getMatrix() {
        // Build full transformation matrix: Translate * Rotate * Scale * Shear * Mirror
        const rad = this.angle * Math.PI / 180;
        const cos = Math.cos(rad), sin = Math.sin(rad);

        // Mirror matrix
        let mx = 1, my = 1;
        if (this.mirror === 'x') my = -1;
        if (this.mirror === 'y') mx = -1;

        // Combined: T * R * S * Sh * M
        // Shear: [1, shx; 0, 1]
        // Scale: [sx, 0; 0, sy]
        // Mirror: [mx, 0; 0, my]
        // First apply mirror, then shear, then scale, then rotate, then translate
        // M_combined = T * R * S * Sh * Mirror

        // Step 1: Sh * Mirror
        const sm = [
            [mx + this.shx * 0, this.shx * my],
            [0, my]
        ];
        // Step 2: S * (Sh * Mirror)
        const ssm = [
            [this.sx * sm[0][0], this.sx * sm[0][1]],
            [this.sy * sm[1][0], this.sy * sm[1][1]]
        ];
        // Step 3: R * S * Sh * Mirror
        const rssm = [
            [cos * ssm[0][0] - sin * ssm[1][0], cos * ssm[0][1] - sin * ssm[1][1]],
            [sin * ssm[0][0] + cos * ssm[1][0], sin * ssm[0][1] + cos * ssm[1][1]]
        ];

        return {
            a: rssm[0][0], b: rssm[0][1],
            c: rssm[1][0], d: rssm[1][1],
            tx: this.tx, ty: this.ty
        };
    },

    transformPoint(pt, mat) {
        return [
            mat.a * pt[0] + mat.b * pt[1] + mat.tx,
            mat.c * pt[0] + mat.d * pt[1] + mat.ty
        ];
    },

    sizeCanvas() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.parentElement.getBoundingClientRect();
        const w = Math.round(rect.width);
        const h = Math.round(Math.max(w * 0.75, 300));
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        return { w, h };
    },

    mapX(x, w) { return ((x + this.viewRange) / (2 * this.viewRange)) * w; },
    mapY(y, h) { return ((this.viewRange - y) / (2 * this.viewRange)) * h; },

    draw() {
        if (!this.ctx) return;
        const { w, h } = this.sizeCanvas();
        const ctx = this.ctx;
        const vr = this.viewRange;

        // Background
        ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface-2').trim() || '#151822';
        ctx.fillRect(0, 0, w, h);

        // Grid
        ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 1;
        for (let g = -vr; g <= vr; g++) {
            const px = this.mapX(g, w);
            ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, h); ctx.stroke();
            const py = this.mapY(g, h);
            ctx.beginPath(); ctx.moveTo(0, py); ctx.lineTo(w, py); ctx.stroke();
        }

        // Axes
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 1.5;
        const ox = this.mapX(0, w), oy = this.mapY(0, h);
        ctx.beginPath(); ctx.moveTo(0, oy); ctx.lineTo(w, oy); ctx.stroke();
        ctx.beginPath(); ctx.moveTo(ox, 0); ctx.lineTo(ox, h); ctx.stroke();

        // Axis labels
        ctx.fillStyle = 'rgba(255,255,255,0.2)';
        ctx.font = '10px monospace';
        ctx.textAlign = 'center'; ctx.textBaseline = 'top';
        for (let g = -vr; g <= vr; g++) {
            if (g === 0) continue;
            ctx.fillText(g, this.mapX(g, w), oy + 3);
        }
        ctx.textAlign = 'right'; ctx.textBaseline = 'middle';
        for (let g = -vr; g <= vr; g++) {
            if (g === 0) continue;
            ctx.fillText(g, ox - 5, this.mapY(g, h));
        }

        // Draw original shape (ghost)
        this.drawShape(ctx, w, h, this.shape, 'rgba(91,141,206,0.15)', 'rgba(91,141,206,0.3)', true);

        // Draw transformed shape
        const mat = this.getMatrix();
        const transformed = this.shape.map(pt => this.transformPoint(pt, mat));
        this.drawShape(ctx, w, h, transformed, 'rgba(196,121,58,0.15)', '#c4793a', false);

        // Draw origin marker
        ctx.beginPath();
        ctx.arc(ox, oy, 4, 0, Math.PI * 2);
        ctx.fillStyle = 'rgba(255,255,255,0.4)';
        ctx.fill();

        // Draw transformation center
        const center = this.transformPoint([0, 0], mat);
        const cx = this.mapX(center[0], w), cy = this.mapY(center[1], h);
        ctx.beginPath();
        ctx.arc(cx, cy, 4, 0, Math.PI * 2);
        ctx.fillStyle = '#c4793a';
        ctx.shadowColor = '#c4793a'; ctx.shadowBlur = 8;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Matrix display
        this.drawMatrixInfo(ctx, w, h, mat);
    },

    drawShape(ctx, w, h, pts, fillColor, strokeColor, dashed) {
        if (pts.length < 2) return;
        ctx.beginPath();
        pts.forEach((pt, i) => {
            const px = this.mapX(pt[0], w), py = this.mapY(pt[1], h);
            if (i === 0) ctx.moveTo(px, py);
            else ctx.lineTo(px, py);
        });
        ctx.closePath();

        ctx.fillStyle = fillColor;
        ctx.fill();

        if (dashed) ctx.setLineDash([4, 3]);
        ctx.strokeStyle = strokeColor;
        ctx.lineWidth = dashed ? 1.5 : 2.5;
        ctx.stroke();
        if (dashed) ctx.setLineDash([]);

        // Vertex labels
        const labels = ['A', 'B', 'C', 'D'];
        pts.forEach((pt, i) => {
            const px = this.mapX(pt[0], w), py = this.mapY(pt[1], h);
            ctx.beginPath();
            ctx.arc(px, py, 3.5, 0, Math.PI * 2);
            ctx.fillStyle = strokeColor;
            ctx.fill();

            if (!dashed) {
                ctx.fillStyle = 'rgba(255,255,255,0.6)';
                ctx.font = '10px Inter, sans-serif';
                ctx.textAlign = 'left'; ctx.textBaseline = 'bottom';
                ctx.fillText(labels[i] + "'", px + 5, py - 3);
            }
        });
    },

    drawMatrixInfo(ctx, w, h, mat) {
        // Display transformation matrix in top-right corner
        const pad = 12;
        const x0 = w - 140, y0 = pad;

        ctx.fillStyle = 'rgba(0,0,0,0.4)';
        ctx.fillRect(x0 - 8, y0 - 4, 140, 52);

        ctx.fillStyle = 'rgba(255,255,255,0.5)';
        ctx.font = '10px monospace';
        ctx.textAlign = 'left';
        ctx.fillText('变换矩阵:', x0, y0 + 10);
        ctx.fillText(`[ ${mat.a.toFixed(2)}  ${mat.b.toFixed(2)}  ${mat.tx.toFixed(2)} ]`, x0, y0 + 24);
        ctx.fillText(`[ ${mat.c.toFixed(2)}  ${mat.d.toFixed(2)}  ${mat.ty.toFixed(2)} ]`, x0, y0 + 38);
    },

    setMirror(axis) {
        this.mirror = axis;
        document.querySelectorAll('.geo-mirror-btn').forEach(b => {
            b.classList.remove('active');
            if (b.dataset.axis === axis || b.textContent.trim().toLowerCase().includes(axis === 'none' ? '无' : axis)) b.classList.add('active');
        });
        this.draw();
    },

    setShape(name) {
        const shapes = {
            square: [[-1,-1],[1,-1],[1,1],[-1,1]],
            triangle: [[0,1.5],[-1.3,-0.75],[1.3,-0.75]],
            arrow: [[0,1.5],[0.8,0],[0.3,0],[0.3,-1.5],[-0.3,-1.5],[-0.3,0],[-0.8,0]],
            star: (() => {
                const pts = [];
                for (let i = 0; i < 10; i++) {
                    const a = (i / 10) * Math.PI * 2 - Math.PI / 2;
                    const r = i % 2 === 0 ? 1.5 : 0.6;
                    pts.push([Math.cos(a) * r, Math.sin(a) * r]);
                }
                return pts;
            })()
        };
        this.shape = shapes[name] || shapes.square;
        document.querySelectorAll('.geo-shape-btn').forEach(b => {
            b.classList.remove('active');
            if (b.dataset.shape === name || b.textContent.trim().toLowerCase().includes(name)) b.classList.add('active');
        });
        this.draw();
    },

    resetAll() {
        this.tx = 0; this.ty = 0; this.angle = 0;
        this.sx = 1; this.sy = 1; this.shx = 0;
        this.mirror = 'none';
        // Reset sliders
        const defaults = { 'geo-tx': 0, 'geo-ty': 0, 'geo-angle': 0, 'geo-sx': 1, 'geo-sy': 1, 'geo-shx': 0 };
        for (const [id, val] of Object.entries(defaults)) {
            const el = document.getElementById(id);
            if (el) el.value = val;
            const lbl = document.getElementById(id + '-val');
            if (lbl) lbl.textContent = id === 'geo-angle' ? '0' : val.toFixed(2);
        }
        document.querySelectorAll('.geo-mirror-btn').forEach(b => b.classList.remove('active'));
        const noneBtn = document.querySelector('.geo-mirror-btn[data-v="none"]');
        if (noneBtn) noneBtn.classList.add('active');
        this.draw();
    },

    animate() {
        if (this.animating) { this.stopAnimate(); return; }
        this.animating = true;
        this.animTime = 0;
        const btn = document.getElementById('geo-animate-btn');
        if (btn) btn.textContent = '⏸ 暂停';

        const loop = () => {
            if (!this.animating) return;
            this.animTime += 0.02;
            this.angle = (this.animTime * 60) % 360;
            this.sx = 1 + 0.5 * Math.sin(this.animTime * 2);
            this.sy = 1 + 0.5 * Math.cos(this.animTime * 1.5);
            this.tx = 2 * Math.sin(this.animTime * 0.8);
            this.ty = 1.5 * Math.cos(this.animTime * 0.6);

            // Update slider displays
            const updates = {
                'geo-tx': this.tx, 'geo-ty': this.ty,
                'geo-angle': this.angle, 'geo-sx': this.sx, 'geo-sy': this.sy
            };
            for (const [id, val] of Object.entries(updates)) {
                const el = document.getElementById(id);
                if (el) el.value = val;
                const lbl = document.getElementById(id + '-val');
                if (lbl) lbl.textContent = id === 'geo-angle' ? Math.round(val) : val.toFixed(2);
            }

            this.draw();
            this.animId = requestAnimationFrame(loop);
        };
        this.animId = requestAnimationFrame(loop);
    },

    stopAnimate() {
        this.animating = false;
        if (this.animId) cancelAnimationFrame(this.animId);
        this.animId = null;
        const btn = document.getElementById('geo-animate-btn');
        if (btn) btn.textContent = '▶ 动画';
    }
};

// ── 初始化 ──
function initGeoTransform() {
    GeoTransform.init();
    let resizeT;
    window.addEventListener('resize', () => {
        clearTimeout(resizeT);
        resizeT = setTimeout(() => GeoTransform.draw(), 200);
    });
}

window.GeoTransform = GeoTransform;
window.initGeoTransform = initGeoTransform;

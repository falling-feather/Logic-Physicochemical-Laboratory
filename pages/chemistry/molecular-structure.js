// ===== Molecular Structure Visualization =====
const MoleculeVis = {
    canvas: null,
    ctx: null,
    W: 0, H: 0,
    molecule: null,
    rotX: -0.4,
    rotY: 0.6,
    dragging: false,
    lastMouse: { x: 0, y: 0 },
    scale: 80,
    autoRotate: false,
    autoRotateId: null,

    // Atom visual properties: color, radius
    atomStyles: {
        H:  { color: '#ffffff', r: 0.31, name: '氢' },
        C:  { color: '#555555', r: 0.77, name: '碳' },
        N:  { color: '#3050F8', r: 0.75, name: '氮' },
        O:  { color: '#FF0D0D', r: 0.73, name: '氧' },
        S:  { color: '#FFFF30', r: 1.02, name: '硫' },
        P:  { color: '#FF8000', r: 1.06, name: '磷' },
        Cl: { color: '#1FF01F', r: 0.99, name: '氯' },
        F:  { color: '#90E050', r: 0.64, name: '氟' },
        Na: { color: '#AB5CF2', r: 1.66, name: '钠' },
        Fe: { color: '#E06633', r: 1.24, name: '铁' }
    },

    molecules: {
        H2O: {
            name: '水 H₂O',
            formula: 'H₂O',
            desc: '极性分子，键角 104.5°',
            atoms: [
                { el: 'O', x: 0, y: 0, z: 0 },
                { el: 'H', x: -0.76, y: 0.59, z: 0 },
                { el: 'H', x: 0.76, y: 0.59, z: 0 }
            ],
            bonds: [[0,1,1],[0,2,1]]
        },
        CO2: {
            name: '二氧化碳 CO₂',
            formula: 'CO₂',
            desc: '线性非极性分子，双键',
            atoms: [
                { el: 'C', x: 0, y: 0, z: 0 },
                { el: 'O', x: -1.16, y: 0, z: 0 },
                { el: 'O', x: 1.16, y: 0, z: 0 }
            ],
            bonds: [[0,1,2],[0,2,2]]
        },
        CH4: {
            name: '甲烷 CH₄',
            formula: 'CH₄',
            desc: '正四面体构型，键角 109.5°',
            atoms: [
                { el: 'C', x: 0, y: 0, z: 0 },
                { el: 'H', x: 0.63, y: 0.63, z: 0.63 },
                { el: 'H', x: -0.63, y: -0.63, z: 0.63 },
                { el: 'H', x: -0.63, y: 0.63, z: -0.63 },
                { el: 'H', x: 0.63, y: -0.63, z: -0.63 }
            ],
            bonds: [[0,1,1],[0,2,1],[0,3,1],[0,4,1]]
        },
        NH3: {
            name: '氨 NH₃',
            formula: 'NH₃',
            desc: '三角锥形，键角 107.3°',
            atoms: [
                { el: 'N', x: 0, y: -0.38, z: 0 },
                { el: 'H', x: 0.94, y: 0.31, z: 0 },
                { el: 'H', x: -0.47, y: 0.31, z: 0.82 },
                { el: 'H', x: -0.47, y: 0.31, z: -0.82 }
            ],
            bonds: [[0,1,1],[0,2,1],[0,3,1]]
        },
        C2H4: {
            name: '乙烯 C₂H₄',
            formula: 'C₂H₄',
            desc: '平面分子，C=C双键',
            atoms: [
                { el: 'C', x: -0.67, y: 0, z: 0 },
                { el: 'C', x: 0.67, y: 0, z: 0 },
                { el: 'H', x: -1.24, y: 0.93, z: 0 },
                { el: 'H', x: -1.24, y: -0.93, z: 0 },
                { el: 'H', x: 1.24, y: 0.93, z: 0 },
                { el: 'H', x: 1.24, y: -0.93, z: 0 }
            ],
            bonds: [[0,1,2],[0,2,1],[0,3,1],[1,4,1],[1,5,1]]
        },
        C2H2: {
            name: '乙炔 C₂H₂',
            formula: 'C₂H₂',
            desc: '线性分子，C≡C三键',
            atoms: [
                { el: 'C', x: -0.6, y: 0, z: 0 },
                { el: 'C', x: 0.6, y: 0, z: 0 },
                { el: 'H', x: -1.66, y: 0, z: 0 },
                { el: 'H', x: 1.66, y: 0, z: 0 }
            ],
            bonds: [[0,1,3],[0,2,1],[1,3,1]]
        },
        C6H6: {
            name: '苯 C₆H₆',
            formula: 'C₆H₆',
            desc: '平面六元环，离域π键',
            atoms: (() => {
                const atoms = [];
                for (let i = 0; i < 6; i++) {
                    const a = (i * 60 - 90) * Math.PI / 180;
                    atoms.push({ el: 'C', x: 1.4 * Math.cos(a), y: 1.4 * Math.sin(a), z: 0 });
                }
                for (let i = 0; i < 6; i++) {
                    const a = (i * 60 - 90) * Math.PI / 180;
                    atoms.push({ el: 'H', x: 2.48 * Math.cos(a), y: 2.48 * Math.sin(a), z: 0 });
                }
                return atoms;
            })(),
            bonds: (() => {
                const bonds = [];
                for (let i = 0; i < 6; i++) {
                    bonds.push([i, (i + 1) % 6, i % 2 === 0 ? 2 : 1]); // alternating double/single
                    bonds.push([i, i + 6, 1]); // C-H
                }
                return bonds;
            })()
        },
        NaCl: {
            name: '氯化钠 NaCl',
            formula: 'NaCl',
            desc: '离子键，晶格单元',
            atoms: [
                { el: 'Na', x: -1.2, y: 0, z: 0 },
                { el: 'Cl', x: 1.2, y: 0, z: 0 }
            ],
            bonds: [[0,1,1]]
        }
    },

    init() {
        this.canvas = document.getElementById('mol-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        this.loadMolecule('H2O');
        this.bindControls();
        window.addEventListener('resize', () => { this.resize(); this.draw(); });
    },

    resize() {
        const wrap = this.canvas.parentElement;
        const w = wrap.clientWidth;
        const h = Math.min(w, 480);
        this.canvas.width = w * devicePixelRatio;
        this.canvas.height = h * devicePixelRatio;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
        this.W = w;
        this.H = h;
    },

    bindControls() {
        // Molecule selector buttons
        document.querySelectorAll('.mol-select-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.mol-select-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.loadMolecule(btn.dataset.mol);
            });
        });

        // Canvas drag to rotate
        this.canvas.addEventListener('mousedown', e => {
            this.dragging = true;
            this.lastMouse = { x: e.clientX, y: e.clientY };
        });
        this.canvas.addEventListener('mousemove', e => {
            if (!this.dragging) return;
            const dx = e.clientX - this.lastMouse.x;
            const dy = e.clientY - this.lastMouse.y;
            this.rotY += dx * 0.01;
            this.rotX += dy * 0.01;
            this.lastMouse = { x: e.clientX, y: e.clientY };
            this.draw();
        });
        this.canvas.addEventListener('mouseup', () => this.dragging = false);
        this.canvas.addEventListener('mouseleave', () => this.dragging = false);

        // Touch
        this.canvas.addEventListener('touchstart', e => {
            e.preventDefault();
            this.dragging = true;
            this.lastMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
        }, { passive: false });
        this.canvas.addEventListener('touchmove', e => {
            e.preventDefault();
            if (!this.dragging) return;
            const dx = e.touches[0].clientX - this.lastMouse.x;
            const dy = e.touches[0].clientY - this.lastMouse.y;
            this.rotY += dx * 0.01;
            this.rotX += dy * 0.01;
            this.lastMouse = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            this.draw();
        }, { passive: false });
        this.canvas.addEventListener('touchend', () => this.dragging = false);

        // Scroll to zoom
        this.canvas.addEventListener('wheel', e => {
            e.preventDefault();
            this.scale = Math.max(30, Math.min(200, this.scale - e.deltaY * 0.1));
            this.draw();
        }, { passive: false });

        // Auto rotate button
        const autoBtn = document.getElementById('mol-auto-rotate');
        if (autoBtn) autoBtn.addEventListener('click', () => this.toggleAutoRotate());

        // Reset view
        const resetBtn = document.getElementById('mol-reset');
        if (resetBtn) resetBtn.addEventListener('click', () => {
            this.rotX = -0.4;
            this.rotY = 0.6;
            this.scale = 80;
            this.draw();
        });
    },

    loadMolecule(key) {
        this.molecule = this.molecules[key];
        if (!this.molecule) return;
        // Reset rotation for fresh view
        this.rotX = -0.4;
        this.rotY = 0.6;
        this.draw();
        this.updateInfo();
    },

    toggleAutoRotate() {
        const btn = document.getElementById('mol-auto-rotate');
        if (this.autoRotateId) {
            cancelAnimationFrame(this.autoRotateId);
            this.autoRotateId = null;
            this.autoRotate = false;
            if (btn) btn.textContent = '自动旋转';
            return;
        }
        this.autoRotate = true;
        if (btn) btn.textContent = '停止旋转';
        const loop = () => {
            this.rotY += 0.015;
            this.draw();
            this.autoRotateId = requestAnimationFrame(loop);
        };
        this.autoRotateId = requestAnimationFrame(loop);
    },

    // 3D rotation (Y then X)
    project(x, y, z) {
        // Rotate Y
        const cosY = Math.cos(this.rotY), sinY = Math.sin(this.rotY);
        let x1 = x * cosY + z * sinY;
        let z1 = -x * sinY + z * cosY;
        // Rotate X
        const cosX = Math.cos(this.rotX), sinX = Math.sin(this.rotX);
        let y1 = y * cosX - z1 * sinX;
        let z2 = y * sinX + z1 * cosX;
        // Perspective-ish scale
        const s = this.scale;
        const depth = 1 + z2 * 0.12;
        return {
            x: this.W / 2 + x1 * s,
            y: this.H / 2 + y1 * s,
            z: z2,
            depth: Math.max(0.3, depth)
        };
    },

    draw() {
        const { ctx, W, H } = this;
        if (!this.molecule) return;
        ctx.clearRect(0, 0, W, H);

        // Background
        ctx.fillStyle = '#0d1017';
        ctx.fillRect(0, 0, W, H);

        const mol = this.molecule;
        // Project all atoms
        const projected = mol.atoms.map(a => ({
            ...a,
            ...this.project(a.x, a.y, a.z)
        }));

        // Sort by z for painter's algorithm
        const bondsToDraw = [...mol.bonds].map(([i, j, order]) => ({
            i, j, order,
            avgZ: (projected[i].z + projected[j].z) / 2
        }));
        bondsToDraw.sort((a, b) => a.avgZ - b.avgZ);

        const atomsToDraw = projected.map((a, idx) => ({ ...a, idx }));
        atomsToDraw.sort((a, b) => a.z - b.z);

        // Draw bonds first
        bondsToDraw.forEach(({ i, j, order }) => {
            const a = projected[i];
            const b = projected[j];
            this.drawBond(a, b, order);
        });

        // Draw atoms
        atomsToDraw.forEach(a => {
            this.drawAtom(a);
        });
    },

    drawBond(a, b, order) {
        const { ctx } = this;
        const avgDepth = (a.depth + b.depth) / 2;
        const alpha = 0.3 + avgDepth * 0.3;

        if (order === 1) {
            ctx.strokeStyle = `rgba(180,180,180,${alpha})`;
            ctx.lineWidth = 3 * avgDepth;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        } else if (order === 2) {
            // Double bond: two parallel lines
            const dx = b.x - a.x, dy = b.y - a.y;
            const len = Math.hypot(dx, dy);
            const nx = -dy / len * 3, ny = dx / len * 3;
            ctx.strokeStyle = `rgba(180,180,180,${alpha})`;
            ctx.lineWidth = 2.5 * avgDepth;
            ctx.beginPath(); ctx.moveTo(a.x + nx, a.y + ny); ctx.lineTo(b.x + nx, b.y + ny); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(a.x - nx, a.y - ny); ctx.lineTo(b.x - nx, b.y - ny); ctx.stroke();
        } else if (order === 3) {
            // Triple bond
            const dx = b.x - a.x, dy = b.y - a.y;
            const len = Math.hypot(dx, dy);
            const nx = -dy / len * 4, ny = dx / len * 4;
            ctx.strokeStyle = `rgba(180,180,180,${alpha})`;
            ctx.lineWidth = 2 * avgDepth;
            ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(a.x + nx, a.y + ny); ctx.lineTo(b.x + nx, b.y + ny); ctx.stroke();
            ctx.beginPath(); ctx.moveTo(a.x - nx, a.y - ny); ctx.lineTo(b.x - nx, b.y - ny); ctx.stroke();
        }
    },

    drawAtom(a) {
        const { ctx } = this;
        const style = this.atomStyles[a.el] || { color: '#aaa', r: 0.5 };
        const r = style.r * 18 * a.depth;

        // Glow
        const grd = ctx.createRadialGradient(a.x - r * 0.2, a.y - r * 0.2, 0, a.x, a.y, r);
        grd.addColorStop(0, this.lighten(style.color, 0.4));
        grd.addColorStop(0.7, style.color);
        grd.addColorStop(1, this.darken(style.color, 0.3));

        ctx.fillStyle = grd;
        ctx.beginPath(); ctx.arc(a.x, a.y, r, 0, Math.PI * 2); ctx.fill();

        // Highlight
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.beginPath(); ctx.arc(a.x - r * 0.25, a.y - r * 0.25, r * 0.45, 0, Math.PI * 2); ctx.fill();

        // Element label
        ctx.fillStyle = a.el === 'H' ? '#333' : '#fff';
        ctx.font = `bold ${Math.round(11 * a.depth)}px "JetBrains Mono", monospace`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(a.el, a.x, a.y);
    },

    lighten(hex, amt) {
        const rgb = this.hexToRgb(hex);
        return `rgb(${Math.min(255, rgb.r + 255 * amt)},${Math.min(255, rgb.g + 255 * amt)},${Math.min(255, rgb.b + 255 * amt)})`;
    },

    darken(hex, amt) {
        const rgb = this.hexToRgb(hex);
        return `rgb(${Math.max(0, rgb.r - 255 * amt)},${Math.max(0, rgb.g - 255 * amt)},${Math.max(0, rgb.b - 255 * amt)})`;
    },

    hexToRgb(hex) {
        const h = hex.replace('#', '');
        return {
            r: parseInt(h.substring(0, 2), 16),
            g: parseInt(h.substring(2, 4), 16),
            b: parseInt(h.substring(4, 6), 16)
        };
    },

    updateInfo() {
        const el = document.getElementById('mol-info');
        if (!el || !this.molecule) return;
        const mol = this.molecule;
        const atomCounts = {};
        mol.atoms.forEach(a => { atomCounts[a.el] = (atomCounts[a.el] || 0) + 1; });
        const bondTypes = { 1: 0, 2: 0, 3: 0 };
        mol.bonds.forEach(([,,o]) => { bondTypes[o] = (bondTypes[o] || 0) + 1; });

        let html = `<div class="mol-info-title">${mol.name}</div>`;
        html += `<div class="mol-info-desc">${mol.desc}</div>`;
        html += `<div class="mol-info-row"><span class="mol-info-label">原子数</span><span>${mol.atoms.length}</span></div>`;
        html += `<div class="mol-info-row"><span class="mol-info-label">组成</span><span>`;
        for (const [el, count] of Object.entries(atomCounts)) {
            const style = this.atomStyles[el];
            html += `<span class="mol-atom-badge" style="background:${style ? style.color : '#aaa'};color:${el === 'H' ? '#333' : '#fff'}">${el}</span> ×${count} `;
        }
        html += `</span></div>`;
        html += `<div class="mol-info-row"><span class="mol-info-label">化学键</span><span>`;
        if (bondTypes[1]) html += `单键 ×${bondTypes[1]} `;
        if (bondTypes[2]) html += `双键 ×${bondTypes[2]} `;
        if (bondTypes[3]) html += `三键 ×${bondTypes[3]}`;
        html += `</span></div>`;

        el.innerHTML = html;
    }
};

function initMoleculeVis() {
    MoleculeVis.init();
}

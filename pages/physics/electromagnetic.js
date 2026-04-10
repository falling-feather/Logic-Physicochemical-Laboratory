// ===== 电磁场可视化引擎 =====

const EMField = {
    canvas: null,
    ctx: null,
    charges: [],
    running: false,
    animId: null,

    // 拖拽状态
    dragIndex: -1,
    dragOffsetX: 0,
    dragOffsetY: 0,

    // 显示选项
    showFieldLines: true,
    showVectorField: false,
    fieldLineCount: 16,       // 每个正电荷发出的场线数
    vectorGridStep: 32,       // 矢量场网格间距
    arrowScale: 22,           // 箭头最大长度

    // 物理常数（缩放后的库仑常数）
    k: 800,

    // charge 颜色
    COLOR_POS: '#ef4444',
    COLOR_NEG: '#3b82f6',

    init() {
        this.canvas = document.getElementById('em-canvas');
        if (!this.canvas) return;

        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
        this.bindControls();
        this.bindCanvas();

        window.addEventListener('resize', () => this.resizeCanvas());
    },

    /* ── Canvas 尺寸 ── */
    resizeCanvas() {
        if (!this.canvas) return;
        const container = this.canvas.parentElement;
        const rect = container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = rect.width;
        this.H = rect.height;
        this.render();
    },

    /* ── 控件绑定 ── */
    bindControls() {
        const addPos = document.getElementById('em-add-pos');
        const addNeg = document.getElementById('em-add-neg');
        const clearBtn = document.getElementById('em-clear');
        const toggleLines = document.getElementById('em-toggle-lines');
        const toggleVectors = document.getElementById('em-toggle-vectors');
        const lineCountSlider = document.getElementById('em-line-count');

        if (addPos) addPos.addEventListener('click', () => this.addCharge(+1));
        if (addNeg) addNeg.addEventListener('click', () => this.addCharge(-1));
        if (clearBtn) clearBtn.addEventListener('click', () => {
            this.charges = [];
            this.updateStats();
            this.render();
        });

        if (toggleLines) toggleLines.addEventListener('change', (e) => {
            this.showFieldLines = e.target.checked;
            this.render();
        });
        if (toggleVectors) toggleVectors.addEventListener('change', (e) => {
            this.showVectorField = e.target.checked;
            this.render();
        });

        if (lineCountSlider) {
            lineCountSlider.addEventListener('input', (e) => {
                this.fieldLineCount = parseInt(e.target.value);
                document.getElementById('em-line-count-value').textContent = this.fieldLineCount;
                this.render();
            });
        }
    },

    /* ── Canvas 交互 ── */
    bindCanvas() {
        const getPos = (e) => {
            const rect = this.canvas.getBoundingClientRect();
            if (e.touches) {
                return { x: e.touches[0].clientX - rect.left, y: e.touches[0].clientY - rect.top };
            }
            return { x: e.clientX - rect.left, y: e.clientY - rect.top };
        };

        const onDown = (e) => {
            e.preventDefault();
            const pos = getPos(e);
            // 检查是否点到了电荷
            for (let i = this.charges.length - 1; i >= 0; i--) {
                const c = this.charges[i];
                const dx = pos.x - c.x, dy = pos.y - c.y;
                if (dx * dx + dy * dy < 400) { // ~20px 半径
                    this.dragIndex = i;
                    this.dragOffsetX = dx;
                    this.dragOffsetY = dy;
                    this.canvas.style.cursor = 'grabbing';
                    return;
                }
            }
        };

        const onMove = (e) => {
            if (this.dragIndex < 0) return;
            e.preventDefault();
            const pos = getPos(e);
            this.charges[this.dragIndex].x = pos.x - this.dragOffsetX;
            this.charges[this.dragIndex].y = pos.y - this.dragOffsetY;
            this.render();
        };

        const onUp = () => {
            this.dragIndex = -1;
            this.canvas.style.cursor = 'default';
        };

        this.canvas.addEventListener('mousedown', onDown);
        this.canvas.addEventListener('mousemove', onMove);
        this.canvas.addEventListener('mouseup', onUp);
        this.canvas.addEventListener('mouseleave', onUp);

        this.canvas.addEventListener('touchstart', onDown, { passive: false });
        this.canvas.addEventListener('touchmove', onMove, { passive: false });
        this.canvas.addEventListener('touchend', onUp);
    },

    /* ── 添加电荷 ── */
    addCharge(sign) {
        if (this.charges.length >= 20) return; // 最多 20 个电荷
        const margin = 60;
        const x = margin + Math.random() * (this.W - 2 * margin);
        const y = margin + Math.random() * (this.H - 2 * margin);
        this.charges.push({ x, y, q: sign });
        this.updateStats();
        this.render();
    },

    updateStats() {
        const countEl = document.getElementById('em-charge-count');
        if (countEl) countEl.textContent = this.charges.length;
    },

    /* ── 计算某一点的电场 ── */
    fieldAt(px, py) {
        let ex = 0, ey = 0;
        for (const c of this.charges) {
            const dx = px - c.x;
            const dy = py - c.y;
            const r2 = dx * dx + dy * dy;
            if (r2 < 100) continue; // 避免奇点
            const r = Math.sqrt(r2);
            const E = this.k * c.q / r2;
            ex += E * dx / r;
            ey += E * dy / r;
        }
        return { x: ex, y: ey };
    },

    /* ── 渲染 ── */
    render() {
        const ctx = this.ctx;
        if (!ctx) return;

        ctx.clearRect(0, 0, this.W, this.H);

        // 背景网格
        this.drawGrid();

        if (this.charges.length === 0) {
            this.drawEmptyHint();
            return;
        }

        // 电场线
        if (this.showFieldLines) this.drawFieldLines();

        // 矢量场
        if (this.showVectorField) this.drawVectorField();

        // 电荷
        this.drawCharges();
    },

    /* ── 背景网格 ── */
    drawGrid() {
        const ctx = this.ctx;
        ctx.strokeStyle = 'rgba(255,255,255,0.03)';
        ctx.lineWidth = 0.5;
        const step = 40;
        for (let x = step; x < this.W; x += step) {
            ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, this.H); ctx.stroke();
        }
        for (let y = step; y < this.H; y += step) {
            ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(this.W, y); ctx.stroke();
        }
    },

    /* ── 空状态提示 ── */
    drawEmptyHint() {
        const ctx = this.ctx;
        ctx.fillStyle = 'rgba(255,255,255,0.15)';
        ctx.font = '500 16px Inter, Noto Sans SC, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('添加电荷以查看电场分布', this.W / 2, this.H / 2);
        ctx.textAlign = 'left';
    },

    /* ── 电场线绘制 ── */
    drawFieldLines() {
        const ctx = this.ctx;
        const positives = this.charges.filter(c => c.q > 0);
        const negatives = this.charges.filter(c => c.q < 0);

        // 从正电荷发出场线
        const sources = positives.length > 0 ? positives : negatives;
        const lineCount = this.fieldLineCount;

        for (const src of sources) {
            for (let i = 0; i < lineCount; i++) {
                const angle = (2 * Math.PI * i) / lineCount;
                const startR = 14;
                let x = src.x + startR * Math.cos(angle);
                let y = src.y + startR * Math.sin(angle);

                ctx.beginPath();
                ctx.moveTo(x, y);

                const step = 3;
                const maxSteps = 600;
                let outOfBounds = false;

                for (let s = 0; s < maxSteps; s++) {
                    const E = this.fieldAt(x, y);
                    const mag = Math.sqrt(E.x * E.x + E.y * E.y);
                    if (mag < 0.5) break;

                    // 方向：正电荷发出的线沿 E 方向，负电荷发出的线逆 E 方向
                    const dir = (src.q > 0) ? 1 : -1;
                    const nx = x + dir * step * E.x / mag;
                    const ny = y + dir * step * E.y / mag;

                    // 检查是否到达另一个电荷
                    let hitCharge = false;
                    for (const c of this.charges) {
                        if (c === src) continue;
                        const dx = nx - c.x, dy = ny - c.y;
                        if (dx * dx + dy * dy < 144) { // 12px
                            hitCharge = true;
                            break;
                        }
                    }

                    ctx.lineTo(nx, ny);

                    if (hitCharge) break;
                    if (nx < -10 || nx > this.W + 10 || ny < -10 || ny > this.H + 10) {
                        outOfBounds = true;
                        break;
                    }

                    x = nx;
                    y = ny;
                }

                // 颜色渐变 —— 从 src 颜色到白色
                const gradient = ctx.createLinearGradient(src.x, src.y, x, y);
                const baseColor = src.q > 0 ? 'rgba(239,68,68,' : 'rgba(59,130,246,';
                gradient.addColorStop(0, baseColor + '0.6)');
                gradient.addColorStop(1, baseColor + '0.08)');

                ctx.strokeStyle = gradient;
                ctx.lineWidth = 1.2;
                ctx.stroke();
            }
        }
    },

    /* ── 矢量场绘制 ── */
    drawVectorField() {
        const ctx = this.ctx;
        const step = this.vectorGridStep;

        for (let x = step / 2; x < this.W; x += step) {
            for (let y = step / 2; y < this.H; y += step) {
                // 跳过电荷附近
                let tooClose = false;
                for (const c of this.charges) {
                    const dx = x - c.x, dy = y - c.y;
                    if (dx * dx + dy * dy < 900) { tooClose = true; break; }
                }
                if (tooClose) continue;

                const E = this.fieldAt(x, y);
                const mag = Math.sqrt(E.x * E.x + E.y * E.y);
                if (mag < 0.3) continue;

                // 箭头长度按对数缩放，避免极端值
                const len = Math.min(this.arrowScale, 5 * Math.log(1 + mag));
                const angle = Math.atan2(E.y, E.x);

                const ex = x + len * Math.cos(angle);
                const ey = y + len * Math.sin(angle);

                // 根据场强着色
                const intensity = Math.min(1, mag / 30);
                const r = Math.round(59 + intensity * 180);
                const g = Math.round(130 - intensity * 62);
                const b = Math.round(246 - intensity * 182);
                const alpha = 0.3 + intensity * 0.5;

                ctx.strokeStyle = `rgba(${r},${g},${b},${alpha})`;
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(x, y);
                ctx.lineTo(ex, ey);
                ctx.stroke();

                // 箭头头部
                const headLen = 4;
                ctx.beginPath();
                ctx.moveTo(ex, ey);
                ctx.lineTo(ex - headLen * Math.cos(angle - 0.5), ey - headLen * Math.sin(angle - 0.5));
                ctx.moveTo(ex, ey);
                ctx.lineTo(ex - headLen * Math.cos(angle + 0.5), ey - headLen * Math.sin(angle + 0.5));
                ctx.stroke();
            }
        }
    },

    /* ── 绘制电荷 ── */
    drawCharges() {
        const ctx = this.ctx;

        for (const c of this.charges) {
            const r = 16;

            // 光晕
            const glow = ctx.createRadialGradient(c.x, c.y, r * 0.5, c.x, c.y, r * 2.5);
            const glowColor = c.q > 0 ? 'rgba(239,68,68,' : 'rgba(59,130,246,';
            glow.addColorStop(0, glowColor + '0.25)');
            glow.addColorStop(1, glowColor + '0)');
            ctx.fillStyle = glow;
            ctx.beginPath();
            ctx.arc(c.x, c.y, r * 2.5, 0, Math.PI * 2);
            ctx.fill();

            // 电荷实体
            const grad = ctx.createRadialGradient(c.x - 3, c.y - 3, 2, c.x, c.y, r);
            if (c.q > 0) {
                grad.addColorStop(0, '#fca5a5');
                grad.addColorStop(1, '#dc2626');
            } else {
                grad.addColorStop(0, '#93c5fd');
                grad.addColorStop(1, '#2563eb');
            }
            ctx.fillStyle = grad;
            ctx.beginPath();
            ctx.arc(c.x, c.y, r, 0, Math.PI * 2);
            ctx.fill();

            // 边框
            ctx.strokeStyle = c.q > 0 ? '#fca5a5' : '#93c5fd';
            ctx.lineWidth = 1.5;
            ctx.stroke();

            // +/- 符号
            ctx.fillStyle = '#fff';
            ctx.font = 'bold 16px Inter, sans-serif';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(c.q > 0 ? '+' : '−', c.x, c.y + 1);
        }
        ctx.textAlign = 'left';
        ctx.textBaseline = 'alphabetic';
    }
};

/* ── 初始化入口 ── */
function initElectromagnetic() {
    EMField.init();
}

// ===== 狭义相对论可视化引擎 =====

const RelativityDemo = {
    canvas: null,
    ctx: null,
    animId: null,
    running: true,

    // 速度参数 (v/c)
    beta: 0.0,
    gamma: 1.0,

    // 演示模式: 'time' | 'length' | 'mass'
    mode: 'time',

    // 动画时间
    t: 0,

    // 时钟
    restClockAngle: 0,
    moveClockAngle: 0,

    // 飞船闪烁
    shipX: 0,

    init() {
        this.canvas = document.getElementById('relativity-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
        this.bindControls();
        window.addEventListener('resize', () => this.resizeCanvas());
        this.updateGamma();
        this.updateInfo();
        this.start();
    },

    resizeCanvas() {
        const rect = this.canvas.parentElement.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = rect.width;
        this.H = rect.height;
    },

    bindControls() {
        const slider = document.getElementById('rel-velocity');
        const label = document.getElementById('rel-velocity-val');
        if (slider) {
            slider.addEventListener('input', () => {
                this.beta = parseFloat(slider.value);
                label.textContent = this.beta.toFixed(2) + 'c';
                this.updateGamma();
                this.updateInfo();
            });
        }

        document.querySelectorAll('.rel-mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.rel-mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.mode = btn.dataset.mode;
                this.t = 0;
                this.restClockAngle = 0;
                this.moveClockAngle = 0;
                this.shipX = 0;
                this.updateInfo();
            });
        });

        const resetBtn = document.getElementById('rel-reset');
        if (resetBtn) {
            resetBtn.addEventListener('click', () => {
                this.t = 0;
                this.restClockAngle = 0;
                this.moveClockAngle = 0;
                this.shipX = 0;
            });
        }
    },

    updateGamma() {
        const b2 = this.beta * this.beta;
        this.gamma = b2 >= 1 ? 100 : 1 / Math.sqrt(1 - b2);
    },

    /* ── 绘制 ── */

    start() {
        const step = () => {
            this.t += 0.016;
            this.draw();
            if (this.running) this.animId = requestAnimationFrame(step);
        };
        this.animId = requestAnimationFrame(step);
    },

    draw() {
        const ctx = this.ctx;
        const W = this.W;
        const H = this.H;
        ctx.clearRect(0, 0, W, H);

        // 背景星空
        this.drawStars(ctx, W, H);

        if (this.mode === 'time') this.drawTimeDilation(ctx, W, H);
        else if (this.mode === 'length') this.drawLengthContraction(ctx, W, H);
        else if (this.mode === 'mass') this.drawMassEnergy(ctx, W, H);
    },

    drawStars(ctx, W, H) {
        // 伪随机星星
        const seed = 42;
        for (let i = 0; i < 60; i++) {
            const x = ((seed * (i + 1) * 7919) % 10000) / 10000 * W;
            const y = ((seed * (i + 1) * 6271) % 10000) / 10000 * H;
            const r = ((seed * (i + 1) * 3571) % 10000) / 10000 * 1.5 + 0.3;
            const alpha = 0.3 + 0.3 * Math.sin(this.t * 2 + i);
            ctx.beginPath();
            ctx.arc(x, y, r, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(200,210,240,${alpha})`;
            ctx.fill();
        }
    },

    /* ── 时间膨胀 ── */
    drawTimeDilation(ctx, W, H) {
        const cx1 = W * 0.28;
        const cx2 = W * 0.72;
        const cy = H * 0.5;
        const clockR = Math.min(W * 0.14, H * 0.28, 90);

        // 静止时钟速度
        const restSpeed = 1.0;
        const moveSpeed = 1.0 / this.gamma;

        this.restClockAngle += restSpeed * 0.03;
        this.moveClockAngle += moveSpeed * 0.03;

        // 标签
        ctx.fillStyle = '#8b9dc3';
        ctx.font = '14px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('静止观察者', cx1, cy - clockR - 24);
        ctx.fillText('高速运动者 (v = ' + this.beta.toFixed(2) + 'c)', cx2, cy - clockR - 24);

        // 绘制两个时钟
        this.drawClock(ctx, cx1, cy, clockR, this.restClockAngle, '#5b8dce', '1.00s');
        this.drawClock(ctx, cx2, cy, clockR, this.moveClockAngle, '#c4793a', (1 / this.gamma).toFixed(3) + 's');

        // γ 显示
        ctx.fillStyle = '#e8dcc8';
        ctx.font = 'bold 18px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText('γ = ' + this.gamma.toFixed(4), W * 0.5, H * 0.12);

        // 公式
        ctx.fillStyle = '#8b9dc3';
        ctx.font = '13px JetBrains Mono, monospace';
        ctx.fillText("Δt' = γ · Δt", W * 0.5, H * 0.92);
    },

    drawClock(ctx, cx, cy, r, angle, color, label) {
        // 表盘
        ctx.beginPath();
        ctx.arc(cx, cy, r, 0, Math.PI * 2);
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.5;
        ctx.stroke();

        // 刻度
        for (let i = 0; i < 12; i++) {
            const a = (i / 12) * Math.PI * 2 - Math.PI / 2;
            const inner = r * 0.85;
            const outer = r * 0.95;
            ctx.beginPath();
            ctx.moveTo(cx + Math.cos(a) * inner, cy + Math.sin(a) * inner);
            ctx.lineTo(cx + Math.cos(a) * outer, cy + Math.sin(a) * outer);
            ctx.strokeStyle = 'rgba(200,210,240,0.5)';
            ctx.lineWidth = 1.5;
            ctx.stroke();
        }

        // 中心点
        ctx.beginPath();
        ctx.arc(cx, cy, 3, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();

        // 秒针
        const a = angle - Math.PI / 2;
        ctx.beginPath();
        ctx.moveTo(cx, cy);
        ctx.lineTo(cx + Math.cos(a) * r * 0.75, cy + Math.sin(a) * r * 0.75);
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.stroke();

        // 标签
        ctx.fillStyle = color;
        ctx.font = 'bold 14px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText(label, cx, cy + r + 22);
    },

    /* ── 长度收缩 ── */
    drawLengthContraction(ctx, W, H) {
        const topY = H * 0.28;
        const botY = H * 0.68;
        const restLen = W * 0.35;
        const moveLen = restLen / this.gamma;
        const cx = W * 0.5;

        // 标签
        ctx.fillStyle = '#8b9dc3';
        ctx.font = '14px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('静止参考系中的飞船', cx, topY - 40);
        ctx.fillText('运动参考系中的飞船 (v = ' + this.beta.toFixed(2) + 'c)', cx, botY - 40);

        // 静止飞船
        this.drawShip(ctx, cx - restLen / 2, topY, restLen, 40, '#5b8dce');

        // 运动飞船（收缩）
        this.shipX += this.beta * 1.2;
        if (this.shipX > W * 0.6) this.shipX = -W * 0.6;
        const moveShipCx = cx + this.shipX;
        this.drawShip(ctx, moveShipCx - moveLen / 2, botY, moveLen, 40, '#c4793a');

        // 尺寸标注 — 静止
        this.drawDimension(ctx, cx - restLen / 2, topY + 56, cx + restLen / 2, topY + 56, 'L₀ = 1.000', '#5b8dce');

        // 尺寸标注 — 运动
        this.drawDimension(ctx, moveShipCx - moveLen / 2, botY + 56, moveShipCx + moveLen / 2, botY + 56,
            "L = L₀/γ = " + (1 / this.gamma).toFixed(3), '#c4793a');

        // γ 显示
        ctx.fillStyle = '#e8dcc8';
        ctx.font = 'bold 18px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText('γ = ' + this.gamma.toFixed(4), W * 0.5, H * 0.12);

        // 公式
        ctx.fillStyle = '#8b9dc3';
        ctx.font = '13px JetBrains Mono, monospace';
        ctx.fillText("L = L₀ / γ = L₀ · √(1 - v²/c²)", W * 0.5, H * 0.92);
    },

    drawShip(ctx, x, y, w, h, color) {
        ctx.save();
        ctx.beginPath();
        // 机身
        ctx.moveTo(x, y + h * 0.3);
        ctx.lineTo(x + w * 0.15, y);
        ctx.lineTo(x + w * 0.85, y);
        ctx.lineTo(x + w, y + h * 0.3);
        ctx.lineTo(x + w * 0.95, y + h * 0.7);
        ctx.lineTo(x + w * 0.85, y + h);
        ctx.lineTo(x + w * 0.15, y + h);
        ctx.lineTo(x + w * 0.05, y + h * 0.7);
        ctx.closePath();

        const grad = ctx.createLinearGradient(x, y, x, y + h);
        grad.addColorStop(0, color);
        grad.addColorStop(1, color + '66');
        ctx.fillStyle = grad;
        ctx.fill();
        ctx.strokeStyle = color;
        ctx.lineWidth = 1.5;
        ctx.stroke();

        // 窗口
        const winR = Math.min(h * 0.15, 6);
        ctx.beginPath();
        ctx.arc(x + w * 0.5, y + h * 0.4, winR, 0, Math.PI * 2);
        ctx.fillStyle = '#e8dcc8';
        ctx.fill();
        ctx.restore();
    },

    drawDimension(ctx, x1, y, x2, y2, label, color) {
        ctx.strokeStyle = color;
        ctx.lineWidth = 1;
        // 横线
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x2, y);
        ctx.stroke();
        // 两端竖线
        ctx.beginPath();
        ctx.moveTo(x1, y - 6);
        ctx.lineTo(x1, y + 6);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(x2, y - 6);
        ctx.lineTo(x2, y + 6);
        ctx.stroke();
        // 箭头
        ctx.beginPath();
        ctx.moveTo(x1, y);
        ctx.lineTo(x1 + 6, y - 3);
        ctx.lineTo(x1 + 6, y + 3);
        ctx.closePath();
        ctx.fillStyle = color;
        ctx.fill();
        ctx.beginPath();
        ctx.moveTo(x2, y);
        ctx.lineTo(x2 - 6, y - 3);
        ctx.lineTo(x2 - 6, y + 3);
        ctx.closePath();
        ctx.fill();
        // 标签
        ctx.fillStyle = color;
        ctx.font = '12px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText(label, (x1 + x2) / 2, y + 20);
    },

    /* ── 质能等价 ── */
    drawMassEnergy(ctx, W, H) {
        const cx = W * 0.5;
        const baseM = 1.0;
        const relM = baseM * this.gamma;
        const E = relM; // E = γmc² (单位 mc²)
        const Ek = (this.gamma - 1) * baseM; // 动能
        const E0 = baseM; // 静止能量

        // γ 显示
        ctx.fillStyle = '#e8dcc8';
        ctx.font = 'bold 18px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText('γ = ' + this.gamma.toFixed(4), cx, H * 0.1);

        // 能量柱状图
        const barW = Math.min(W * 0.12, 60);
        const barMaxH = H * 0.5;
        const barY = H * 0.72;
        const barGap = W * 0.18;

        const bars = [
            { label: 'E₀ = mc²', val: E0, max: Math.max(E, 3), color: '#5b8dce' },
            { label: 'Eₖ = (γ-1)mc²', val: Ek, max: Math.max(E, 3), color: '#c4793a' },
            { label: 'E = γmc²', val: E, max: Math.max(E, 3), color: '#8b6fc0' }
        ];

        bars.forEach((bar, i) => {
            const bx = cx + (i - 1) * barGap - barW / 2;
            const bh = Math.min(bar.val / bar.max, 1) * barMaxH;

            // 背景槽
            ctx.fillStyle = 'rgba(200,210,240,0.08)';
            ctx.fillRect(bx, barY - barMaxH, barW, barMaxH);

            // 值
            const grad = ctx.createLinearGradient(bx, barY, bx, barY - bh);
            grad.addColorStop(0, bar.color + '99');
            grad.addColorStop(1, bar.color);
            ctx.fillStyle = grad;
            ctx.fillRect(bx, barY - bh, barW, bh);

            // 边框
            ctx.strokeStyle = bar.color;
            ctx.lineWidth = 1;
            ctx.strokeRect(bx, barY - barMaxH, barW, barMaxH);

            // 数值
            ctx.fillStyle = bar.color;
            ctx.font = 'bold 13px JetBrains Mono, monospace';
            ctx.textAlign = 'center';
            ctx.fillText(bar.val.toFixed(3), bx + barW / 2, barY - bh - 8);

            // 标签
            ctx.fillStyle = '#8b9dc3';
            ctx.font = '12px JetBrains Mono, monospace';
            ctx.fillText(bar.label, bx + barW / 2, barY + 18);
        });

        // 单位说明
        ctx.fillStyle = '#8b9dc3';
        ctx.font = '11px Inter, sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('(单位: mc²)', cx, barY + 36);

        // 质量球
        const ballY = H * 0.2;
        const restR = 18;
        const relR = restR * Math.min(Math.pow(this.gamma, 0.3), 3);

        // 静止质量球
        ctx.beginPath();
        ctx.arc(cx - barGap, ballY, restR, 0, Math.PI * 2);
        ctx.fillStyle = '#5b8dce44';
        ctx.fill();
        ctx.strokeStyle = '#5b8dce';
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = '#5b8dce';
        ctx.font = '12px JetBrains Mono, monospace';
        ctx.fillText('m₀', cx - barGap, ballY + restR + 16);

        // 相对论质量球（视觉放大）
        ctx.beginPath();
        ctx.arc(cx + barGap, ballY, relR, 0, Math.PI * 2);
        ctx.fillStyle = '#8b6fc044';
        ctx.fill();
        ctx.strokeStyle = '#8b6fc0';
        ctx.lineWidth = 2;
        ctx.stroke();
        ctx.fillStyle = '#8b6fc0';
        ctx.font = '12px JetBrains Mono, monospace';
        ctx.fillText('γm₀ = ' + relM.toFixed(2), cx + barGap, ballY + relR + 16);

        // 公式
        ctx.fillStyle = '#8b9dc3';
        ctx.font = '13px JetBrains Mono, monospace';
        ctx.textAlign = 'center';
        ctx.fillText('E² = (pc)² + (mc²)²    |    E = γmc²', cx, H * 0.93);
    },

    /* ── 信息面板 ── */
    updateInfo() {
        const info = document.getElementById('rel-info');
        if (!info) return;

        const g = this.gamma;
        const b = this.beta;

        if (this.mode === 'time') {
            info.innerHTML = `
                <h3>时间膨胀 Time Dilation</h3>
                <p>当物体以接近光速运动时，运动参考系中的时间会变慢。静止观察者测量到的时间间隔 Δt'
                   与运动物体固有时间 Δt 的关系：</p>
                <p style="text-align:center;font-family:'JetBrains Mono',monospace;font-size:1.1em;color:#e8dcc8;">
                    Δt' = γ · Δt = ${g.toFixed(4)} · Δt
                </p>
                <p>当前速度 <strong>v = ${b.toFixed(2)}c</strong>，洛伦兹因子 <strong>γ = ${g.toFixed(4)}</strong>。
                   运动时钟每走 <strong>${(1/g).toFixed(3)}</strong> 秒，静止时钟走 1 秒。</p>`;
        } else if (this.mode === 'length') {
            info.innerHTML = `
                <h3>长度收缩 Length Contraction</h3>
                <p>运动方向上的长度在静止观察者看来会缩短。长度收缩公式：</p>
                <p style="text-align:center;font-family:'JetBrains Mono',monospace;font-size:1.1em;color:#e8dcc8;">
                    L = L₀ / γ = L₀ · √(1 - v²/c²) = ${(1/g).toFixed(4)} · L₀
                </p>
                <p>当前速度 <strong>v = ${b.toFixed(2)}c</strong>，飞船长度收缩为原来的
                   <strong>${(100/g).toFixed(1)}%</strong>。</p>`;
        } else {
            info.innerHTML = `
                <h3>质能等价 Mass-Energy Equivalence</h3>
                <p>爱因斯坦质能关系 E = mc² 是狭义相对论最著名的推论。运动物体的总能量：</p>
                <p style="text-align:center;font-family:'JetBrains Mono',monospace;font-size:1.1em;color:#e8dcc8;">
                    E = γmc² = ${g.toFixed(4)}mc²
                </p>
                <p>其中静止能量 E₀ = mc²，动能 Eₖ = (γ-1)mc² = <strong>${(g-1).toFixed(4)}mc²</strong>。
                   在低速 (v≪c) 时，Eₖ ≈ ½mv²。</p>`;
        }
    }
};

function initRelativity() {
    RelativityDemo.init();
}

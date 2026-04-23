// ===== 动量守恒 =====
// 3 模式: 弹性碰撞 · 非弹性碰撞 · 完全非弹性碰撞
// 人教版选择性必修一 第1章

const MomentumConservation = {
    canvas: null, ctx: null, W: 0, H: 0,
    mode: 'elastic',        // 'elastic' | 'inelastic' | 'perfectly'
    _listeners: [],
    _resizeObs: null,
    _raf: null,
    _running: false,
    _phase: 'ready',        // 'ready' | 'running' | 'done'

    /* ── 物理参数 ── */
    m1: 3, m2: 2,           // kg
    v1i: 4, v2i: -2,        // m/s (初始速度，右为正)
    restitution: 0.5,       // 恢复系数 e (非弹性模式)
    v1f: 0, v2f: 0,         // 碰后速度

    /* ── 动画参数 ── */
    _t: 0,
    _x1: 0, _x2: 0,         // 当前 x 位置 (逻辑坐标, m)
    _v1: 0, _v2: 0,          // 当前速度
    _collided: false,
    _trackLen: 10,           // 轨道逻辑长度 (m)
    _blockW: 0.6,            // 物块宽度 (m)
    _lastTime: 0,

    /* ── 动量/动能记录 ── */
    _pBefore: { p1: 0, p2: 0, total: 0 },
    _pAfter:  { p1: 0, p2: 0, total: 0 },
    _kBefore: { k1: 0, k2: 0, total: 0 },
    _kAfter:  { k1: 0, k2: 0, total: 0 },

    _on(el, evt, fn, opts) {
        el.addEventListener(evt, fn, opts);
        this._listeners.push({ el, evt, fn, opts });
    },

    /* ═══════════════════ 生命周期 ═══════════════════ */
    init() {
        this.canvas = document.getElementById('mc-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this._resize();
        this._buildControls();
        this._injectEduPanel();

        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => { this._resize(); this._draw(); });
            this._resizeObs.observe(this.canvas.parentElement);
        }
        this._reset();
    },

    destroy() {
        this._stop();
        for (const l of this._listeners) l.el.removeEventListener(l.evt, l.fn, l.opts);
        this._listeners = [];
        if (this._resizeObs) { this._resizeObs.disconnect(); this._resizeObs = null; }
        const ctrl = document.getElementById('mc-controls');
        if (ctrl) ctrl.innerHTML = '';
        const edu = document.getElementById('mc-edu');
        if (edu) edu.innerHTML = '';
    },

    /* ═══════════════════ 尺寸 ═══════════════════ */
    _resize() {
        if (window.PhysicsZoom && window.PhysicsZoom.movedCanvas === this.canvas) return;
        const wrap = this.canvas.parentElement;
        if (!wrap) return;
        const w = wrap.clientWidth;
        if (w === 0) return;
        const h = Math.min(w * 0.55, 480);
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w; this.H = h;
    },

    /* ═══════════════════ 坐标映射 ═══════════════════ */
    _trackArea() {
        const pad = 40;
        return { x: pad, y: 40, w: this.W - pad * 2, h: this.H * 0.35 };
    },
    _barArea() {
        return { x: 40, y: this.H * 0.48, w: this.W - 80, h: this.H * 0.48 };
    },
    _logicToCanvas(lx) {
        const t = this._trackArea();
        return t.x + (lx / this._trackLen) * t.w;
    },

    /* ═══════════════════ 控件 ═══════════════════ */
    _buildControls() {
        const ctrl = document.getElementById('mc-controls');
        if (!ctrl) return;

        const self = this;
        const modes = [
            { key: 'elastic',    label: '⚡ 弹性碰撞' },
            { key: 'inelastic',  label: '💥 非弹性碰撞' },
            { key: 'perfectly',  label: '🧲 完全非弹性' }
        ];

        let html = '<div class="mc-mode-btns" role="group" aria-label="模式选择">';
        modes.forEach(m => {
            html += `<button class="mc-mode-btn${m.key === self.mode ? ' active' : ''}" data-mode="${m.key}">${m.label}</button>`;
        });
        html += '</div>';

        html += '<div class="mc-params">';
        html += this._sliderHTML('mc-m1', '物块 A 质量 m₁', 'kg', 1, 10, this.m1, 0.5);
        html += this._sliderHTML('mc-m2', '物块 B 质量 m₂', 'kg', 1, 10, this.m2, 0.5);
        html += this._sliderHTML('mc-v1', 'A 初速度 v₁', 'm/s', -8, 8, this.v1i, 0.5);
        html += this._sliderHTML('mc-v2', 'B 初速度 v₂', 'm/s', -8, 8, this.v2i, 0.5);
        html += '<div class="mc-e-row" id="mc-e-row">';
        html += this._sliderHTML('mc-e', '恢复系数 e', '', 0, 1, this.restitution, 0.05);
        html += '</div>';
        html += '</div>';

        html += '<div class="mc-actions">';
        html += '<button class="mc-btn mc-play" id="mc-play-btn">▶ 开始</button>';
        html += '<button class="mc-btn mc-reset" id="mc-reset-btn">↺ 重置</button>';
        html += '</div>';

        html += '<div id="mc-info" class="mc-info"></div>';
        ctrl.innerHTML = html;

        // 模式切换
        ctrl.querySelectorAll('.mc-mode-btn').forEach(btn => {
            this._on(btn, 'click', () => {
                self.mode = btn.dataset.mode;
                ctrl.querySelectorAll('.mc-mode-btn').forEach(b => b.classList.toggle('active', b === btn));
                self._updateERowVisibility();
                self._reset();
            });
        });

        // 滑块绑定
        const bindSlider = (id, prop, isFloat) => {
            const slider = document.getElementById(id);
            if (!slider) return;
            this._on(slider, 'input', () => {
                self[prop] = isFloat ? parseFloat(slider.value) : parseInt(slider.value);
                self._updateSliderLabel(id);
                self._reset();
            });
        };
        bindSlider('mc-m1', 'm1', true);
        bindSlider('mc-m2', 'm2', true);
        bindSlider('mc-v1', 'v1i', true);
        bindSlider('mc-v2', 'v2i', true);
        bindSlider('mc-e', 'restitution', true);

        // 播放/重置
        const playBtn = document.getElementById('mc-play-btn');
        const resetBtn = document.getElementById('mc-reset-btn');
        this._on(playBtn, 'click', () => {
            if (self._phase === 'done') self._reset();
            if (self._phase === 'ready') self._start();
            else if (self._running) self._pause();
            else self._resume();
        });
        this._on(resetBtn, 'click', () => self._reset());

        this._updateERowVisibility();
    },

    _sliderHTML(id, label, unit, min, max, val, step) {
        const display = unit ? `${val} ${unit}` : val;
        return `<div class="mc-slider-row">
            <label class="mc-label" id="${id}-lbl">${label} = <strong>${display}</strong></label>
            <input type="range" id="${id}" class="mc-slider" min="${min}" max="${max}" value="${val}" step="${step}">
        </div>`;
    },

    _updateSliderLabel(id) {
        const slider = document.getElementById(id);
        const lbl = document.getElementById(id + '-lbl');
        if (!slider || !lbl) return;
        const map = {
            'mc-m1': ['物块 A 质量 m₁', 'kg'],
            'mc-m2': ['物块 B 质量 m₂', 'kg'],
            'mc-v1': ['A 初速度 v₁', 'm/s'],
            'mc-v2': ['B 初速度 v₂', 'm/s'],
            'mc-e':  ['恢复系数 e', '']
        };
        const [name, unit] = map[id] || ['', ''];
        const v = parseFloat(slider.value);
        lbl.innerHTML = `${name} = <strong>${unit ? v + ' ' + unit : v}</strong>`;
    },

    _updateERowVisibility() {
        const row = document.getElementById('mc-e-row');
        if (row) row.style.display = this.mode === 'inelastic' ? '' : 'none';
    },

    /* ═══════════════════ 物理计算 ═══════════════════ */
    _calcPostCollision() {
        const { m1, m2, v1i, v2i, mode, restitution } = this;
        let v1f, v2f, e;

        if (mode === 'elastic') {
            e = 1;
        } else if (mode === 'perfectly') {
            e = 0;
        } else {
            e = restitution;
        }

        // 一般公式  v1' = ((m1 - e·m2)v1 + (1+e)m2·v2) / (m1+m2)
        //           v2' = ((m2 - e·m1)v2 + (1+e)m1·v1) / (m1+m2)
        const M = m1 + m2;
        v1f = ((m1 - e * m2) * v1i + (1 + e) * m2 * v2i) / M;
        v2f = ((m2 - e * m1) * v2i + (1 + e) * m1 * v1i) / M;

        this.v1f = v1f;
        this.v2f = v2f;

        this._pBefore = { p1: m1 * v1i, p2: m2 * v2i, total: m1 * v1i + m2 * v2i };
        this._pAfter  = { p1: m1 * v1f, p2: m2 * v2f, total: m1 * v1f + m2 * v2f };
        this._kBefore = { k1: 0.5 * m1 * v1i * v1i, k2: 0.5 * m2 * v2i * v2i, total: 0.5 * m1 * v1i * v1i + 0.5 * m2 * v2i * v2i };
        this._kAfter  = { k1: 0.5 * m1 * v1f * v1f, k2: 0.5 * m2 * v2f * v2f, total: 0.5 * m1 * v1f * v1f + 0.5 * m2 * v2f * v2f };
    },

    /* ═══════════════════ 动画控制 ═══════════════════ */
    _reset() {
        this._stop();
        this._phase = 'ready';
        this._collided = false;
        this._t = 0;
        // 初始位置
        this._x1 = this._trackLen * 0.3;
        this._x2 = this._trackLen * 0.7;
        this._v1 = this.v1i;
        this._v2 = this.v2i;
        this._calcPostCollision();
        this._updateInfo();
        this._draw();
        const btn = document.getElementById('mc-play-btn');
        if (btn) btn.textContent = '▶ 开始';
    },

    _start() {
        this._phase = 'running';
        this._running = true;
        this._lastTime = performance.now();
        const btn = document.getElementById('mc-play-btn');
        if (btn) btn.textContent = '⏸ 暂停';
        this._tick();
    },

    _pause() {
        this._running = false;
        const btn = document.getElementById('mc-play-btn');
        if (btn) btn.textContent = '▶ 继续';
    },

    _resume() {
        this._running = true;
        this._lastTime = performance.now();
        const btn = document.getElementById('mc-play-btn');
        if (btn) btn.textContent = '⏸ 暂停';
        this._tick();
    },

    _stop() {
        this._running = false;
        if (this._raf) { cancelAnimationFrame(this._raf); this._raf = null; }
    },

    _tick() {
        if (!this._running) return;
        const now = performance.now();
        const dt = Math.min((now - this._lastTime) / 1000, 0.05); // cap dt
        this._lastTime = now;

        // 更新位置
        this._x1 += this._v1 * dt;
        this._x2 += this._v2 * dt;

        // 碰撞检测
        if (!this._collided) {
            const gap = this._x2 - this._x1 - this._blockW;
            if (gap <= 0) {
                this._collided = true;
                // 修正穿透
                const overlap = -gap;
                this._x1 -= overlap * 0.5;
                this._x2 += overlap * 0.5;
                // 应用碰后速度
                this._v1 = this.v1f;
                this._v2 = this.v2f;
            }
        }

        // 边界检测 - 碰撞后物块超出轨道范围则结束
        if (this._collided) {
            const outLeft = this._x1 < -0.5 || this._x2 < -0.5;
            const outRight = this._x1 + this._blockW > this._trackLen + 0.5 || this._x2 + this._blockW > this._trackLen + 0.5;
            if (outLeft || outRight) {
                this._phase = 'done';
                this._stop();
                const btn = document.getElementById('mc-play-btn');
                if (btn) btn.textContent = '↺ 重来';
                this._draw();
                return;
            }
        }

        this._draw();
        this._raf = requestAnimationFrame(() => this._tick());
    },

    /* ═══════════════════ 信息面板 ═══════════════════ */
    _updateInfo() {
        const info = document.getElementById('mc-info');
        if (!info) return;
        const { m1, m2, v1i, v2i, v1f, v2f, _pBefore: pb, _pAfter: pa, _kBefore: kb, _kAfter: ka } = this;
        const modeLabel = { elastic: '弹性碰撞', inelastic: '非弹性碰撞', perfectly: '完全非弹性碰撞' }[this.mode];
        const kLoss = kb.total - ka.total;
        const kLossPct = kb.total > 0 ? (kLoss / kb.total * 100).toFixed(1) : '0';

        info.innerHTML = `
            <div class="mc-mode-tag">${modeLabel}</div>
            <div class="mc-data-row"><span>碰前：</span> v₁ = <strong>${v1i}</strong> m/s，v₂ = <strong>${v2i}</strong> m/s</div>
            <div class="mc-data-row"><span>碰后：</span> v₁' = <strong>${v1f.toFixed(2)}</strong> m/s，v₂' = <strong>${v2f.toFixed(2)}</strong> m/s</div>
            <div class="mc-data-row mc-momentum">动量守恒：p = m₁v₁+m₂v₂ = <strong>${pb.total.toFixed(1)}</strong> kg·m/s（碰前=碰后）</div>
            <div class="mc-data-row mc-energy">动能损失：ΔEk = <strong>${kLoss.toFixed(1)}</strong> J（${kLossPct}%）</div>`;
    },

    /* ═══════════════════ 绘图 ═══════════════════ */
    _draw() {
        const { ctx, W, H } = this;
        if (!ctx) return;
        ctx.clearRect(0, 0, W, H);

        this._drawTrack();
        this._drawBlocks();
        this._drawVelocityArrows();
        this._drawBarCharts();
    },

    _drawTrack() {
        const { ctx } = this;
        const t = this._trackArea();
        const trackY = t.y + t.h;

        // 轨道线
        ctx.save();
        ctx.strokeStyle = 'rgba(255,255,255,0.3)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(t.x, trackY);
        ctx.lineTo(t.x + t.w, trackY);
        ctx.stroke();

        // 刻度
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '12px ' + CF.sans;
        ctx.textAlign = 'center';
        for (let i = 0; i <= this._trackLen; i += 2) {
            const cx = this._logicToCanvas(i);
            ctx.beginPath();
            ctx.moveTo(cx, trackY);
            ctx.lineTo(cx, trackY + 6);
            ctx.stroke();
            ctx.fillText(i + 'm', cx, trackY + 16);
        }
        ctx.restore();
    },

    _drawBlocks() {
        const { ctx } = this;
        const t = this._trackArea();
        const trackY = t.y + t.h;

        // 物块尺寸（根据质量缩放）
        const bw1 = this._blockW / this._trackLen * t.w;
        const bw2 = this._blockW / this._trackLen * t.w;
        const baseH = t.h * 0.5;
        const bh1 = baseH * (0.6 + 0.4 * this.m1 / 10);
        const bh2 = baseH * (0.6 + 0.4 * this.m2 / 10);

        const cx1 = this._logicToCanvas(this._x1);
        const cx2 = this._logicToCanvas(this._x2);

        // 物块 A (蓝色)
        ctx.save();
        ctx.fillStyle = 'rgba(100, 149, 237, 0.85)';
        ctx.strokeStyle = '#6495ED';
        ctx.lineWidth = 2;
        const r = 4;
        this._roundRect(ctx, cx1, trackY - bh1, bw1, bh1, r);
        ctx.fill();
        ctx.stroke();
        // 标签
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 13px ' + CF.sans;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('A', cx1 + bw1 / 2, trackY - bh1 / 2 - 7);
        ctx.font = '12px ' + CF.sans;
        ctx.fillText(this.m1 + 'kg', cx1 + bw1 / 2, trackY - bh1 / 2 + 9);
        ctx.restore();

        // 物块 B (红色)
        ctx.save();
        ctx.fillStyle = 'rgba(235, 87, 87, 0.85)';
        ctx.strokeStyle = '#EB5757';
        ctx.lineWidth = 2;
        this._roundRect(ctx, cx2, trackY - bh2, bw2, bh2, r);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = '#fff';
        ctx.font = 'bold 13px ' + CF.sans;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText('B', cx2 + bw2 / 2, trackY - bh2 / 2 - 7);
        ctx.font = '12px ' + CF.sans;
        ctx.fillText(this.m2 + 'kg', cx2 + bw2 / 2, trackY - bh2 / 2 + 9);
        ctx.restore();
    },

    _drawVelocityArrows() {
        const { ctx } = this;
        const t = this._trackArea();
        const trackY = t.y + t.h;
        const bw = this._blockW / this._trackLen * t.w;
        const arrowScale = t.w / this._trackLen * 0.12;
        const arrowY = t.y + 12;

        // A 的速度箭头
        const cx1 = this._logicToCanvas(this._x1) + bw / 2;
        if (Math.abs(this._v1) > 0.01) {
            this._drawArrow(ctx, cx1, arrowY, cx1 + this._v1 * arrowScale, arrowY, '#6495ED', 2);
            ctx.save();
            ctx.fillStyle = '#6495ED';
            ctx.font = '12px ' + CF.sans;
            ctx.textAlign = 'center';
            ctx.fillText(`v₁=${this._v1.toFixed(1)}`, cx1 + this._v1 * arrowScale * 0.5, arrowY - 10);
            ctx.restore();
        }

        // B 的速度箭头
        const cx2 = this._logicToCanvas(this._x2) + bw / 2;
        if (Math.abs(this._v2) > 0.01) {
            this._drawArrow(ctx, cx2, arrowY, cx2 + this._v2 * arrowScale, arrowY, '#EB5757', 2);
            ctx.save();
            ctx.fillStyle = '#EB5757';
            ctx.font = '12px ' + CF.sans;
            ctx.textAlign = 'center';
            ctx.fillText(`v₂=${this._v2.toFixed(1)}`, cx2 + this._v2 * arrowScale * 0.5, arrowY - 10);
            ctx.restore();
        }
    },

    _drawBarCharts() {
        const { ctx, _pBefore: pb, _pAfter: pa, _kBefore: kb, _kAfter: ka } = this;
        const area = this._barArea();
        const midX = area.x + area.w * 0.5;
        const leftW = area.w * 0.45;
        const rightW = area.w * 0.45;

        // 标题
        ctx.save();
        ctx.fillStyle = 'rgba(255,255,255,0.6)';
        ctx.font = 'bold 12px ' + CF.sans;
        ctx.textAlign = 'center';
        ctx.fillText('动量 p (kg·m/s)', area.x + leftW * 0.5, area.y);
        ctx.fillText('动能 Ek (J)', midX + rightW * 0.5 + 20, area.y);
        ctx.restore();

        // 动量柱状图
        const pMax = Math.max(Math.abs(pb.p1), Math.abs(pb.p2), Math.abs(pb.total), Math.abs(pa.p1), Math.abs(pa.p2), Math.abs(pa.total), 1);
        this._drawBarGroup(area.x, area.y + 16, leftW, area.h - 20, [
            { label: 'p₁ 碰前', value: pb.p1, color: '#6495ED' },
            { label: 'p₂ 碰前', value: pb.p2, color: '#EB5757' },
            { label: '∑p 碰前', value: pb.total, color: '#2ED573' },
            { label: 'p₁ 碰后', value: pa.p1, color: '#6495ED88' },
            { label: 'p₂ 碰后', value: pa.p2, color: '#EB575788' },
            { label: '∑p 碰后', value: pa.total, color: '#2ED57388' }
        ], pMax);

        // 动能柱状图
        const kMax = Math.max(kb.k1, kb.k2, kb.total, ka.k1, ka.k2, ka.total, 1);
        this._drawBarGroup(midX + 20, area.y + 16, rightW, area.h - 20, [
            { label: 'Ek₁ 碰前', value: kb.k1, color: '#6495ED' },
            { label: 'Ek₂ 碰前', value: kb.k2, color: '#EB5757' },
            { label: '∑Ek 碰前', value: kb.total, color: '#FFD93D' },
            { label: 'Ek₁ 碰后', value: ka.k1, color: '#6495ED88' },
            { label: 'Ek₂ 碰后', value: ka.k2, color: '#EB575788' },
            { label: '∑Ek 碰后', value: ka.total, color: '#FFD93D88' }
        ], kMax);
    },

    _drawBarGroup(x, y, w, h, bars, maxVal) {
        const { ctx } = this;
        const n = bars.length;
        const barW = Math.min(w / n * 0.7, 28);
        const gap = (w - barW * n) / (n + 1);
        const baseY = y + h * 0.6; // 零线 (允许负值)
        const scaleH = h * 0.5;

        // 零线
        ctx.save();
        ctx.strokeStyle = 'rgba(255,255,255,0.15)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(x, baseY);
        ctx.lineTo(x + w, baseY);
        ctx.stroke();

        bars.forEach((bar, i) => {
            const bx = x + gap + i * (barW + gap);
            const barH = (bar.value / maxVal) * scaleH;

            // 柱
            ctx.fillStyle = bar.color;
            if (barH >= 0) {
                this._roundRect(ctx, bx, baseY - barH, barW, barH, 2);
            } else {
                this._roundRect(ctx, bx, baseY, barW, -barH, 2);
            }
            ctx.fill();

            // 数值
            ctx.fillStyle = 'rgba(255,255,255,0.8)';
            ctx.font = '12px ' + CF.sans;
            ctx.textAlign = 'center';
            const valY = barH >= 0 ? baseY - barH - 4 : baseY - barH + 10;
            ctx.fillText(bar.value.toFixed(1), bx + barW / 2, valY);

            // 标签
            ctx.fillStyle = 'rgba(255,255,255,0.5)';
            ctx.font = '12px ' + CF.sans;
            ctx.save();
            ctx.translate(bx + barW / 2, baseY + 8);
            ctx.rotate(-Math.PI / 6);
            ctx.textAlign = 'right';
            ctx.fillText(bar.label, 0, 0);
            ctx.restore();
        });
        ctx.restore();
    },

    /* ═══════════════════ 绘图工具 ═══════════════════ */
    _drawArrow(ctx, x1, y1, x2, y2, color, lineW) {
        const len = Math.hypot(x2 - x1, y2 - y1);
        if (len < 2) return;
        const headLen = Math.min(10, len * 0.3);
        const angle = Math.atan2(y2 - y1, x2 - x1);

        ctx.save();
        ctx.strokeStyle = color;
        ctx.fillStyle = color;
        ctx.lineWidth = lineW;
        ctx.beginPath();
        ctx.moveTo(x1, y1);
        ctx.lineTo(x2 - headLen * Math.cos(angle), y2 - headLen * Math.sin(angle));
        ctx.stroke();

        ctx.beginPath();
        ctx.moveTo(x2, y2);
        ctx.lineTo(x2 - headLen * Math.cos(angle - 0.35), y2 - headLen * Math.sin(angle - 0.35));
        ctx.lineTo(x2 - headLen * Math.cos(angle + 0.35), y2 - headLen * Math.sin(angle + 0.35));
        ctx.closePath();
        ctx.fill();
        ctx.restore();
    },

    _roundRect(ctx, x, y, w, h, r) {
        if (w < 0) { x += w; w = -w; }
        if (h < 0) { y += h; h = -h; }
        r = Math.min(r, w / 2, h / 2);
        ctx.beginPath();
        ctx.moveTo(x + r, y);
        ctx.lineTo(x + w - r, y);
        ctx.quadraticCurveTo(x + w, y, x + w, y + r);
        ctx.lineTo(x + w, y + h - r);
        ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
        ctx.lineTo(x + r, y + h);
        ctx.quadraticCurveTo(x, y + h, x, y + h - r);
        ctx.lineTo(x, y + r);
        ctx.quadraticCurveTo(x, y, x + r, y);
        ctx.closePath();
    },

    /* ═══════════════════ 教育面板 ═══════════════════ */
    _injectEduPanel() {
        const edu = document.getElementById('mc-edu');
        if (!edu) return;
        edu.innerHTML = `
            <h4>📚 动量守恒定律</h4>
            <p>一个系统不受外力（或所受合外力为零）时，系统总动量守恒：</p>
            <p class="mc-formula">m₁v₁ + m₂v₂ = m₁v₁' + m₂v₂'</p>
            <ul>
                <li><strong>弹性碰撞</strong>（e = 1）：动量、动能均守恒。v₁' = [(m₁−m₂)v₁ + 2m₂v₂]/(m₁+m₂)</li>
                <li><strong>完全非弹性碰撞</strong>（e = 0）：两物体碰后粘合，共速 v' = (m₁v₁+m₂v₂)/(m₁+m₂)，动能损失最大</li>
                <li><strong>非弹性碰撞</strong>（0 < e < 1）：恢复系数 e = |v₂'−v₁'| / |v₁−v₂|</li>
            </ul>
            <p class="mc-tip">💡 调整质量和速度，观察碰前碰后动量守恒与动能变化</p>`;
    }
};

window.MomentumConservation = MomentumConservation;

function initMomentumConservation() {
    MomentumConservation.init();
}
window.initMomentumConservation = initMomentumConservation;

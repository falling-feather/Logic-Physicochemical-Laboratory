/* ============================================================
 * Codevis · 首页 - 代码雨 + 粒子网络 + 打字机
 * ============================================================ */
(function (global) {
    'use strict';

    const RAIN_CHARS = '01{}();=<>+-*/!?&|[]_:$#@%^~`αβγδλπΣΩ→←↑↓';
    const RAIN_FONT_SIZE = 16;
    const RAIN_TICK_MS = 70;
    const PARTICLE_DENSITY = 22000;

    const CvHome = {
        _canvas: null, _ctx: null,
        _w: 0, _h: 0, _dpr: 1,
        _particles: [],
        _columns: [],
        _lastRainTick: 0,
        _raf: 0,
        _reduce: false,
        _inited: false,
        _typeTimer: null,

        init() {
            if (this._inited) return;
            this._inited = true;

            this._canvas = document.getElementById('cv-home-canvas');
            if (!this._canvas) { this._inited = false; return; }

            this._reduce = !!(window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches);
            this._ctx = this._canvas.getContext('2d');

            this._resize();
            this._initParticles();
            this._initRain();

            window.addEventListener('resize', this._onResize);

            if (this._reduce) {
                this._drawOnce();
            } else {
                this._lastRainTick = performance.now();
                this._loop();
            }

            this._startTypewriter();
            this._bindFeatureGlow();
        },

        destroy() {
            this._inited = false;
            cancelAnimationFrame(this._raf);
            this._raf = 0;
            if (this._typeTimer) { clearTimeout(this._typeTimer); this._typeTimer = null; }
            window.removeEventListener('resize', this._onResize);
            this._particles = [];
            this._columns = [];
        },

        _bindFeatureGlow() {
            const cards = document.querySelectorAll('.cv-feature');
            cards.forEach((c) => {
                c.addEventListener('mousemove', (e) => {
                    const rect = c.getBoundingClientRect();
                    const mx = ((e.clientX - rect.left) / rect.width) * 100;
                    const my = ((e.clientY - rect.top) / rect.height) * 100;
                    c.style.setProperty('--cv-mx', mx + '%');
                    c.style.setProperty('--cv-my', my + '%');
                });
            });
        },

        _onResize() {
            if (!CvHome._inited || !CvHome._canvas) return;
            CvHome._resize();
            CvHome._initParticles();
            CvHome._initRain();
            if (CvHome._reduce) CvHome._drawOnce();
        },

        _resize() {
            const rect = this._canvas.getBoundingClientRect();
            this._dpr = Math.min(window.devicePixelRatio || 1, 2);
            this._w = rect.width;
            this._h = rect.height;
            this._canvas.width = Math.max(1, Math.floor(rect.width * this._dpr));
            this._canvas.height = Math.max(1, Math.floor(rect.height * this._dpr));
            this._ctx.setTransform(this._dpr, 0, 0, this._dpr, 0, 0);
        },

        // ─── 粒子网络 ───
        _initParticles() {
            const count = Math.max(28, Math.floor((this._w * this._h) / PARTICLE_DENSITY));
            this._particles = [];
            for (let i = 0; i < count; i++) {
                this._particles.push({
                    x: Math.random() * this._w,
                    y: Math.random() * this._h,
                    vx: (Math.random() - 0.5) * 0.28,
                    vy: (Math.random() - 0.5) * 0.28,
                    r: 0.8 + Math.random() * 1.4
                });
            }
        },

        _drawParticles() {
            const ctx = this._ctx;
            const ps = this._particles;
            for (let i = 0; i < ps.length; i++) {
                const p = ps[i];
                p.x += p.vx; p.y += p.vy;
                if (p.x < 0 || p.x > this._w) p.vx *= -1;
                if (p.y < 0 || p.y > this._h) p.vy *= -1;
            }
            const max = 130;
            ctx.lineWidth = 0.6;
            for (let i = 0; i < ps.length; i++) {
                for (let j = i + 1; j < ps.length; j++) {
                    const a = ps[i], b = ps[j];
                    const dx = a.x - b.x, dy = a.y - b.y;
                    const d2 = dx * dx + dy * dy;
                    if (d2 < max * max) {
                        const op = (1 - Math.sqrt(d2) / max) * 0.32;
                        ctx.strokeStyle = `rgba(0, 212, 255, ${op})`;
                        ctx.beginPath();
                        ctx.moveTo(a.x, a.y);
                        ctx.lineTo(b.x, b.y);
                        ctx.stroke();
                    }
                }
            }
            for (let i = 0; i < ps.length; i++) {
                const p = ps[i];
                ctx.fillStyle = 'rgba(0, 212, 255, 0.85)';
                ctx.beginPath();
                ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
                ctx.fill();
            }
        },

        // ─── 代码雨 ───
        _initRain() {
            const cols = Math.ceil(this._w / RAIN_FONT_SIZE);
            this._columns = new Array(cols);
            for (let i = 0; i < cols; i++) {
                this._columns[i] = {
                    y: Math.floor(Math.random() * (this._h / RAIN_FONT_SIZE)) - 5,
                    char: this._randChar()
                };
            }
        },

        _randChar() {
            return RAIN_CHARS.charAt(Math.floor(Math.random() * RAIN_CHARS.length));
        },

        _drawRain(now) {
            const ctx = this._ctx;
            if (now - this._lastRainTick > RAIN_TICK_MS) {
                this._lastRainTick = now;
                for (let i = 0; i < this._columns.length; i++) {
                    const c = this._columns[i];
                    c.y += 1;
                    if (Math.random() < 0.25) c.char = this._randChar();
                    if (c.y * RAIN_FONT_SIZE > this._h && Math.random() < 0.025) {
                        c.y = -Math.floor(Math.random() * 30);
                        c.char = this._randChar();
                    }
                }
            }

            ctx.font = `${RAIN_FONT_SIZE}px "JetBrains Mono", Consolas, monospace`;
            ctx.textBaseline = 'top';
            const tail = 14;
            for (let i = 0; i < this._columns.length; i++) {
                const c = this._columns[i];
                const x = i * RAIN_FONT_SIZE;
                for (let k = 0; k < tail; k++) {
                    const yRow = c.y - k;
                    if (yRow < 0) continue;
                    const y = yRow * RAIN_FONT_SIZE;
                    if (y > this._h) continue;
                    const opacity = k === 0 ? 0.85 : Math.max(0, 0.45 * (1 - k / tail));
                    if (opacity < 0.04) continue;
                    const ch = (k === 0)
                        ? c.char
                        : RAIN_CHARS.charAt(((i * 7 + k * 13 + yRow) % RAIN_CHARS.length + RAIN_CHARS.length) % RAIN_CHARS.length);
                    if (k === 0)        ctx.fillStyle = `rgba(180, 250, 255, ${opacity})`;
                    else if (k < 3)     ctx.fillStyle = `rgba(0, 212, 255, ${opacity})`;
                    else                ctx.fillStyle = `rgba(56, 189, 248, ${opacity})`;
                    ctx.fillText(ch, x, y);
                }
            }
        },

        // ─── 主循环 ───
        _loop() {
            const now = performance.now();
            const ctx = this._ctx;
            // 淡淡擦除（造拖尾感）
            ctx.fillStyle = 'rgba(5, 11, 20, 0.18)';
            ctx.fillRect(0, 0, this._w, this._h);

            ctx.save();
            ctx.globalAlpha = 0.45;
            this._drawRain(now);
            ctx.restore();

            ctx.save();
            ctx.globalAlpha = 0.85;
            this._drawParticles();
            ctx.restore();

            this._raf = requestAnimationFrame(() => this._loop());
        },

        _drawOnce() {
            const ctx = this._ctx;
            ctx.clearRect(0, 0, this._w, this._h);
            ctx.save();
            ctx.globalAlpha = 0.3;
            ctx.font = `${RAIN_FONT_SIZE}px "JetBrains Mono", Consolas, monospace`;
            ctx.textBaseline = 'top';
            ctx.fillStyle = 'rgba(0, 212, 255, 0.45)';
            for (let i = 0; i < this._columns.length; i++) {
                const c = this._columns[i];
                const y = Math.max(0, c.y) * RAIN_FONT_SIZE;
                if (y < this._h) ctx.fillText(c.char, i * RAIN_FONT_SIZE, y);
            }
            ctx.restore();
            ctx.save();
            ctx.globalAlpha = 0.7;
            this._drawParticles();
            ctx.restore();
        },

        // ─── 打字机 ───
        _startTypewriter() {
            const els = document.querySelectorAll('[data-typewriter]');
            if (!els.length) return;

            els.forEach(el => {
                el.dataset.full = el.textContent;
                el.textContent = '';
                el.classList.add('cv-typewriter');
            });

            if (this._reduce) {
                els.forEach(el => {
                    el.textContent = el.dataset.full;
                    el.classList.add('cv-typewriter--done');
                });
                return;
            }

            const queue = Array.from(els).map(el => ({
                el,
                text: el.dataset.full,
                delay: parseInt(el.dataset.typewriterDelay || '0', 10),
                speed: parseInt(el.dataset.typewriterSpeed || '75', 10)
            }));

            const runOne = (i) => {
                if (i >= queue.length) return;
                const { el, text, delay, speed } = queue[i];
                this._typeTimer = setTimeout(() => {
                    let idx = 0;
                    const step = () => {
                        if (idx > text.length) {
                            el.classList.add('cv-typewriter--done');
                            // 非最后一个：完成后隐藏光标，让下一个接力
                            if (i < queue.length - 1) el.classList.add('cv-typewriter--no-caret');
                            runOne(i + 1);
                            return;
                        }
                        el.textContent = text.slice(0, idx);
                        idx++;
                        this._typeTimer = setTimeout(step, speed);
                    };
                    step();
                }, delay);
            };
            runOne(0);
        }
    };

    global.CvHome = CvHome;
})(window);

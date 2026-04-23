// ===== 首页逻辑 =====
const _isReturningVisitor = !!(window.__englabCache && window.__englabCache.returnVisitor);

// ===== 粒子网络系统 =====
const ParticleNetwork = {
    canvas: null, ctx: null,
    particles: [],
    mouse: { x: -1000, y: -1000 },
    maxDist: 140,
    W: 0, H: 0,
    running: false,
    _resizeObs: null,
    _hidden: false,

    // ── FPS 自适应 ──
    _fpsFrames: 0,
    _fpsTime: 0,
    _fps: 60,
    _targetCount: 0,   // 期望粒子数
    _maxParticles: 80,

    // ── 空间网格 ──
    _grid: null,
    _gridCols: 0,
    _gridRows: 0,
    _cellSize: 0,

    // ── OffscreenCanvas Worker ──
    _worker: null,
    _useWorker: false,
    _dpr: 1,

    init() {
        this.canvas = document.getElementById('particle-network');
        if (!this.canvas) return;
        this._maxParticles = (typeof _isLowEnd !== 'undefined' && _isLowEnd) ? 40 : 80;
        this._cellSize = this.maxDist;

        // 优先使用 OffscreenCanvas + Web Worker（释放主线程）
        if (typeof this.canvas.transferControlToOffscreen === 'function' && typeof Worker !== 'undefined') {
            try {
                this._initWorker();
                return;
            } catch (e) {
                console.warn('[ParticleNetwork] OffscreenCanvas 回退:', e);
            }
        }
        this._initDirect();
    },

    /** OffscreenCanvas + Web Worker 渲染路径 */
    _initWorker() {
        const lowEnd = typeof _isLowEnd !== 'undefined' && _isLowEnd;
        this._dpr = lowEnd ? Math.min(window.devicePixelRatio || 1, 1.5) : (window.devicePixelRatio || 1);
        const offscreen = this.canvas.transferControlToOffscreen();
        this._worker = new Worker('shared/workers/particle-worker.js');
        this._useWorker = true;

        const w = window.innerWidth, h = window.innerHeight;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.W = w; this.H = h;

        this._worker.postMessage({
            type: 'init', canvas: offscreen,
            width: w, height: h, dpr: this._dpr,
            maxParticles: this._maxParticles
        }, [offscreen]);

        this.running = true;

        // 转发鼠标位置
        document.addEventListener('mousemove', e => {
            this.mouse.x = e.clientX;
            this.mouse.y = e.clientY;
            if (this._worker) this._worker.postMessage({ type: 'mouse', x: e.clientX, y: e.clientY });
        });

        // 转发尺寸变化
        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => {
                const nw = window.innerWidth, nh = window.innerHeight;
                this.canvas.style.width = nw + 'px';
                this.canvas.style.height = nh + 'px';
                this.W = nw; this.H = nh;
                if (this._worker) this._worker.postMessage({ type: 'resize', width: nw, height: nh, dpr: this._dpr });
            });
            this._resizeObs.observe(this.canvas.parentElement);
        }

        // 转发可见性状态
        document.addEventListener('visibilitychange', () => {
            if (this._worker) this._worker.postMessage({ type: 'visibility', hidden: document.hidden });
        });
    },

    /** 主线程直接渲染路径（OffscreenCanvas 不可用时的回退） */
    _initDirect() {
        this.ctx = this.canvas.getContext('2d');
        this.resize();

        if (typeof ResizeObserver !== 'undefined') {
            this._resizeObs = new ResizeObserver(() => { this.resize(); this.spawn(); });
            this._resizeObs.observe(this.canvas.parentElement);
        } else {
            window.addEventListener('resize', () => { this.resize(); this.spawn(); });
        }

        document.addEventListener('mousemove', e => {
            this.mouse.x = e.clientX;
            this.mouse.y = e.clientY;
        });

        // Page Visibility — 标签页隐藏时暂停
        document.addEventListener('visibilitychange', () => {
            this._hidden = document.hidden;
            if (!this._hidden && this.running) {
                this._fpsTime = performance.now();
                this._fpsFrames = 0;
            }
        });

        this.spawn();
        this.running = true;
        this._fpsTime = performance.now();
        this.loop();
    },

    destroy() {
        this.running = false;
        if (this._worker) {
            this._worker.postMessage({ type: 'destroy' });
            this._worker.terminate();
            this._worker = null;
        }
        if (this._resizeObs) { this._resizeObs.disconnect(); this._resizeObs = null; }
    },

    resize() {
        const lowEnd = typeof _isLowEnd !== 'undefined' && _isLowEnd;
        const dpr = lowEnd ? Math.min(window.devicePixelRatio || 1, 1.5) : (window.devicePixelRatio || 1);
        const w = window.innerWidth;
        const h = window.innerHeight;
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        this.W = w;
        this.H = h;
        this._gridCols = Math.ceil(w / this._cellSize) + 1;
        this._gridRows = Math.ceil(h / this._cellSize) + 1;
    },

    spawn() {
        const area = this.W * this.H;
        this._targetCount = Math.min(Math.floor(area / 18000), this._maxParticles);
        this.particles = [];
        for (let i = 0; i < this._targetCount; i++) {
            this.particles.push({
                x: Math.random() * this.W,
                y: Math.random() * this.H,
                vx: (Math.random() - 0.5) * 0.4,
                vy: (Math.random() - 0.5) * 0.4,
                r: 1 + Math.random() * 1.5
            });
        }
    },

    /** 基于实际帧率自适应调整粒子数量 */
    _adaptParticleCount() {
        this._fpsFrames++;
        const now = performance.now();
        const elapsed = now - this._fpsTime;
        if (elapsed < 1000) return; // 每秒检查一次

        this._fps = Math.round(this._fpsFrames * 1000 / elapsed);
        this._fpsFrames = 0;
        this._fpsTime = now;

        const particles = this.particles;
        if (this._fps < 25 && particles.length > 20) {
            // 帧率过低 → 减少 20% 粒子
            const remove = Math.max(2, Math.floor(particles.length * 0.2));
            particles.splice(particles.length - remove, remove);
            this._targetCount = particles.length;
        } else if (this._fps > 50 && particles.length < this._targetCount) {
            // 帧率充裕且低于目标 → 补充粒子
            const add = Math.min(4, this._targetCount - particles.length);
            for (let i = 0; i < add; i++) {
                particles.push({
                    x: Math.random() * this.W,
                    y: Math.random() * this.H,
                    vx: (Math.random() - 0.5) * 0.4,
                    vy: (Math.random() - 0.5) * 0.4,
                    r: 1 + Math.random() * 1.5
                });
            }
        }
    },

    /** 构建空间网格，将粒子分配到 cellSize×cellSize 的格子中 */
    _buildGrid() {
        const cols = this._gridCols, rows = this._gridRows;
        const cs = this._cellSize;
        const grid = new Array(cols * rows);
        for (let k = 0; k < grid.length; k++) grid[k] = [];
        const particles = this.particles;
        for (let i = 0; i < particles.length; i++) {
            const c = Math.min(cols - 1, (particles[i].x / cs) | 0);
            const r = Math.min(rows - 1, (particles[i].y / cs) | 0);
            grid[r * cols + c].push(i);
        }
        this._grid = grid;
    },

    loop() {
        if (!this.running) return;
        requestAnimationFrame(() => this.loop());

        // 标签页隐藏时跳过渲染
        if (this._hidden) return;

        this._adaptParticleCount();

        const { ctx, particles, mouse, maxDist, W, H } = this;
        const maxDist2 = maxDist * maxDist;
        const mouseDist = maxDist * 1.5;
        const mouseDist2 = mouseDist * mouseDist;
        ctx.clearRect(0, 0, W, H);

        // Update & draw particles
        ctx.fillStyle = 'rgba(91,141,206,0.4)';
        ctx.beginPath();
        for (const p of particles) {
            p.x += p.vx;
            p.y += p.vy;
            if (p.x < 0 || p.x > W) p.vx *= -1;
            if (p.y < 0 || p.y > H) p.vy *= -1;

            // Mouse attraction (use squared distance)
            const dx = mouse.x - p.x, dy = mouse.y - p.y;
            const dist2 = dx * dx + dy * dy;
            if (dist2 < 40000) { // 200^2
                p.vx += dx * 0.00005;
                p.vy += dy * 0.00005;
            }

            ctx.moveTo(p.x + p.r, p.y);
            ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        }
        ctx.fill();

        // ── 基于空间网格的连线（替代 O(n²) 暴力搜索）──
        this._buildGrid();
        const grid = this._grid;
        const cols = this._gridCols, rows = this._gridRows;
        const cs = this._cellSize;

        ctx.lineWidth = 0.5;
        const bins = [[], [], [], []]; // 4 opacity bins

        for (let i = 0; i < particles.length; i++) {
            const pi = particles[i];
            const gc = Math.min(cols - 1, (pi.x / cs) | 0);
            const gr = Math.min(rows - 1, (pi.y / cs) | 0);

            // 检查自身及相邻 3x3 格子
            for (let dr = -1; dr <= 1; dr++) {
                const nr = gr + dr;
                if (nr < 0 || nr >= rows) continue;
                for (let dc = -1; dc <= 1; dc++) {
                    const nc = gc + dc;
                    if (nc < 0 || nc >= cols) continue;
                    const cell = grid[nr * cols + nc];
                    for (let k = 0; k < cell.length; k++) {
                        const j = cell[k];
                        if (j <= i) continue; // 避免重复
                        const pj = particles[j];
                        const dx = pi.x - pj.x;
                        const dy = pi.y - pj.y;
                        const d2 = dx * dx + dy * dy;
                        if (d2 < maxDist2) {
                            const ratio = 1 - Math.sqrt(d2) / maxDist;
                            const bin = Math.min(3, (ratio * 4) | 0);
                            bins[bin].push(i, j);
                        }
                    }
                }
            }
            // Mouse connections
            const mdx = mouse.x - pi.x;
            const mdy = mouse.y - pi.y;
            const md2 = mdx * mdx + mdy * mdy;
            if (md2 < mouseDist2) {
                const ratio = 1 - Math.sqrt(md2) / mouseDist;
                const bin = Math.min(3, (ratio * 4) | 0);
                bins[bin].push(i, -1);
            }
        }

        // Draw each opacity bin as a single batched path
        const alphas = [0.03, 0.06, 0.09, 0.12];
        for (let b = 0; b < 4; b++) {
            const arr = bins[b];
            if (!arr.length) continue;
            ctx.strokeStyle = `rgba(91,141,206,${alphas[b]})`;
            ctx.beginPath();
            for (let k = 0; k < arr.length; k += 2) {
                const pi = arr[k], pj = arr[k + 1];
                ctx.moveTo(particles[pi].x, particles[pi].y);
                if (pj === -1) {
                    ctx.lineTo(mouse.x, mouse.y);
                } else {
                    ctx.lineTo(particles[pj].x, particles[pj].y);
                }
            }
            ctx.stroke();
        }
    }
};

// ===== 打字机标语 =====
const TaglineTyper = {
    phrases: [
        '探索科学的星辰大海',
        'Visualize. Interact. Understand.',
        '数学 · 物理 · 化学 · 算法 · 生物',
        'f(x) = curiosity × imagination',
        'E = mc² | F = ma | PV = nRT',
        '从抽象到直觉，从公式到画面',
        'Made by Fallingfeather'
    ],
    idx: 0,
    el: null,
    charIdx: 0,
    deleting: false,
    timeout: null,

    init() {
        this.el = document.getElementById('tagline-text');
        if (!this.el) return;
        if (this.timeout) clearTimeout(this.timeout);
        this.el.textContent = '';
        this.charIdx = 0;
        this.deleting = false;
        this.tick();
    },

    tick() {
        const phrase = this.phrases[this.idx];
        if (!this.deleting) {
            this.charIdx++;
            this.el.textContent = phrase.slice(0, this.charIdx);
            if (this.charIdx >= phrase.length) {
                this.timeout = setTimeout(() => { this.deleting = true; this.tick(); }, 3000);
                return;
            }
            this.timeout = setTimeout(() => this.tick(), 60 + Math.random() * 40);
        } else {
            this.charIdx--;
            this.el.textContent = phrase.slice(0, this.charIdx);
            if (this.charIdx <= 0) {
                this.deleting = false;
                this.idx = (this.idx + 1) % this.phrases.length;
                this.timeout = setTimeout(() => this.tick(), 400);
                return;
            }
            this.timeout = setTimeout(() => this.tick(), 25);
        }
    }
};

// ===== HUD 数据流 =====
const HUDData = {
    _interval: null,
    init() {
        const left = document.getElementById('hud-data-left');
        const right = document.getElementById('hud-data-right');
        if (!left || !right) return;

        const dataL = ['SYS.OK', 'LAT: 39.9°N', 'FREQ: 60Hz', 'MEM: 512MB', 'CPU: IDLE', 'NET: ●', 'NODES: 16', 'δt: 16ms'];
        const dataR = ['v' + new Date().getFullYear() + '.06', 'π≈3.1416', 'e≈2.7183', 'φ≈1.6180', 'i²=−1', 'ℏ=1.055e-34', '∇·E=ρ/ε₀', 'Σ=∞'];

        left.innerHTML = dataL.map(d => `<span>${d}</span>`).join('<br>');
        right.innerHTML = dataR.map(d => `<span>${d}</span>`).join('<br>');

        // Periodically flash random data items
        if (this._interval) clearInterval(this._interval);
        this._interval = setInterval(() => {
            const targets = [left, right];
            const target = targets[Math.floor(Math.random() * 2)];
            const spans = target.querySelectorAll('span');
            if (spans.length === 0) return;
            const span = spans[Math.floor(Math.random() * spans.length)];
            span.style.color = 'rgba(91,141,206,0.7)';
            setTimeout(() => { span.style.color = ''; }, 400);
        }, 1500);
    }
};

// ===== 独立轨道卫星系统 =====
const SatelliteSystem = {
    isRunning: true,
    startTime: Date.now(),
    satellites: [],
    orbit: null,

    // 每颗行星拥有独立轨道参数
    orbits: [
        { radiusX: 320, radiusY: 200, tiltX: 65, tiltZ: 25,  period: 18000, dir:  1 },
        { radiusX: 420, radiusY: 260, tiltX: 60, tiltZ: -15, period: 25000, dir: -1 },
        { radiusX: 520, radiusY: 320, tiltX: 70, tiltZ: 35,  period: 32000, dir:  1 },
        { radiusX: 450, radiusY: 280, tiltX: 55, tiltZ: -30, period: 22000, dir: -1 },
        { radiusX: 380, radiusY: 240, tiltX: 62, tiltZ: 18,  period: 28000, dir:  1 }
    ],

    // 移动端缩放轨道半径
    getScaledOrbits: function() {
        const w = window.innerWidth;
        if (w <= 480) {
            return this.orbits.map(o => ({
                ...o, radiusX: o.radiusX * 0.58, radiusY: o.radiusY * 0.58
            }));
        } else if (w <= 768) {
            return this.orbits.map(o => ({
                ...o, radiusX: o.radiusX * 0.78, radiusY: o.radiusY * 0.78
            }));
        }
        return this.orbits;
    },

    perspective: 1200,
    _lastFrameTime: 0,

    init: function() {
        this.satellites = document.querySelectorAll('.satellite');
        this.orbit = document.getElementById('satellites-orbit');

        if (!this.orbit || this.satellites.length === 0) return;

        this.startTime = Date.now();
        this.isRunning = true;
        this._lastFrameTime = 0;
        this.loop();
    },

    loop: function() {
        if (!this.isRunning) return;
        requestAnimationFrame(this.loop.bind(this));

        // 低端设备帧率限制：约 30fps（~33ms 间隔）
        const perfNow = performance.now();
        const minInterval = (typeof _isLowEnd !== 'undefined' && _isLowEnd) ? 33 : 0;
        if (minInterval > 0 && perfNow - this._lastFrameTime < minInterval) return;
        this._lastFrameTime = perfNow;

        const now = Date.now();
        const toRad = Math.PI / 180;
        const scaledOrbits = this.getScaledOrbits();

        this.satellites.forEach((sat, index) => {
            if (sat.classList.contains('focusing')) return;
            if (index >= scaledOrbits.length) return;

            const orb = scaledOrbits[index];
            const elapsed = (now - this.startTime) % orb.period;
            const angle = ((elapsed / orb.period) * 360 * orb.dir) * toRad;

            const x_orbit = orb.radiusX * Math.cos(angle);
            const y_orbit = orb.radiusY * Math.sin(angle);

            const cosTiltX = Math.cos(orb.tiltX * toRad);
            const sinTiltX = Math.sin(orb.tiltX * toRad);
            const cosTiltZ = Math.cos(orb.tiltZ * toRad);
            const sinTiltZ = Math.sin(orb.tiltZ * toRad);

            const y_rotX = y_orbit * cosTiltX;
            const z_rotX = y_orbit * sinTiltX;

            const x_final = x_orbit * cosTiltZ - y_rotX * sinTiltZ;
            const y_final = x_orbit * sinTiltZ + y_rotX * cosTiltZ;
            const z_final = z_rotX;

            const scale = this.perspective / (this.perspective - z_final);

            sat.style.transform = `translate(-50%, -50%) translate3d(${x_final}px, ${y_final}px, 0) scale(${scale})`;
            sat.style.zIndex = z_final > 0 ? 20 : 5;
            // 远近深度透视：远处更暗
            sat.style.opacity = Math.max(0.4, Math.min(1, 0.45 + (scale - 0.7) * 1.6));
        });
    }
};

// ===== 模块选择动画 =====
function selectModule(target) {
    const mainStar = document.getElementById('main-star');
    const satellite = document.querySelector(`.satellite[data-target="${target}"]`);
    const allSatellites = document.querySelectorAll('.satellite');
    const homePage = document.getElementById('page-home');

    if (!mainStar || !satellite || !homePage) {
        navigate(target);
        return;
    }

    // Set transition origin from satellite position for radial wipe
    const satRect = satellite.getBoundingClientRect();
    if (typeof Router !== 'undefined') {
        Router.transitionOrigin = {
            x: ((satRect.left + satRect.width / 2) / window.innerWidth) * 100,
            y: ((satRect.top + satRect.height / 2) / window.innerHeight) * 100
        };
    }

    emitClickParticles(satellite);
    SatelliteSystem.isRunning = false;
    mainStar.classList.add('shake');

    setTimeout(() => {
        mainStar.classList.remove('shake');
        satellite.classList.add('focusing');

        allSatellites.forEach(sat => {
            if (sat !== satellite) {
                sat.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
                sat.style.opacity = '0';
                sat.style.transform += ' scale(0)';
            }
        });

        mainStar.classList.add('fading-out');
        mainStar.style.transition = 'opacity 0.5s ease-out, transform 0.5s ease-out';
        mainStar.style.opacity = '0';
        mainStar.style.transform = 'scale(0.5)';

        document.querySelectorAll('.orbit-path').forEach(o => {
            o.style.transition = 'opacity 0.4s ease-out';
            o.style.opacity = '0';
        });

        const tagline = document.getElementById('home-tagline');
        if (tagline) { tagline.style.transition = 'opacity 0.3s'; tagline.style.opacity = '0'; }

        setTimeout(() => {
            satellite.style.transition = 'transform 0.8s cubic-bezier(0.4, 0, 0.2, 1)';
            satellite.style.zIndex = '1000';
            satellite.style.transform = 'translate(-50%, -50%) translate3d(0px, 0px, 0) scale(4)';

            const icon = satellite.querySelector('.satellite-icon');
            if (icon) { icon.style.transition = 'transform 0.8s'; icon.style.transform = 'scale(1)'; }

            const labelContainer = satellite.querySelector('.satellite-label-container');
            if (labelContainer) { labelContainer.style.transition = 'opacity 0.3s'; labelContainer.style.opacity = '0'; }

            const colors = {
                mathematics: 'rgba(91,141,206,0.25)',
                physics: 'rgba(139,111,192,0.25)',
                chemistry: 'rgba(77,158,126,0.25)',
                algorithms: 'rgba(196,121,58,0.25)',
                biology: 'rgba(58,158,143,0.25)'
            };
            homePage.style.transition = 'background 0.8s ease-out';
            homePage.style.background = `radial-gradient(ellipse at center, ${colors[target] || 'rgba(91,141,206,0.25)'} 0%, #08090e 100%)`;

            setTimeout(() => {
                // Skip router animation — selectModule already provides visual departure
                Router.navigateTo(target, false);
                setTimeout(() => resetHomeState(allSatellites, mainStar, homePage, satellite, tagline, icon, labelContainer), 300);
            }, 800);
        }, 400);
    }, 250);
}

function resetHomeState(allSatellites, mainStar, homePage, satellite, tagline, icon, labelContainer) {
    SatelliteSystem.startTime = Date.now();
    SatelliteSystem.isRunning = true;

    allSatellites.forEach(sat => {
        sat.classList.remove('focusing');
        sat.style.transition = ''; sat.style.opacity = ''; sat.style.transform = ''; sat.style.zIndex = '';
    });

    mainStar.classList.remove('fading-out');
    mainStar.style.transition = ''; mainStar.style.opacity = ''; mainStar.style.transform = ''; mainStar.style.zIndex = '10';

    document.querySelectorAll('.orbit-path').forEach(o => { o.style.transition = ''; o.style.opacity = ''; });
    homePage.style.transition = ''; homePage.style.background = '';

    if (tagline) { tagline.style.transition = ''; tagline.style.opacity = ''; }
    if (icon) icon.style.transform = '';
    if (labelContainer) { labelContainer.style.transition = ''; labelContainer.style.opacity = ''; }
}

// ===== 点击粒子效果 =====
function emitClickParticles(element) {
    const rect = element.getBoundingClientRect();
    const cx = rect.left + rect.width / 2;
    const cy = rect.top + rect.height / 2;

    for (let i = 0; i < 14; i++) {
        const p = document.createElement('div');
        p.className = 'cursor-particle';
        const angle = (Math.PI * 2 / 14) * i + (Math.random() - 0.5) * 0.6;
        const dist = 25 + Math.random() * 50;
        p.style.left = (cx + Math.cos(angle) * dist) + 'px';
        p.style.top  = (cy + Math.sin(angle) * dist) + 'px';
        const size = 2 + Math.random() * 3;
        p.style.width = size + 'px';
        p.style.height = size + 'px';
        document.body.appendChild(p);
        setTimeout(() => p.remove(), 850);
    }
}

// ===== 多层星空背景 =====
function createStars() {
    const lowEnd = typeof _isLowEnd !== 'undefined' && _isLowEnd;
    const returning = typeof _isReturningVisitor !== 'undefined' && _isReturningVisitor;
    const layers = [
        { id: 'star-layer-1', count: lowEnd ? 40 : (returning ? 70 : 90), classes: ['small'] },
        { id: 'star-layer-2', count: lowEnd ? 18 : (returning ? 36 : 50), classes: ['small', 'medium'] },
        { id: 'star-layer-3', count: lowEnd ? 8 : (returning ? 14 : 20), classes: ['medium', 'large', 'bright'] }
    ];

    layers.forEach(layer => {
        const el = document.getElementById(layer.id);
        if (!el) return;
        el.innerHTML = '';

        for (let i = 0; i < layer.count; i++) {
            const s = document.createElement('div');
            const cls = layer.classes[Math.floor(Math.random() * layer.classes.length)];
            s.className = 'star ' + cls;
            s.style.left = Math.random() * 100 + '%';
            s.style.top  = Math.random() * 100 + '%';
            s.style.animationDelay    = (Math.random() * 6) + 's';
            s.style.animationDuration = (2.5 + Math.random() * 5) + 's';
            el.appendChild(s);
        }
    });
}

// ===== 视差背景跟踪 =====
function initParallax() {
    if (window.__homeParallaxBound) return;
    window.__homeParallaxBound = true;

    const depths = [0.015, 0.04, 0.09]; // 三层视差深度
    const layerEls = [
        document.getElementById('star-layer-1'),
        document.getElementById('star-layer-2'),
        document.getElementById('star-layer-3')
    ];

    function applyParallax(clientX, clientY) {
        const x = (clientX / window.innerWidth  - 0.5) * 2;
        const y = (clientY / window.innerHeight - 0.5) * 2;

        layerEls.forEach((layer, i) => {
            if (!layer) return;
            const d = depths[i];
            layer.style.transform = `translate(${x * d * 100}px, ${y * d * 100}px)`;
        });
    }

    document.addEventListener('mousemove', e => applyParallax(e.clientX, e.clientY));
    document.addEventListener('touchmove', e => {
        const t = e.touches[0];
        applyParallax(t.clientX, t.clientY);
    }, { passive: true });
}

// ===== 眼睛跟随 + 眨眼 =====
function initEyeTracking() {
    if (window.__homeEyeTrackingBound) return;
    window.__homeEyeTrackingBound = true;

    const main = document.getElementById('main-star');
    const pl = document.getElementById('pupil-left');
    const pr = document.getElementById('pupil-right');
    if (!main) return;

    function trackEye(clientX, clientY) {
        const rect = main.getBoundingClientRect();
        const cx = rect.left + rect.width / 2;
        const cy = rect.top  + rect.height / 2;
        const dx = clientX - cx, dy = clientY - cy;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const ang  = Math.atan2(dy, dx);
        const maxMove = 5;
        const ratio = Math.min(dist / 250, 1);
        const mx = Math.cos(ang) * ratio * maxMove;
        const my = Math.sin(ang) * ratio * maxMove;
        if (pl) pl.style.transform = `translate(calc(-50% + ${mx}px), calc(-50% + ${my}px))`;
        if (pr) pr.style.transform = `translate(calc(-50% + ${mx}px), calc(-50% + ${my}px))`;
    }

    document.addEventListener('mousemove', e => trackEye(e.clientX, e.clientY));
    document.addEventListener('touchmove', e => {
        const t = e.touches[0];
        trackEye(t.clientX, t.clientY);
    }, { passive: true });

    // 不规则眨眼
    function scheduleBlink() {
        const delay = 2500 + Math.random() * 4500;
        setTimeout(() => {
            const eyes = document.querySelectorAll('.eye');
            eyes.forEach(e => e.classList.add('blink'));
            setTimeout(() => {
                eyes.forEach(e => e.classList.remove('blink'));
                // 偶尔双眨
                if (Math.random() < 0.25) {
                    setTimeout(() => {
                        eyes.forEach(e => e.classList.add('blink'));
                        setTimeout(() => eyes.forEach(e => e.classList.remove('blink')), 140);
                    }, 200);
                }
            }, 140);
            scheduleBlink();
        }, delay);
    }
    scheduleBlink();
}

// ===== 流星系统 =====
function initShootingStars() {
    if (window.__homeShootingStarsBound) return;
    window.__homeShootingStarsBound = true;

    const container = document.getElementById('shooting-stars');
    if (!container) return;

    function spawnStar() {
        const star = document.createElement('div');
        star.className = 'shooting-star';

        const startX  = Math.random() * window.innerWidth * 0.7;
        const startY  = Math.random() * window.innerHeight * 0.35;
        const angle   = 25 + Math.random() * 35;   // 25–60°
        const distance = 200 + Math.random() * 350;
        const duration = 0.5 + Math.random() * 0.9;

        star.style.left  = startX + 'px';
        star.style.top   = startY + 'px';
        star.style.width = (55 + Math.random() * 65) + 'px';
        star.style.transform = `rotate(${angle}deg)`;
        star.style.setProperty('--tx', (Math.cos(angle * Math.PI/180) * distance) + 'px');
        star.style.setProperty('--ty', (Math.sin(angle * Math.PI/180) * distance) + 'px');
        star.style.setProperty('--duration', duration + 's');

        container.appendChild(star);
        setTimeout(() => star.remove(), duration * 1000 + 150);

        // 下一颗
        setTimeout(spawnStar, 3500 + Math.random() * 7000);
    }

    setTimeout(spawnStar, 2000 + Math.random() * 3000);
}

// ===== 首页初始化（分阶段，避免首次加载卡顿）=====
// 低端设备检测：硬件线程数 ≤ 4 或内存 ≤ 4GB 时启用简化模式
const _isLowEnd = (navigator.hardwareConcurrency || 8) <= 4 ||
                  (navigator.deviceMemory && navigator.deviceMemory <= 4);

function initHome() {
    // ── Phase 1 (同步): 先确保首页可见可交互 ──
    SatelliteSystem.init();
    TaglineTyper.init();
    if (window.__loadProgress) window.__loadProgress(85);

    // 其余动效延后：先让页面出来，再逐步补视觉细节
    requestAnimationFrame(function () {
        if (window.__loadProgress) window.__loadProgress(95);

        const scheduleEnhancements = window.requestIdleCallback
            ? (cb) => window.requestIdleCallback(cb, { timeout: _isReturningVisitor ? 450 : 300 })
            : (cb) => setTimeout(cb, _isReturningVisitor ? 180 : 120);

        scheduleEnhancements(function () {
            createStars();
            initParallax();
            if (!_isLowEnd && !_isReturningVisitor) {
                ParticleNetwork.init();
                initShootingStars();
            } else if (!_isLowEnd) {
                setTimeout(function () {
                    ParticleNetwork.init();
                    initShootingStars();
                }, 350);
            }
            HUDData.init();
            initEyeTracking();
        });
    });
}

// 导出全局
window.selectModule = selectModule;
window.SatelliteSystem = SatelliteSystem;


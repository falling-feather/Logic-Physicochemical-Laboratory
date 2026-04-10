// ===== 力学模拟引擎 =====

const PhysicsSim = {
    canvas: null,
    ctx: null,
    balls: [],
    running: false,
    paused: false,
    lastTime: 0,
    fpsFrames: 0,
    fpsTime: 0,
    currentFps: 0,

    // 可调参数
    gravity: 980,
    restitution: 0.75,
    friction: 0.10,
    ballRadius: 16,

    // 拖拽发射
    dragStart: null,
    dragEnd: null,
    isDragging: false,

    // 颜色调色板（紫色系，匹配物理页主题）
    palette: [
        '#8b6fc0', '#a78bfa', '#7c3aed', '#6366f1',
        '#818cf8', '#c084fc', '#e879f9', '#a855f7'
    ],

    init() {
        this.canvas = document.getElementById('physics-canvas');
        if (!this.canvas) return;

        this.ctx = this.canvas.getContext('2d');
        this.resizeCanvas();
        this.bindControls();
        this.bindCanvas();

        window.addEventListener('resize', () => this.resizeCanvas());
    },

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
    },

    bindControls() {
        const gravSlider = document.getElementById('gravity-slider');
        const restSlider = document.getElementById('restitution-slider');
        const fricSlider = document.getElementById('friction-slider');
        const radSlider = document.getElementById('radius-slider');
        const clearBtn = document.getElementById('physics-clear');
        const pauseBtn = document.getElementById('physics-pause');

        if (gravSlider) gravSlider.addEventListener('input', () => {
            this.gravity = +gravSlider.value;
            document.getElementById('gravity-value').textContent = gravSlider.value;
        });

        if (restSlider) restSlider.addEventListener('input', () => {
            this.restitution = +restSlider.value / 100;
            document.getElementById('restitution-value').textContent = this.restitution.toFixed(2);
        });

        if (fricSlider) fricSlider.addEventListener('input', () => {
            this.friction = +fricSlider.value / 100;
            document.getElementById('friction-value').textContent = this.friction.toFixed(2);
        });

        if (radSlider) radSlider.addEventListener('input', () => {
            this.ballRadius = +radSlider.value;
            document.getElementById('radius-value').textContent = radSlider.value;
        });

        if (clearBtn) clearBtn.addEventListener('click', () => {
            this.balls = [];
            this.updateStats();
        });

        if (pauseBtn) pauseBtn.addEventListener('click', () => {
            this.paused = !this.paused;
            pauseBtn.textContent = this.paused ? '继续' : '暂停';
        });
    },

    bindCanvas() {
        const getPos = (e) => {
            const rect = this.canvas.getBoundingClientRect();
            const clientX = e.touches ? e.touches[0].clientX : e.clientX;
            const clientY = e.touches ? e.touches[0].clientY : e.clientY;
            return { x: clientX - rect.left, y: clientY - rect.top };
        };

        // Mouse
        this.canvas.addEventListener('mousedown', (e) => {
            this.dragStart = getPos(e);
            this.isDragging = true;
        });

        this.canvas.addEventListener('mousemove', (e) => {
            if (this.isDragging) this.dragEnd = getPos(e);
        });

        this.canvas.addEventListener('mouseup', (e) => {
            if (this.isDragging && this.dragStart) {
                const end = getPos(e);
                this.launchBall(this.dragStart, end);
            }
            this.isDragging = false;
            this.dragStart = null;
            this.dragEnd = null;
        });

        // Touch
        this.canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            this.dragStart = getPos(e);
            this.isDragging = true;
        }, { passive: false });

        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            if (this.isDragging) this.dragEnd = getPos(e);
        }, { passive: false });

        this.canvas.addEventListener('touchend', (e) => {
            if (this.isDragging && this.dragStart) {
                const end = this.dragEnd || this.dragStart;
                this.launchBall(this.dragStart, end);
            }
            this.isDragging = false;
            this.dragStart = null;
            this.dragEnd = null;
        });
    },

    launchBall(start, end) {
        const dx = start.x - end.x;
        const dy = start.y - end.y;
        const speed = Math.sqrt(dx * dx + dy * dy) * 3;
        const angle = Math.atan2(dy, dx);

        // Cap at 100 balls for performance
        if (this.balls.length >= 100) {
            this.balls.shift();
        }

        this.balls.push({
            x: start.x,
            y: start.y,
            vx: Math.cos(angle) * speed,
            vy: Math.sin(angle) * speed,
            r: this.ballRadius,
            color: this.palette[Math.floor(Math.random() * this.palette.length)],
            trail: []
        });

        this.updateStats();
    },

    start() {
        if (this.running) return;
        this.running = true;
        this.lastTime = performance.now();
        this.fpsTime = this.lastTime;
        this.loop();
    },

    stop() {
        this.running = false;
    },

    loop() {
        if (!this.running) return;
        requestAnimationFrame(() => this.loop());

        const now = performance.now();
        const dt = Math.min((now - this.lastTime) / 1000, 0.032); // Cap at ~30fps min
        this.lastTime = now;

        // FPS counter
        this.fpsFrames++;
        if (now - this.fpsTime >= 500) {
            this.currentFps = Math.round(this.fpsFrames / ((now - this.fpsTime) / 1000));
            this.fpsFrames = 0;
            this.fpsTime = now;
            const el = document.getElementById('physics-fps');
            if (el) el.textContent = this.currentFps;
        }

        if (!this.paused) this.update(dt);
        this.render();
    },

    update(dt) {
        const g = this.gravity;
        const rest = this.restitution;
        const fric = this.friction;

        for (let i = 0; i < this.balls.length; i++) {
            const b = this.balls[i];

            // Gravity
            b.vy += g * dt;

            // Apply friction (air resistance)
            b.vx *= (1 - fric * dt);
            b.vy *= (1 - fric * 0.3 * dt);

            // Move
            b.x += b.vx * dt;
            b.y += b.vy * dt;

            // Trail (store last 8 positions)
            b.trail.push({ x: b.x, y: b.y });
            if (b.trail.length > 8) b.trail.shift();

            // Wall collisions
            if (b.x - b.r < 0) {
                b.x = b.r;
                b.vx = Math.abs(b.vx) * rest;
            }
            if (b.x + b.r > this.W) {
                b.x = this.W - b.r;
                b.vx = -Math.abs(b.vx) * rest;
            }
            if (b.y + b.r > this.H) {
                b.y = this.H - b.r;
                b.vy = -Math.abs(b.vy) * rest;

                // Friction on ground
                b.vx *= (1 - fric);

                // Stop micro-bouncing
                if (Math.abs(b.vy) < 15) {
                    b.vy = 0;
                    b.y = this.H - b.r;
                }
            }
            if (b.y - b.r < 0) {
                b.y = b.r;
                b.vy = Math.abs(b.vy) * rest;
            }

            // Ball-to-ball collisions
            for (let j = i + 1; j < this.balls.length; j++) {
                this.resolveCollision(b, this.balls[j]);
            }
        }
    },

    resolveCollision(a, b) {
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const dist = Math.sqrt(dx * dx + dy * dy);
        const minDist = a.r + b.r;

        if (dist >= minDist || dist === 0) return;

        // Normalize
        const nx = dx / dist;
        const ny = dy / dist;

        // Separate
        const overlap = (minDist - dist) / 2;
        a.x -= nx * overlap;
        a.y -= ny * overlap;
        b.x += nx * overlap;
        b.y += ny * overlap;

        // Relative velocity along normal
        const dvx = a.vx - b.vx;
        const dvy = a.vy - b.vy;
        const relVn = dvx * nx + dvy * ny;

        if (relVn < 0) return; // Moving apart

        // Equal mass elastic collision with restitution
        const impulse = relVn * (1 + this.restitution) / 2;
        a.vx -= impulse * nx;
        a.vy -= impulse * ny;
        b.vx += impulse * nx;
        b.vy += impulse * ny;
    },

    render() {
        const ctx = this.ctx;
        ctx.clearRect(0, 0, this.W, this.H);

        // Subtle grid
        ctx.strokeStyle = 'rgba(255,255,255,0.03)';
        ctx.lineWidth = 1;
        const gridSize = 40;
        for (let x = gridSize; x < this.W; x += gridSize) {
            ctx.beginPath();
            ctx.moveTo(x, 0);
            ctx.lineTo(x, this.H);
            ctx.stroke();
        }
        for (let y = gridSize; y < this.H; y += gridSize) {
            ctx.beginPath();
            ctx.moveTo(0, y);
            ctx.lineTo(this.W, y);
            ctx.stroke();
        }

        // Ground line
        ctx.strokeStyle = 'rgba(139,111,192,0.3)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(0, this.H - 1);
        ctx.lineTo(this.W, this.H - 1);
        ctx.stroke();

        // Balls
        for (const b of this.balls) {
            // Trail
            if (b.trail.length > 1) {
                const speed = Math.sqrt(b.vx * b.vx + b.vy * b.vy);
                if (speed > 30) {
                    ctx.beginPath();
                    ctx.moveTo(b.trail[0].x, b.trail[0].y);
                    for (let t = 1; t < b.trail.length; t++) {
                        ctx.lineTo(b.trail[t].x, b.trail[t].y);
                    }
                    ctx.strokeStyle = b.color + '30';
                    ctx.lineWidth = b.r * 0.6;
                    ctx.lineCap = 'round';
                    ctx.stroke();
                }
            }

            // Ball body
            const gradient = ctx.createRadialGradient(
                b.x - b.r * 0.3, b.y - b.r * 0.3, 0,
                b.x, b.y, b.r
            );
            gradient.addColorStop(0, b.color + 'ff');
            gradient.addColorStop(0.7, b.color + 'cc');
            gradient.addColorStop(1, b.color + '66');

            ctx.beginPath();
            ctx.arc(b.x, b.y, b.r, 0, Math.PI * 2);
            ctx.fillStyle = gradient;
            ctx.fill();

            // Highlight
            ctx.beginPath();
            ctx.arc(b.x - b.r * 0.25, b.y - b.r * 0.25, b.r * 0.35, 0, Math.PI * 2);
            ctx.fillStyle = 'rgba(255,255,255,0.2)';
            ctx.fill();

            // Shadow on ground
            if (b.y + b.r < this.H) {
                const shadowY = this.H - 2;
                const proximity = 1 - ((shadowY - b.y) / this.H);
                const shadowR = b.r * (0.5 + proximity * 0.5);
                ctx.beginPath();
                ctx.ellipse(b.x, shadowY, shadowR, 3, 0, 0, Math.PI * 2);
                ctx.fillStyle = `rgba(0,0,0,${proximity * 0.15})`;
                ctx.fill();
            }
        }

        // Drag arrow
        if (this.isDragging && this.dragStart && this.dragEnd) {
            const dx = this.dragStart.x - this.dragEnd.x;
            const dy = this.dragStart.y - this.dragEnd.y;
            const len = Math.sqrt(dx * dx + dy * dy);

            if (len > 5) {
                ctx.save();
                ctx.strokeStyle = 'rgba(167,139,250,0.6)';
                ctx.lineWidth = 2;
                ctx.setLineDash([6, 4]);
                ctx.beginPath();
                ctx.moveTo(this.dragStart.x, this.dragStart.y);
                ctx.lineTo(this.dragStart.x + dx, this.dragStart.y + dy);
                ctx.stroke();
                ctx.setLineDash([]);

                // Arrowhead
                const angle = Math.atan2(dy, dx);
                const aLen = 10;
                ctx.fillStyle = 'rgba(167,139,250,0.6)';
                ctx.beginPath();
                ctx.moveTo(this.dragStart.x + dx, this.dragStart.y + dy);
                ctx.lineTo(
                    this.dragStart.x + dx - aLen * Math.cos(angle - 0.4),
                    this.dragStart.y + dy - aLen * Math.sin(angle - 0.4)
                );
                ctx.lineTo(
                    this.dragStart.x + dx - aLen * Math.cos(angle + 0.4),
                    this.dragStart.y + dy - aLen * Math.sin(angle + 0.4)
                );
                ctx.fill();
                ctx.restore();

                // Preview ball
                ctx.beginPath();
                ctx.arc(this.dragStart.x, this.dragStart.y, this.ballRadius, 0, Math.PI * 2);
                ctx.strokeStyle = 'rgba(167,139,250,0.5)';
                ctx.lineWidth = 2;
                ctx.stroke();
            }
        }

        // Empty state hint
        if (this.balls.length === 0 && !this.isDragging) {
            ctx.fillStyle = 'rgba(255,255,255,0.15)';
            ctx.font = '16px "Inter", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('在画布上拖拽来发射小球', this.W / 2, this.H / 2 - 10);
            ctx.font = '13px "Inter", sans-serif';
            ctx.fillStyle = 'rgba(255,255,255,0.08)';
            ctx.fillText('拖拽方向和距离决定发射速度', this.W / 2, this.H / 2 + 15);
        }
    },

    updateStats() {
        const el = document.getElementById('ball-count');
        if (el) el.textContent = this.balls.length;
    }
};

// ===== 物理页初始化 =====
function initPhysics() {
    PhysicsSim.init();
    PhysicsSim.start();
}

window.PhysicsSim = PhysicsSim;

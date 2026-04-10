// ===== Data Structures Visualization =====
const DataStructVis = {
    canvas: null,
    ctx: null,
    W: 0, H: 0,
    mode: 'stack', // stack | queue | bst
    animId: null,
    speed: 500,

    // Stack
    stack: [],
    stackMax: 10,

    // Queue
    queue: [],
    queueMax: 10,

    // BST
    bstRoot: null,

    // Animation queue
    animQueue: [],
    animating: false,
    highlight: null, // { index, color } or { nodeId, color }

    init() {
        this.canvas = document.getElementById('ds-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.resize();
        this.bindControls();
        this.draw();
        window.addEventListener('resize', () => { this.resize(); this.draw(); });
    },

    resize() {
        const wrap = this.canvas.parentElement;
        const w = wrap.clientWidth;
        const h = Math.min(w * 0.65, 420);
        this.canvas.width = w * devicePixelRatio;
        this.canvas.height = h * devicePixelRatio;
        this.canvas.style.width = w + 'px';
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(devicePixelRatio, 0, 0, devicePixelRatio, 0, 0);
        this.W = w;
        this.H = h;
    },

    bindControls() {
        // Mode buttons
        document.querySelectorAll('.ds-mode-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                document.querySelectorAll('.ds-mode-btn').forEach(b => b.classList.remove('active'));
                btn.classList.add('active');
                this.mode = btn.dataset.mode;
                this.updatePanelVisibility();
                this.draw();
            });
        });

        // Stack controls
        const pushBtn = document.getElementById('ds-push');
        if (pushBtn) pushBtn.addEventListener('click', () => this.pushStack());
        const popBtn = document.getElementById('ds-pop');
        if (popBtn) popBtn.addEventListener('click', () => this.popStack());

        // Queue controls
        const enqBtn = document.getElementById('ds-enqueue');
        if (enqBtn) enqBtn.addEventListener('click', () => this.enqueue());
        const deqBtn = document.getElementById('ds-dequeue');
        if (deqBtn) deqBtn.addEventListener('click', () => this.dequeue());

        // BST controls
        const insertBtn = document.getElementById('ds-bst-insert');
        if (insertBtn) insertBtn.addEventListener('click', () => this.bstInsert());
        const searchBtn = document.getElementById('ds-bst-search');
        if (searchBtn) searchBtn.addEventListener('click', () => this.bstSearch());
        const clearBtn = document.getElementById('ds-bst-clear');
        if (clearBtn) clearBtn.addEventListener('click', () => {
            this.bstRoot = null;
            this.draw();
            this.updateInfo('BST 已清空');
        });
        const presetBtn = document.getElementById('ds-bst-preset');
        if (presetBtn) presetBtn.addEventListener('click', () => this.bstPreset());

        // Traversal buttons
        document.querySelectorAll('.ds-trav-btn').forEach(btn => {
            btn.addEventListener('click', () => this.bstTraverse(btn.dataset.trav));
        });

        // Speed slider
        const speedSlider = document.getElementById('ds-speed');
        if (speedSlider) speedSlider.addEventListener('input', () => {
            this.speed = 1200 - parseInt(speedSlider.value);
        });
    },

    updatePanelVisibility() {
        const stackP = document.getElementById('ds-stack-panel');
        const queueP = document.getElementById('ds-queue-panel');
        const bstP = document.getElementById('ds-bst-panel');
        if (stackP) stackP.style.display = this.mode === 'stack' ? 'flex' : 'none';
        if (queueP) queueP.style.display = this.mode === 'queue' ? 'flex' : 'none';
        if (bstP) bstP.style.display = this.mode === 'bst' ? 'flex' : 'none';
    },

    randomVal() {
        return Math.floor(Math.random() * 99) + 1;
    },

    // ========== STACK ==========
    pushStack() {
        if (this.stack.length >= this.stackMax) {
            this.updateInfo('栈已满! (最大 ' + this.stackMax + ')');
            return;
        }
        const val = this.randomVal();
        this.stack.push({ val, animY: -40 });
        this.updateInfo(`Push(${val}) — 栈大小: ${this.stack.length}`);
        this.animateEntry('stack', this.stack.length - 1);
    },

    popStack() {
        if (this.stack.length === 0) {
            this.updateInfo('栈为空!');
            return;
        }
        const item = this.stack[this.stack.length - 1];
        this.highlight = { index: this.stack.length - 1, color: '#c4793a' };
        this.draw();
        setTimeout(() => {
            this.stack.pop();
            this.highlight = null;
            this.updateInfo(`Pop() → ${item.val} — 栈大小: ${this.stack.length}`);
            this.draw();
        }, this.speed);
    },

    // ========== QUEUE ==========
    enqueue() {
        if (this.queue.length >= this.queueMax) {
            this.updateInfo('队列已满! (最大 ' + this.queueMax + ')');
            return;
        }
        const val = this.randomVal();
        this.queue.push({ val, animX: 40 });
        this.updateInfo(`Enqueue(${val}) — 队列大小: ${this.queue.length}`);
        this.animateEntry('queue', this.queue.length - 1);
    },

    dequeue() {
        if (this.queue.length === 0) {
            this.updateInfo('队列为空!');
            return;
        }
        this.highlight = { index: 0, color: '#c4793a' };
        this.draw();
        const item = this.queue[0];
        setTimeout(() => {
            this.queue.shift();
            this.highlight = null;
            this.updateInfo(`Dequeue() → ${item.val} — 队列大小: ${this.queue.length}`);
            this.draw();
        }, this.speed);
    },

    animateEntry(type, idx) {
        let frame = 0;
        const frames = 15;
        const loop = () => {
            frame++;
            if (type === 'stack') {
                this.stack[idx].animY = -40 * (1 - frame / frames);
            } else {
                this.queue[idx].animX = 40 * (1 - frame / frames);
            }
            this.draw();
            if (frame < frames) requestAnimationFrame(loop);
        };
        requestAnimationFrame(loop);
    },

    // ========== BST ==========
    bstInsert() {
        const input = document.getElementById('ds-bst-val');
        let val = input ? parseInt(input.value) : this.randomVal();
        if (isNaN(val)) val = this.randomVal();
        if (input) input.value = '';

        this.bstRoot = this._bstInsert(this.bstRoot, val, 0);
        this.updateInfo(`BST Insert(${val})`);
        this.highlight = { val, color: '#4d9e7e' };
        this.draw();
        setTimeout(() => { this.highlight = null; this.draw(); }, this.speed);
    },

    _bstInsert(node, val, depth) {
        if (!node) return { val, left: null, right: null, depth };
        if (val < node.val) node.left = this._bstInsert(node.left, val, depth + 1);
        else if (val > node.val) node.right = this._bstInsert(node.right, val, depth + 1);
        return node;
    },

    bstSearch() {
        const input = document.getElementById('ds-bst-val');
        let val = input ? parseInt(input.value) : 0;
        if (isNaN(val)) { this.updateInfo('请输入搜索值'); return; }

        // Animate search path
        const path = [];
        let node = this.bstRoot;
        while (node) {
            path.push(node.val);
            if (val === node.val) break;
            else if (val < node.val) node = node.left;
            else node = node.right;
        }

        let i = 0;
        const step = () => {
            if (i < path.length) {
                this.highlight = { val: path[i], color: i === path.length - 1 && path[i] === val ? '#4d9e7e' : '#c4793a' };
                this.draw();
                i++;
                setTimeout(step, this.speed);
            } else {
                const found = node && node.val === val;
                this.updateInfo(found ? `找到 ${val}! 路径: ${path.join(' → ')}` : `未找到 ${val}, 路径: ${path.join(' → ')}`);
                setTimeout(() => { this.highlight = null; this.draw(); }, this.speed);
            }
        };
        step();
    },

    bstPreset() {
        this.bstRoot = null;
        const vals = [50, 30, 70, 20, 40, 60, 80, 10, 35, 55, 75];
        vals.forEach(v => { this.bstRoot = this._bstInsert(this.bstRoot, v, 0); });
        this.updateInfo('加载预设 BST: [' + vals.join(', ') + ']');
        this.draw();
    },

    bstTraverse(type) {
        if (!this.bstRoot) { this.updateInfo('BST 为空'); return; }
        const result = [];
        const collect = (node) => {
            if (!node) return;
            if (type === 'pre') { result.push(node.val); collect(node.left); collect(node.right); }
            else if (type === 'in') { collect(node.left); result.push(node.val); collect(node.right); }
            else { collect(node.left); collect(node.right); result.push(node.val); }
        };
        collect(this.bstRoot);

        // Animate traversal
        let i = 0;
        const names = { pre: '前序', in: '中序', post: '后序' };
        const step = () => {
            if (i < result.length) {
                this.highlight = { val: result[i], color: '#5b8dce' };
                this.draw();
                i++;
                setTimeout(step, this.speed);
            } else {
                this.highlight = null;
                this.draw();
                this.updateInfo(`${names[type]}遍历: ${result.join(' → ')}`);
            }
        };
        step();
    },

    // ========== DRAW ==========
    draw() {
        const { ctx, W, H } = this;
        ctx.clearRect(0, 0, W, H);
        ctx.fillStyle = '#0d1017';
        ctx.fillRect(0, 0, W, H);

        if (this.mode === 'stack') this.drawStack();
        else if (this.mode === 'queue') this.drawQueue();
        else this.drawBST();
    },

    drawStack() {
        const { ctx, W, H } = this;
        const boxW = 60;
        const boxH = 34;
        const baseX = W / 2 - boxW / 2;
        const baseY = H - 40;

        // Container outline
        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.lineWidth = 1.5;
        const containerH = this.stackMax * boxH + 10;
        ctx.strokeRect(baseX - 5, baseY - containerH - 5, boxW + 10, containerH + 15);

        // "Bottom" label
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '11px "Inter", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('底部', baseX + boxW / 2, baseY + 16);

        // Top pointer
        if (this.stack.length > 0) {
            const topY = baseY - this.stack.length * boxH;
            ctx.fillStyle = '#c4793a';
            ctx.font = '12px "JetBrains Mono", monospace';
            ctx.textAlign = 'right';
            ctx.fillText('TOP →', baseX - 12, topY + boxH / 2 + 4);
        }

        // Draw stack elements
        this.stack.forEach((item, i) => {
            const y = baseY - (i + 1) * boxH + (item.animY || 0);
            const isHighlight = this.highlight && this.highlight.index === i;
            const color = isHighlight ? this.highlight.color : '#c4793a';
            const alpha = isHighlight ? 0.3 : 0.1;

            ctx.fillStyle = `rgba(${this.hexRgb(color)},${alpha})`;
            ctx.fillRect(baseX, y, boxW, boxH - 2);
            ctx.strokeStyle = color;
            ctx.lineWidth = isHighlight ? 2 : 1;
            ctx.strokeRect(baseX, y, boxW, boxH - 2);

            ctx.fillStyle = '#fff';
            ctx.font = 'bold 14px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(item.val, baseX + boxW / 2, y + (boxH - 2) / 2);
        });

        // LIFO label
        ctx.fillStyle = 'rgba(255,255,255,0.2)';
        ctx.font = '13px "Inter", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('LIFO — 后进先出', W / 2, 24);
    },

    drawQueue() {
        const { ctx, W, H } = this;
        const boxW = 50;
        const boxH = 44;
        const midY = H / 2;
        const startX = (W - this.queueMax * (boxW + 4)) / 2;

        // Container
        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(startX - 6, midY - boxH / 2 - 6, this.queueMax * (boxW + 4) + 8, boxH + 12);

        // Front / Rear labels
        ctx.fillStyle = 'rgba(255,255,255,0.3)';
        ctx.font = '11px "Inter", sans-serif';
        ctx.textAlign = 'center';
        if (this.queue.length > 0) {
            ctx.fillStyle = '#4d9e7e';
            ctx.fillText('↑ FRONT', startX + boxW / 2, midY + boxH / 2 + 20);
            ctx.fillStyle = '#5b8dce';
            ctx.fillText('↑ REAR', startX + (this.queue.length - 1) * (boxW + 4) + boxW / 2, midY + boxH / 2 + 20);
        }

        // Draw queue elements
        this.queue.forEach((item, i) => {
            const x = startX + i * (boxW + 4) + (item.animX || 0);
            const isHighlight = this.highlight && this.highlight.index === i;
            const color = i === 0 ? '#4d9e7e' : '#5b8dce';
            const drawColor = isHighlight ? this.highlight.color : color;
            const alpha = isHighlight ? 0.3 : 0.1;

            ctx.fillStyle = `rgba(${this.hexRgb(drawColor)},${alpha})`;
            ctx.fillRect(x, midY - boxH / 2, boxW, boxH);
            ctx.strokeStyle = drawColor;
            ctx.lineWidth = isHighlight ? 2 : 1;
            ctx.strokeRect(x, midY - boxH / 2, boxW, boxH);

            ctx.fillStyle = '#fff';
            ctx.font = 'bold 14px "JetBrains Mono", monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(item.val, x + boxW / 2, midY);
        });

        // Arrow showing direction
        if (this.queue.length > 1) {
            ctx.strokeStyle = 'rgba(255,255,255,0.15)';
            ctx.lineWidth = 1;
            const ax = startX + boxW / 2;
            const bx = startX + (this.queue.length - 1) * (boxW + 4) + boxW / 2;
            ctx.beginPath(); ctx.moveTo(ax, midY - boxH / 2 - 14); ctx.lineTo(bx, midY - boxH / 2 - 14); ctx.stroke();
            ctx.fillStyle = 'rgba(255,255,255,0.15)';
            ctx.beginPath();
            ctx.moveTo(ax, midY - boxH / 2 - 14);
            ctx.lineTo(ax + 8, midY - boxH / 2 - 18);
            ctx.lineTo(ax + 8, midY - boxH / 2 - 10);
            ctx.fill();
        }

        // FIFO label
        ctx.fillStyle = 'rgba(255,255,255,0.2)';
        ctx.font = '13px "Inter", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText('FIFO — 先进先出', W / 2, 24);
    },

    drawBST() {
        if (!this.bstRoot) {
            const { ctx, W, H } = this;
            ctx.fillStyle = 'rgba(255,255,255,0.2)';
            ctx.font = '14px "Inter", sans-serif';
            ctx.textAlign = 'center';
            ctx.fillText('空树 — 点击"插入"或"加载预设"添加节点', W / 2, H / 2);
            return;
        }
        // Layout BST with x positions
        const positions = new Map();
        let idx = 0;
        const inorder = (node) => {
            if (!node) return;
            inorder(node.left);
            positions.set(node, { order: idx++ });
            inorder(node.right);
        };
        inorder(this.bstRoot);

        const total = idx;
        const nodeR = 18;
        const levelH = 55;
        const padX = 40;
        const usableW = this.W - padX * 2;

        // Assign (x, y) based on inorder position and depth
        const assignPos = (node, depth) => {
            if (!node) return;
            const pos = positions.get(node);
            pos.x = padX + (pos.order / (total - 1 || 1)) * usableW;
            pos.y = 40 + depth * levelH;
            assignPos(node.left, depth + 1);
            assignPos(node.right, depth + 1);
        };
        assignPos(this.bstRoot, 0);

        // Draw edges
        const drawEdges = (node) => {
            if (!node) return;
            const p = positions.get(node);
            if (node.left) {
                const lp = positions.get(node.left);
                this.ctx.strokeStyle = 'rgba(255,255,255,0.15)';
                this.ctx.lineWidth = 1.5;
                this.ctx.beginPath(); this.ctx.moveTo(p.x, p.y); this.ctx.lineTo(lp.x, lp.y); this.ctx.stroke();
                drawEdges(node.left);
            }
            if (node.right) {
                const rp = positions.get(node.right);
                this.ctx.strokeStyle = 'rgba(255,255,255,0.15)';
                this.ctx.lineWidth = 1.5;
                this.ctx.beginPath(); this.ctx.moveTo(p.x, p.y); this.ctx.lineTo(rp.x, rp.y); this.ctx.stroke();
                drawEdges(node.right);
            }
        };
        drawEdges(this.bstRoot);

        // Draw nodes
        const drawNodes = (node) => {
            if (!node) return;
            const p = positions.get(node);
            const isHL = this.highlight && this.highlight.val === node.val;
            const color = isHL ? this.highlight.color : '#c4793a';

            this.ctx.fillStyle = isHL ? `rgba(${this.hexRgb(color)},0.25)` : 'rgba(196,121,58,0.1)';
            this.ctx.beginPath(); this.ctx.arc(p.x, p.y, nodeR, 0, Math.PI * 2); this.ctx.fill();
            this.ctx.strokeStyle = color;
            this.ctx.lineWidth = isHL ? 2.5 : 1.5;
            this.ctx.beginPath(); this.ctx.arc(p.x, p.y, nodeR, 0, Math.PI * 2); this.ctx.stroke();

            if (isHL) {
                this.ctx.shadowColor = color;
                this.ctx.shadowBlur = 12;
                this.ctx.beginPath(); this.ctx.arc(p.x, p.y, nodeR, 0, Math.PI * 2); this.ctx.stroke();
                this.ctx.shadowBlur = 0;
            }

            this.ctx.fillStyle = '#fff';
            this.ctx.font = 'bold 13px "JetBrains Mono", monospace';
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText(node.val, p.x, p.y);

            drawNodes(node.left);
            drawNodes(node.right);
        };
        drawNodes(this.bstRoot);
    },

    hexRgb(hex) {
        if (hex.startsWith('#')) {
            const h = hex.slice(1);
            return `${parseInt(h.substring(0,2),16)},${parseInt(h.substring(2,4),16)},${parseInt(h.substring(4,6),16)}`;
        }
        return '200,200,200';
    },

    updateInfo(msg) {
        const el = document.getElementById('ds-info');
        if (el) el.textContent = msg;
    }
};

function initDataStructVis() {
    DataStructVis.init();
    DataStructVis.updatePanelVisibility();
}

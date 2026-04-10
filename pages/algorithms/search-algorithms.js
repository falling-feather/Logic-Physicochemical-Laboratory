// ===== 搜索算法可视化 =====

// ── 二分查找 ──
const BinarySearch = {
    arr: [],
    target: null,
    isRunning: false,
    speed: 600,
    highlights: {}, // idx -> 'low' | 'high' | 'mid' | 'found' | 'eliminated'

    init() {
        this.generateArray();
        this.bindControls();
    },

    bindControls() {
        const speedEl = document.getElementById('bs-speed');
        if (speedEl) {
            speedEl.addEventListener('input', (e) => {
                this.speed = parseInt(e.target.value);
                const lbl = document.getElementById('bs-speed-value');
                if (lbl) lbl.textContent = this.speed + 'ms';
            });
        }
    },

    generateArray() {
        if (this.isRunning) return;
        const len = 16;
        const set = new Set();
        while (set.size < len) set.add(Math.floor(Math.random() * 99) + 1);
        this.arr = [...set].sort((a, b) => a - b);
        this.highlights = {};
        this.render();
        this.setInfo('已生成有序数组，输入目标值后开始查找');
    },

    render() {
        const container = document.getElementById('bs-array');
        if (!container) return;
        container.innerHTML = '';
        this.arr.forEach((v, i) => {
            const el = document.createElement('div');
            el.className = 'bs-cell';
            const h = this.highlights[i];
            if (h) el.classList.add('bs-' + h);
            el.innerHTML = `<span class="bs-idx">${i}</span><span class="bs-val">${v}</span>`;
            container.appendChild(el);
        });
    },

    setInfo(text) {
        const el = document.getElementById('bs-info');
        if (el) el.textContent = text;
    },

    sleep(ms) {
        return new Promise(r => setTimeout(r, ms));
    },

    async start() {
        if (this.isRunning) return;
        const input = document.getElementById('bs-target');
        if (!input) return;
        const target = parseInt(input.value);
        if (isNaN(target)) { this.setInfo('请输入一个数字目标值'); return; }
        this.target = target;
        this.isRunning = true;
        this.setButtons(false);

        let low = 0, high = this.arr.length - 1;
        this.highlights = {};
        let steps = 0;

        while (low <= high) {
            steps++;
            // Mark eliminated
            for (let i = 0; i < this.arr.length; i++) {
                if (i < low || i > high) this.highlights[i] = 'eliminated';
            }
            this.highlights[low] = 'low';
            this.highlights[high] = 'high';
            this.render();
            this.setInfo(`第 ${steps} 步：搜索范围 [${low}, ${high}]`);
            await this.sleep(this.speed);

            const mid = Math.floor((low + high) / 2);
            this.highlights[mid] = 'mid';
            this.render();
            this.setInfo(`第 ${steps} 步：mid = ${mid}，值 = ${this.arr[mid]}，目标 = ${target}`);
            await this.sleep(this.speed);

            if (this.arr[mid] === target) {
                this.highlights[mid] = 'found';
                this.render();
                this.setInfo(`找到目标 ${target}！位于索引 ${mid}，共 ${steps} 步`);
                this.isRunning = false;
                this.setButtons(true);
                return;
            } else if (this.arr[mid] < target) {
                this.setInfo(`${this.arr[mid]} < ${target}，排除左半部分`);
                await this.sleep(this.speed / 2);
                low = mid + 1;
            } else {
                this.setInfo(`${this.arr[mid]} > ${target}，排除右半部分`);
                await this.sleep(this.speed / 2);
                high = mid - 1;
            }
        }

        // Not found
        for (let i = 0; i < this.arr.length; i++) this.highlights[i] = 'eliminated';
        this.render();
        this.setInfo(`未找到目标 ${target}，共 ${steps} 步`);
        this.isRunning = false;
        this.setButtons(true);
    },

    reset() {
        if (this.isRunning) return;
        this.highlights = {};
        this.render();
        this.setInfo('已重置');
    },

    setButtons(enabled) {
        document.querySelectorAll('#bs-controls .btn').forEach(b => b.disabled = !enabled);
    }
};

// ── 图遍历 (BFS / DFS) ──
const GraphTraversal = {
    canvas: null,
    ctx: null,
    nodes: [],
    edges: [],
    visited: [],
    queue: [],     // for BFS
    stack: [],     // for DFS
    current: null,
    isRunning: false,
    speed: 500,
    mode: 'bfs',
    startNode: 0,

    // Graph presets
    presets: {
        tree: {
            label: '二叉树',
            nodes: [
                { id: 0, x: 0.5, y: 0.1, label: 'A' },
                { id: 1, x: 0.28, y: 0.33, label: 'B' },
                { id: 2, x: 0.72, y: 0.33, label: 'C' },
                { id: 3, x: 0.14, y: 0.58, label: 'D' },
                { id: 4, x: 0.38, y: 0.58, label: 'E' },
                { id: 5, x: 0.62, y: 0.58, label: 'F' },
                { id: 6, x: 0.86, y: 0.58, label: 'G' },
                { id: 7, x: 0.07, y: 0.83, label: 'H' },
                { id: 8, x: 0.21, y: 0.83, label: 'I' }
            ],
            edges: [[0,1],[0,2],[1,3],[1,4],[2,5],[2,6],[3,7],[3,8]]
        },
        grid: {
            label: '网格图',
            nodes: (() => {
                const n = [];
                const labels = 'ABCDEFGHIJKLMNOP';
                for (let r = 0; r < 4; r++) {
                    for (let c = 0; c < 4; c++) {
                        n.push({
                            id: r * 4 + c,
                            x: 0.2 + c * 0.2,
                            y: 0.15 + r * 0.23,
                            label: labels[r * 4 + c]
                        });
                    }
                }
                return n;
            })(),
            edges: (() => {
                const e = [];
                for (let r = 0; r < 4; r++) {
                    for (let c = 0; c < 4; c++) {
                        const id = r * 4 + c;
                        if (c < 3) e.push([id, id + 1]);
                        if (r < 3) e.push([id, id + 4]);
                    }
                }
                return e;
            })()
        },
        cycle: {
            label: '环形图',
            nodes: (() => {
                const n = [];
                const labels = 'ABCDEFGH';
                const count = 8;
                for (let i = 0; i < count; i++) {
                    const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
                    n.push({
                        id: i,
                        x: 0.5 + Math.cos(angle) * 0.35,
                        y: 0.5 + Math.sin(angle) * 0.38,
                        label: labels[i]
                    });
                }
                return n;
            })(),
            edges: [[0,1],[1,2],[2,3],[3,4],[4,5],[5,6],[6,7],[7,0],[0,4],[1,5],[2,6],[3,7]]
        }
    },

    init() {
        this.canvas = document.getElementById('graph-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.bindControls();
        this.loadPreset('tree');
    },

    bindControls() {
        const speedEl = document.getElementById('graph-speed');
        if (speedEl) {
            speedEl.addEventListener('input', (e) => {
                this.speed = parseInt(e.target.value);
                const lbl = document.getElementById('graph-speed-value');
                if (lbl) lbl.textContent = this.speed + 'ms';
            });
        }
        // Canvas click to select start node
        if (this.canvas) {
            this.canvas.addEventListener('click', (e) => {
                if (this.isRunning) return;
                const rect = this.canvas.getBoundingClientRect();
                const mx = (e.clientX - rect.left) / rect.width;
                const my = (e.clientY - rect.top) / rect.height;
                let closest = -1, minDist = Infinity;
                this.nodes.forEach((n, i) => {
                    const d = Math.hypot(n.x - mx, n.y - my);
                    if (d < minDist) { minDist = d; closest = i; }
                });
                if (closest >= 0 && minDist < 0.08) {
                    this.startNode = closest;
                    this.reset();
                    this.setInfo(`起始节点设为 ${this.nodes[closest].label}，点击"开始遍历"`);
                }
            });
        }
    },

    loadPreset(name) {
        if (this.isRunning) return;
        const p = this.presets[name];
        if (!p) return;
        this.nodes = p.nodes.map(n => ({ ...n }));
        this.edges = p.edges.map(e => [...e]);
        this.startNode = 0;
        this.reset();
        // Update active preset button
        document.querySelectorAll('.graph-presets .btn--ghost').forEach(b => {
            b.classList.remove('active');
            if (b.textContent.trim().toLowerCase().includes(name)) b.classList.add('active');
        });
    },

    buildAdj() {
        const adj = {};
        this.nodes.forEach(n => adj[n.id] = []);
        this.edges.forEach(([a, b]) => {
            adj[a].push(b);
            adj[b].push(a);
        });
        // Sort adjacency to ensure deterministic order
        for (const k in adj) adj[k].sort((a, b) => a - b);
        return adj;
    },

    sizeCanvas() {
        const dpr = window.devicePixelRatio || 1;
        const rect = this.canvas.parentElement.getBoundingClientRect();
        const w = Math.round(rect.width);
        const h = Math.round(Math.max(w * 0.6, 300));
        this.canvas.width = w * dpr;
        this.canvas.height = h * dpr;
        this.canvas.style.height = h + 'px';
        this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        return { w, h };
    },

    draw() {
        if (!this.ctx) return;
        const { w, h } = this.sizeCanvas();

        // Background
        this.ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface-2').trim() || '#151822';
        this.ctx.fillRect(0, 0, w, h);

        // Draw edges
        this.edges.forEach(([a, b]) => {
            const na = this.nodes[a], nb = this.nodes[b];
            const ax = na.x * w, ay = na.y * h;
            const bx = nb.x * w, by = nb.y * h;

            // Check if this edge is a "traversed" edge
            const aV = this.visited.includes(a);
            const bV = this.visited.includes(b);
            const edgeActive = aV && bV;

            this.ctx.beginPath();
            this.ctx.moveTo(ax, ay);
            this.ctx.lineTo(bx, by);
            this.ctx.strokeStyle = edgeActive ? 'rgba(196,121,58,0.5)' : 'rgba(255,255,255,0.1)';
            this.ctx.lineWidth = edgeActive ? 2.5 : 1.5;
            this.ctx.stroke();
        });

        // Draw nodes
        const r = Math.min(w, h) * 0.038;
        this.nodes.forEach((n, i) => {
            const nx = n.x * w, ny = n.y * h;
            const isCurrent = this.current === i;
            const isVisited = this.visited.includes(i);
            const inFrontier = this.queue.includes(i) || this.stack.includes(i);
            const isStart = i === this.startNode && !isVisited && !isCurrent;

            this.ctx.beginPath();
            this.ctx.arc(nx, ny, r, 0, Math.PI * 2);

            if (isCurrent) {
                this.ctx.fillStyle = '#c4793a';
                this.ctx.shadowColor = '#c4793a';
                this.ctx.shadowBlur = 16;
            } else if (isVisited) {
                this.ctx.fillStyle = '#4d9e7e';
                this.ctx.shadowColor = '#4d9e7e';
                this.ctx.shadowBlur = 8;
            } else if (inFrontier) {
                this.ctx.fillStyle = '#5b8dce';
                this.ctx.shadowColor = '#5b8dce';
                this.ctx.shadowBlur = 8;
            } else if (isStart) {
                this.ctx.fillStyle = '#8b6fc0';
                this.ctx.shadowColor = '#8b6fc0';
                this.ctx.shadowBlur = 8;
            } else {
                this.ctx.fillStyle = 'rgba(255,255,255,0.08)';
                this.ctx.shadowBlur = 0;
            }
            this.ctx.fill();
            this.ctx.shadowBlur = 0;

            // Border
            this.ctx.strokeStyle = isCurrent ? '#e8a050' : isVisited ? '#6cc09a' : inFrontier ? '#7ba8d8' : 'rgba(255,255,255,0.15)';
            this.ctx.lineWidth = isCurrent ? 2.5 : 1.5;
            this.ctx.stroke();

            // Label
            this.ctx.fillStyle = isCurrent || isVisited || inFrontier ? '#fff' : 'rgba(255,255,255,0.5)';
            this.ctx.font = `600 ${Math.round(r * 0.9)}px Inter, sans-serif`;
            this.ctx.textAlign = 'center';
            this.ctx.textBaseline = 'middle';
            this.ctx.fillText(n.label, nx, ny);
        });

        // Draw legend for queue/stack
        this.drawFrontier(w, h);
    },

    drawFrontier(w, h) {
        const frontier = this.mode === 'bfs' ? this.queue : this.stack;
        if (frontier.length === 0 && this.visited.length === 0) return;

        const pad = 10;
        const boxH = 28;
        const y = h - pad - boxH;

        // Visit order
        if (this.visited.length > 0) {
            this.ctx.font = '12px Inter, sans-serif';
            this.ctx.fillStyle = 'rgba(255,255,255,0.4)';
            this.ctx.textAlign = 'left';
            this.ctx.fillText('访问顺序: ' + this.visited.map(i => this.nodes[i].label).join(' → '), pad, y - 6);
        }

        // Frontier
        if (frontier.length > 0) {
            const label = this.mode === 'bfs' ? '队列' : '栈';
            this.ctx.fillStyle = 'rgba(255,255,255,0.3)';
            this.ctx.textAlign = 'left';
            const text = label + ': [' + frontier.map(i => this.nodes[i].label).join(', ') + ']';
            this.ctx.fillText(text, pad, y + boxH - 6);
        }
    },

    sleep(ms) {
        return new Promise(r => setTimeout(r, ms));
    },

    async startBFS() {
        if (this.isRunning) return;
        this.mode = 'bfs';
        this.isRunning = true;
        this.setButtons(false);
        this.visited = [];
        this.queue = [this.startNode];
        this.stack = [];
        this.current = null;

        const adj = this.buildAdj();
        const visitedSet = new Set();
        visitedSet.add(this.startNode);
        let step = 0;

        this.draw();
        this.setInfo(`BFS 开始，起点 ${this.nodes[this.startNode].label}`);
        await this.sleep(this.speed);

        while (this.queue.length > 0) {
            step++;
            const nodeId = this.queue.shift();
            this.current = nodeId;
            this.visited.push(nodeId);
            this.draw();
            this.setInfo(`第 ${step} 步：访问 ${this.nodes[nodeId].label}`);
            await this.sleep(this.speed);

            // Enqueue neighbors
            const neighbors = adj[nodeId] || [];
            for (const nb of neighbors) {
                if (!visitedSet.has(nb)) {
                    visitedSet.add(nb);
                    this.queue.push(nb);
                }
            }
            this.current = null;
            this.draw();
            await this.sleep(this.speed / 3);
        }

        this.current = null;
        this.draw();
        this.setInfo(`BFS 完成！共 ${step} 步，访问顺序: ${this.visited.map(i => this.nodes[i].label).join(' → ')}`);
        this.isRunning = false;
        this.setButtons(true);
    },

    async startDFS() {
        if (this.isRunning) return;
        this.mode = 'dfs';
        this.isRunning = true;
        this.setButtons(false);
        this.visited = [];
        this.queue = [];
        this.stack = [this.startNode];
        this.current = null;

        const adj = this.buildAdj();
        const visitedSet = new Set();
        let step = 0;

        this.draw();
        this.setInfo(`DFS 开始，起点 ${this.nodes[this.startNode].label}`);
        await this.sleep(this.speed);

        while (this.stack.length > 0) {
            step++;
            const nodeId = this.stack.pop();
            if (visitedSet.has(nodeId)) continue;
            visitedSet.add(nodeId);

            this.current = nodeId;
            this.visited.push(nodeId);
            this.draw();
            this.setInfo(`第 ${step} 步：访问 ${this.nodes[nodeId].label}`);
            await this.sleep(this.speed);

            // Push neighbors in reverse order for correct DFS order
            const neighbors = (adj[nodeId] || []).slice().reverse();
            for (const nb of neighbors) {
                if (!visitedSet.has(nb)) {
                    this.stack.push(nb);
                }
            }
            this.current = null;
            this.draw();
            await this.sleep(this.speed / 3);
        }

        this.current = null;
        this.draw();
        this.setInfo(`DFS 完成！共 ${step} 步，访问顺序: ${this.visited.map(i => this.nodes[i].label).join(' → ')}`);
        this.isRunning = false;
        this.setButtons(true);
    },

    reset() {
        if (this.isRunning) return;
        this.visited = [];
        this.queue = [];
        this.stack = [];
        this.current = null;
        this.draw();
        this.setInfo(`点击节点选择起点（当前: ${this.nodes[this.startNode].label}），然后开始遍历`);
    },

    setInfo(text) {
        const el = document.getElementById('graph-info');
        if (el) el.textContent = text;
    },

    setButtons(enabled) {
        document.querySelectorAll('#graph-controls .btn').forEach(b => b.disabled = !enabled);
    }
};

// ── 初始化 ──
function initSearchAlgorithms() {
    BinarySearch.init();
    GraphTraversal.init();

    // Handle resize
    let resizeT;
    window.addEventListener('resize', () => {
        clearTimeout(resizeT);
        resizeT = setTimeout(() => GraphTraversal.draw(), 200);
    });
}

// Global exports
window.BinarySearch = BinarySearch;
window.GraphTraversal = GraphTraversal;
window.initSearchAlgorithms = initSearchAlgorithms;

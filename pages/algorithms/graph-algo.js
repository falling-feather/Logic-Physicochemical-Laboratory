// ===== 图算法可视化 — Dijkstra & Prim =====

const GraphAlgo = {
    canvas: null,
    ctx: null,
    nodes: [],
    edges: [],       // { from, to, weight }
    isRunning: false,
    speed: 500,
    mode: 'dijkstra',
    startNode: 0,

    // State during algorithm execution
    dist: {},
    prev: {},
    visited: new Set(),
    mstEdges: [],     // for Prim
    currentEdge: null,
    currentNode: null,
    frontier: [],     // edges being considered

    presets: {
        weighted: {
            label: '加权图',
            nodes: [
                { id: 0, x: 0.12, y: 0.15, label: 'A' },
                { id: 1, x: 0.40, y: 0.08, label: 'B' },
                { id: 2, x: 0.70, y: 0.12, label: 'C' },
                { id: 3, x: 0.90, y: 0.35, label: 'D' },
                { id: 4, x: 0.08, y: 0.55, label: 'E' },
                { id: 5, x: 0.35, y: 0.45, label: 'F' },
                { id: 6, x: 0.62, y: 0.50, label: 'G' },
                { id: 7, x: 0.88, y: 0.70, label: 'H' },
                { id: 8, x: 0.20, y: 0.85, label: 'I' },
                { id: 9, x: 0.55, y: 0.85, label: 'J' }
            ],
            edges: [
                [0,1,4],[0,4,2],[1,2,6],[1,5,3],[2,3,3],[2,6,5],
                [3,7,2],[4,5,7],[4,8,8],[5,6,1],[5,8,5],[5,9,9],
                [6,7,4],[6,9,6],[7,9,3],[8,9,10]
            ]
        },
        small: {
            label: '简单图',
            nodes: [
                { id: 0, x: 0.20, y: 0.20, label: 'S' },
                { id: 1, x: 0.50, y: 0.10, label: 'A' },
                { id: 2, x: 0.80, y: 0.25, label: 'B' },
                { id: 3, x: 0.15, y: 0.65, label: 'C' },
                { id: 4, x: 0.50, y: 0.55, label: 'D' },
                { id: 5, x: 0.85, y: 0.65, label: 'E' },
                { id: 6, x: 0.50, y: 0.90, label: 'T' }
            ],
            edges: [
                [0,1,2],[0,3,6],[1,2,3],[1,4,5],[2,5,7],
                [3,4,1],[4,5,4],[3,6,8],[4,6,3],[5,6,2]
            ]
        },
        dense: {
            label: '稠密图',
            nodes: (() => {
                const n = [];
                const labels = 'ABCDEFGH';
                const count = 8;
                for (let i = 0; i < count; i++) {
                    const angle = (i / count) * Math.PI * 2 - Math.PI / 2;
                    n.push({
                        id: i,
                        x: 0.5 + Math.cos(angle) * 0.36,
                        y: 0.50 + Math.sin(angle) * 0.38,
                        label: labels[i]
                    });
                }
                return n;
            })(),
            edges: (() => {
                const e = [];
                const count = 8;
                // Ring edges
                for (let i = 0; i < count; i++) {
                    e.push([i, (i+1) % count, Math.floor(Math.random()*8)+1]);
                }
                // Cross edges
                e.push([0,3,5],[1,4,7],[2,5,3],[3,6,4],[0,5,9],[1,6,6],[2,7,8]);
                return e;
            })()
        }
    },

    init() {
        this.canvas = document.getElementById('graph-algo-canvas');
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.bindControls();
        this.loadPreset('weighted');
    },

    bindControls() {
        const speedEl = document.getElementById('ga-speed');
        if (speedEl) {
            speedEl.addEventListener('input', (e) => {
                this.speed = parseInt(e.target.value);
                const lbl = document.getElementById('ga-speed-value');
                if (lbl) lbl.textContent = this.speed + 'ms';
            });
        }
        // Click to select start node
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
                    this.resetState();
                    this.draw();
                    this.setInfo(`起点设为 ${this.nodes[closest].label}，选择算法并开始`);
                }
            });
        }
    },

    loadPreset(name) {
        if (this.isRunning) return;
        const p = this.presets[name];
        if (!p) return;
        this.nodes = p.nodes.map(n => ({ ...n }));
        this.edges = p.edges.map(e => ({ from: e[0], to: e[1], weight: e[2] }));
        this.startNode = 0;
        this.resetState();
        this.draw();
        this.setInfo(`已加载「${p.label}」，点击节点选择起点`);
        // Update active preset button
        document.querySelectorAll('.ga-presets .btn--ghost').forEach(b => {
            b.classList.remove('active');
            if (b.textContent.trim().toLowerCase().includes(name)) b.classList.add('active');
        });
    },

    resetState() {
        this.visited = new Set();
        this.dist = {};
        this.prev = {};
        this.mstEdges = [];
        this.currentEdge = null;
        this.currentNode = null;
        this.frontier = [];
    },

    reset() {
        if (this.isRunning) return;
        this.resetState();
        this.draw();
        this.setInfo('已重置');
    },

    buildAdj() {
        const adj = {};
        this.nodes.forEach(n => adj[n.id] = []);
        this.edges.forEach(e => {
            adj[e.from].push({ to: e.to, w: e.weight });
            adj[e.to].push({ to: e.from, w: e.weight });
        });
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
        const ctx = this.ctx;

        // Background
        ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface-2').trim() || '#151822';
        ctx.fillRect(0, 0, w, h);

        const r = Math.min(w, h) * 0.035;

        // Draw edges
        this.edges.forEach(e => {
            const na = this.nodes[e.from], nb = this.nodes[e.to];
            const ax = na.x * w, ay = na.y * h;
            const bx = nb.x * w, by = nb.y * h;

            // Determine edge state
            const isMST = this.mstEdges.some(me =>
                (me.from === e.from && me.to === e.to) || (me.from === e.to && me.to === e.from));
            const isPathEdge = this.mode === 'dijkstra' &&
                ((this.prev[e.to] === e.from) || (this.prev[e.from] === e.to));
            const isCurrent = this.currentEdge &&
                ((this.currentEdge.from === e.from && this.currentEdge.to === e.to) ||
                 (this.currentEdge.from === e.to && this.currentEdge.to === e.from));
            const isFrontier = this.frontier.some(fe =>
                (fe.from === e.from && fe.to === e.to) || (fe.from === e.to && fe.to === e.from));

            ctx.beginPath();
            ctx.moveTo(ax, ay);
            ctx.lineTo(bx, by);

            if (isCurrent) {
                ctx.strokeStyle = '#c4793a';
                ctx.lineWidth = 3.5;
            } else if (isMST || isPathEdge) {
                ctx.strokeStyle = '#4d9e7e';
                ctx.lineWidth = 3;
            } else if (isFrontier) {
                ctx.strokeStyle = 'rgba(91,141,206,0.5)';
                ctx.lineWidth = 2;
            } else {
                ctx.strokeStyle = 'rgba(255,255,255,0.08)';
                ctx.lineWidth = 1.5;
            }
            ctx.stroke();

            // Weight label
            const mx = (ax + bx) / 2, my2 = (ay + by) / 2;
            // Offset perpendicular slightly
            const dx = bx - ax, dy = by - ay;
            const len = Math.hypot(dx, dy) || 1;
            const ox = -dy / len * 12, oy = dx / len * 12;

            ctx.fillStyle = isCurrent ? '#c4793a' : isMST || isPathEdge ? '#4d9e7e' : 'rgba(255,255,255,0.3)';
            ctx.font = `${isCurrent || isMST ? 'bold ' : ''}11px Inter, sans-serif`;
            ctx.textAlign = 'center';
            ctx.textBaseline = 'middle';
            ctx.fillText(e.weight, mx + ox, my2 + oy);
        });

        // Draw nodes
        this.nodes.forEach((n, i) => {
            const nx = n.x * w, ny = n.y * h;
            const isCurrent = this.currentNode === i;
            const isVisited = this.visited.has(i);
            const isStart = i === this.startNode && !isVisited && !isCurrent;

            ctx.beginPath();
            ctx.arc(nx, ny, r, 0, Math.PI * 2);

            if (isCurrent) {
                ctx.fillStyle = '#c4793a';
                ctx.shadowColor = '#c4793a'; ctx.shadowBlur = 16;
            } else if (isVisited) {
                ctx.fillStyle = '#4d9e7e';
                ctx.shadowColor = '#4d9e7e'; ctx.shadowBlur = 8;
            } else if (isStart) {
                ctx.fillStyle = '#8b6fc0';
                ctx.shadowColor = '#8b6fc0'; ctx.shadowBlur = 8;
            } else {
                ctx.fillStyle = 'rgba(255,255,255,0.06)';
                ctx.shadowBlur = 0;
            }
            ctx.fill();
            ctx.shadowBlur = 0;

            ctx.strokeStyle = isCurrent ? '#e8a050' : isVisited ? '#6cc09a' : isStart ? '#a58ad0' : 'rgba(255,255,255,0.12)';
            ctx.lineWidth = isCurrent ? 2.5 : 1.5;
            ctx.stroke();

            // Label
            ctx.fillStyle = '#fff';
            ctx.font = `600 ${Math.round(r * 0.85)}px Inter, sans-serif`;
            ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
            ctx.fillText(n.label, nx, ny);

            // Distance label (Dijkstra)
            if (this.mode === 'dijkstra' && this.dist[i] !== undefined) {
                ctx.fillStyle = isVisited ? 'rgba(255,255,255,0.6)' : 'rgba(255,255,255,0.3)';
                ctx.font = '10px monospace';
                ctx.fillText(this.dist[i] === Infinity ? '∞' : this.dist[i], nx, ny + r + 12);
            }
        });

        // Info panel at bottom
        this.drawBottomInfo(w, h);
    },

    drawBottomInfo(w, h) {
        if (this.visited.size === 0) return;
        const ctx = this.ctx;
        ctx.fillStyle = 'rgba(255,255,255,0.35)';
        ctx.font = '11px Inter, sans-serif';
        ctx.textAlign = 'left';

        const order = [...this.visited].map(i => this.nodes[i].label).join(' → ');
        ctx.fillText('访问顺序: ' + order, 10, h - 10);

        if (this.mode === 'prim' && this.mstEdges.length > 0) {
            const total = this.mstEdges.reduce((s, e) => s + e.weight, 0);
            ctx.textAlign = 'right';
            ctx.fillText(`MST 总权值: ${total}`, w - 10, h - 10);
        }
    },

    sleep(ms) { return new Promise(r => setTimeout(r, ms)); },

    setInfo(text) {
        const el = document.getElementById('ga-info');
        if (el) el.textContent = text;
    },

    setButtons(enabled) {
        document.querySelectorAll('#ga-controls .btn').forEach(b => b.disabled = !enabled);
    },

    // ═══ Dijkstra ═══
    async startDijkstra() {
        if (this.isRunning) return;
        this.mode = 'dijkstra';
        this.isRunning = true;
        this.setButtons(false);
        this.resetState();

        const adj = this.buildAdj();
        const n = this.nodes.length;

        // Init distances
        for (let i = 0; i < n; i++) {
            this.dist[i] = i === this.startNode ? 0 : Infinity;
            this.prev[i] = null;
        }

        // Priority queue (simple array)
        const pq = [{ node: this.startNode, d: 0 }];
        let step = 0;

        this.draw();
        this.setInfo(`Dijkstra 开始，起点 ${this.nodes[this.startNode].label}`);
        await this.sleep(this.speed);

        while (pq.length > 0) {
            // Extract min
            pq.sort((a, b) => a.d - b.d);
            const { node: u, d } = pq.shift();
            if (this.visited.has(u)) continue;

            step++;
            this.currentNode = u;
            this.visited.add(u);
            this.draw();
            this.setInfo(`第 ${step} 步：确认 ${this.nodes[u].label}，距离 = ${d}`);
            await this.sleep(this.speed);

            // Relax neighbors
            this.frontier = [];
            for (const { to: v, w } of adj[u]) {
                if (this.visited.has(v)) continue;
                this.frontier.push({ from: u, to: v, weight: w });
            }
            this.currentNode = u;
            this.draw();
            await this.sleep(this.speed / 2);

            for (const { to: v, w } of adj[u]) {
                if (this.visited.has(v)) continue;
                const nd = d + w;
                if (nd < this.dist[v]) {
                    this.currentEdge = { from: u, to: v, weight: w };
                    this.dist[v] = nd;
                    this.prev[v] = u;
                    pq.push({ node: v, d: nd });
                    this.draw();
                    this.setInfo(`松弛 ${this.nodes[u].label}→${this.nodes[v].label}：${d}+${w}=${nd}`);
                    await this.sleep(this.speed / 2);
                }
            }
            this.currentEdge = null;
            this.frontier = [];
        }

        this.currentNode = null;
        this.draw();
        const result = this.nodes.map(n => `${n.label}:${this.dist[n.id] === Infinity ? '∞' : this.dist[n.id]}`).join('  ');
        this.setInfo(`Dijkstra 完成！ ${result}`);
        this.isRunning = false;
        this.setButtons(true);
    },

    // ═══ Prim ═══
    async startPrim() {
        if (this.isRunning) return;
        this.mode = 'prim';
        this.isRunning = true;
        this.setButtons(false);
        this.resetState();

        const adj = this.buildAdj();
        let step = 0;

        this.visited.add(this.startNode);
        this.currentNode = this.startNode;
        this.draw();
        this.setInfo(`Prim 开始，起点 ${this.nodes[this.startNode].label}`);
        await this.sleep(this.speed);

        while (this.visited.size < this.nodes.length) {
            // Find minimum weight edge from visited to unvisited
            let minEdge = null, minW = Infinity;
            this.frontier = [];
            for (const u of this.visited) {
                for (const { to: v, w } of adj[u]) {
                    if (!this.visited.has(v)) {
                        this.frontier.push({ from: u, to: v, weight: w });
                        if (w < minW) {
                            minW = w;
                            minEdge = { from: u, to: v, weight: w };
                        }
                    }
                }
            }
            if (!minEdge) break;

            step++;
            this.currentEdge = minEdge;
            this.draw();
            this.setInfo(`第 ${step} 步：考虑 ${this.frontier.length} 条候选边…`);
            await this.sleep(this.speed);

            // Add edge to MST
            this.mstEdges.push(minEdge);
            this.visited.add(minEdge.to);
            this.currentNode = minEdge.to;
            this.frontier = [];
            this.currentEdge = null;
            this.draw();

            const total = this.mstEdges.reduce((s, e) => s + e.weight, 0);
            this.setInfo(`第 ${step} 步：添加 ${this.nodes[minEdge.from].label}→${this.nodes[minEdge.to].label} (权值 ${minEdge.weight})，MST 总权 = ${total}`);
            await this.sleep(this.speed);
        }

        this.currentNode = null;
        const total = this.mstEdges.reduce((s, e) => s + e.weight, 0);
        this.draw();
        this.setInfo(`Prim 完成！最小生成树总权值 = ${total}，共 ${this.mstEdges.length} 条边`);
        this.isRunning = false;
        this.setButtons(true);
    }
};

// ── 初始化 ──
function initGraphAlgo() {
    GraphAlgo.init();
    let resizeT;
    window.addEventListener('resize', () => {
        clearTimeout(resizeT);
        resizeT = setTimeout(() => GraphAlgo.draw(), 200);
    });
}

window.GraphAlgo = GraphAlgo;
window.initGraphAlgo = initGraphAlgo;

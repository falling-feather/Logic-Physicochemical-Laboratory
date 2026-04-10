// ===== 数学页面逻辑 =====

// ===== 算筹逻辑 =====
function numberToAbacus(n) {
    const s = []; 
    let r = n;
    if(r>=10) {
        const t = Math.floor(r/10);
        for(let i=0;i<Math.floor(t/5);i++) s.push({type:'h',v:5});
        for(let i=0;i<t%5;i++) s.push({type:'v',v:1});
        r%=10;
    }
    for(let i=0;i<Math.floor(r/5);i++) s.push({type:'v',v:5});
    for(let i=0;i<r%5;i++) s.push({type:'h',v:1});
    return s;
}

function renderAbacus(id, n) {
    const c = document.getElementById(id);
    if(!c) return;
    c.innerHTML = '';
    const s = numberToAbacus(n);
    if(!s.length) c.innerHTML = '<span style="color:#94a3b8">0</span>';
    s.forEach((k,i) => {
        const d = document.createElement('div');
        d.className = `stick ${k.type==='h'?'horizontal':''}`;
        d.style.animationDelay = i*0.1+'s';
        c.appendChild(d);
    });
}

function updateAbacus() {
    const num1El = document.getElementById('num1');
    const num2El = document.getElementById('num2');
    if(num1El) renderAbacus('abacus-num1', parseInt(num1El.value)||0);
    if(num2El) renderAbacus('abacus-num2', parseInt(num2El.value)||0);
}

function calculateAbacus() {
    const num1El = document.getElementById('num1');
    const num2El = document.getElementById('num2');
    const operatorEl = document.getElementById('operator');
    if(!num1El || !num2El || !operatorEl) return;
    
    const n1 = parseInt(num1El.value)||0;
    const n2 = parseInt(num2El.value)||0;
    const op = operatorEl.value;
    renderAbacus('abacus-result', op==='add' ? n1+n2 : Math.max(0, n1-n2));
}

// ===== 数学页面初始化 =====
function initMathematics() {
    updateAbacus();
    initFunctionGraph();
}

// ===== 函数图像绘制 =====
function convertPower(expr) {
    // Convert a^b to Math.pow(a,b) by finding ^ and extracting base & exponent
    while (expr.indexOf('^') !== -1) {
        const idx = expr.indexOf('^');
        // Find base: walk backwards from ^
        let baseStart = idx - 1;
        if (expr[baseStart] === ')') {
            // Match closing paren backwards
            let depth = 1;
            baseStart--;
            while (baseStart >= 0 && depth > 0) {
                if (expr[baseStart] === ')') depth++;
                if (expr[baseStart] === '(') depth--;
                baseStart--;
            }
            baseStart++;
            // Include function name before (
            while (baseStart > 0 && /[a-zA-Z._]/.test(expr[baseStart - 1])) baseStart--;
        } else {
            while (baseStart > 0 && /[a-zA-Z0-9._]/.test(expr[baseStart - 1])) baseStart--;
        }
        // Find exponent: walk forward from ^
        let expEnd = idx + 1;
        // Skip leading minus in exponent
        if (expr[expEnd] === '-') expEnd++;
        if (expr[expEnd] === '(') {
            let depth = 1;
            expEnd++;
            while (expEnd < expr.length && depth > 0) {
                if (expr[expEnd] === '(') depth++;
                if (expr[expEnd] === ')') depth--;
                expEnd++;
            }
        } else {
            while (expEnd < expr.length && /[a-zA-Z0-9._]/.test(expr[expEnd])) expEnd++;
        }
        const base = expr.substring(baseStart, idx);
        const exp = expr.substring(idx + 1, expEnd);
        expr = expr.substring(0, baseStart) + 'Math.pow(' + base + ',' + exp + ')' + expr.substring(expEnd);
    }
    return expr;
}

function compileExpression(exprStr) {
    let s = exprStr.trim();
    if (!s) return null;

    // Convert ^ to Math.pow(base, exp)
    s = convertPower(s);

    // Replace math functions with Math.xxx
    const funcs = {
        sin: 'Math.sin', cos: 'Math.cos', tan: 'Math.tan',
        asin: 'Math.asin', acos: 'Math.acos', atan: 'Math.atan',
        abs: 'Math.abs', sqrt: 'Math.sqrt', cbrt: 'Math.cbrt',
        log: 'Math.log10', ln: 'Math.log', exp: 'Math.exp',
        floor: 'Math.floor', ceil: 'Math.ceil', round: 'Math.round',
        sign: 'Math.sign'
    };
    for (const [k, v] of Object.entries(funcs)) {
        s = s.replace(new RegExp('\\b' + k + '\\s*\\(', 'g'), v + '(');
    }

    // Replace constants
    s = s.replace(/\bpi\b/gi, 'Math.PI');
    // Replace standalone 'e' (not part of 'exp' or other words)
    s = s.replace(/(?<![a-zA-Z])e(?![a-zA-Z\(])/g, 'Math.E');

    // Validate: after replacements, strip all allowed tokens, check nothing remains
    const stripped = s
        .replace(/Math\.(sin|cos|tan|asin|acos|atan|abs|sqrt|cbrt|log10|log|exp|floor|ceil|round|sign|PI|E|pow|min|max)/g, '')
        .replace(/[x\d\s\+\-\*\/\(\)\.\,\%]/g, '');
    if (stripped.length > 0) return null;

    try {
        return new Function('x', 'return (' + s + ')');
    } catch (e) {
        return null;
    }
}

function drawFunctionGraph() {
    const canvas = document.getElementById('function-graph-canvas');
    const errorEl = document.getElementById('graph-error');
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    // Size canvas to container
    const rect = canvas.parentElement.getBoundingClientRect();
    const w = Math.round(rect.width);
    const h = Math.round(Math.max(w * 0.6, 300));
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    canvas.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    // Read parameters
    const exprStr = (document.getElementById('func-expr')?.value || '').trim();
    const xmin = parseFloat(document.getElementById('graph-xmin')?.value) || -10;
    const xmax = parseFloat(document.getElementById('graph-xmax')?.value) || 10;
    const ymin = parseFloat(document.getElementById('graph-ymin')?.value) || -5;
    const ymax = parseFloat(document.getElementById('graph-ymax')?.value) || 5;
    const showGrid = document.getElementById('graph-grid')?.checked !== false;

    // Compile expression
    const fn = compileExpression(exprStr);
    if (errorEl) errorEl.textContent = '';
    if (!fn && exprStr) {
        if (errorEl) errorEl.textContent = '⚠ 无法解析表达式';
    }

    // Drawing helpers
    const mapX = (x) => ((x - xmin) / (xmax - xmin)) * w;
    const mapY = (y) => ((ymax - y) / (ymax - ymin)) * h;

    // Background
    ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--surface-2').trim() || '#151822';
    ctx.fillRect(0, 0, w, h);

    // Grid
    if (showGrid) {
        ctx.strokeStyle = 'rgba(255,255,255,0.04)';
        ctx.lineWidth = 1;
        const gridStep = niceStep(xmax - xmin);
        // Vertical grid lines
        for (let gx = Math.ceil(xmin / gridStep) * gridStep; gx <= xmax; gx += gridStep) {
            const px = mapX(gx);
            ctx.beginPath(); ctx.moveTo(px, 0); ctx.lineTo(px, h); ctx.stroke();
        }
        const gridStepY = niceStep(ymax - ymin);
        // Horizontal grid lines
        for (let gy = Math.ceil(ymin / gridStepY) * gridStepY; gy <= ymax; gy += gridStepY) {
            const py = mapY(gy);
            ctx.beginPath(); ctx.moveTo(0, py); ctx.lineTo(w, py); ctx.stroke();
        }
    }

    // Axes
    ctx.strokeStyle = 'rgba(255,255,255,0.18)';
    ctx.lineWidth = 1.5;
    // X axis
    if (ymin <= 0 && ymax >= 0) {
        const ay = mapY(0);
        ctx.beginPath(); ctx.moveTo(0, ay); ctx.lineTo(w, ay); ctx.stroke();
    }
    // Y axis
    if (xmin <= 0 && xmax >= 0) {
        const ax = mapX(0);
        ctx.beginPath(); ctx.moveTo(ax, 0); ctx.lineTo(ax, h); ctx.stroke();
    }

    // Axis labels
    ctx.fillStyle = 'rgba(255,255,255,0.25)';
    ctx.font = '11px ' + (getComputedStyle(document.documentElement).getPropertyValue('--font-mono').trim() || 'monospace');
    ctx.textAlign = 'center';
    ctx.textBaseline = 'top';
    const labelStepX = niceStep(xmax - xmin);
    for (let lx = Math.ceil(xmin / labelStepX) * labelStepX; lx <= xmax; lx += labelStepX) {
        if (Math.abs(lx) < 1e-10) continue;
        const px = mapX(lx);
        const ay = ymin <= 0 && ymax >= 0 ? mapY(0) : h;
        ctx.fillText(formatNum(lx), px, Math.min(ay + 4, h - 14));
    }
    ctx.textAlign = 'right';
    ctx.textBaseline = 'middle';
    const labelStepY = niceStep(ymax - ymin);
    for (let ly = Math.ceil(ymin / labelStepY) * labelStepY; ly <= ymax; ly += labelStepY) {
        if (Math.abs(ly) < 1e-10) continue;
        const py = mapY(ly);
        const ax = xmin <= 0 && xmax >= 0 ? mapX(0) : 0;
        ctx.fillText(formatNum(ly), Math.max(ax - 4, 40), py);
    }

    // Origin label
    if (xmin <= 0 && xmax >= 0 && ymin <= 0 && ymax >= 0) {
        ctx.textAlign = 'right';
        ctx.textBaseline = 'top';
        ctx.fillText('0', mapX(0) - 4, mapY(0) + 4);
    }

    // Draw function curve
    if (fn) {
        ctx.strokeStyle = '#5b8dce';
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.beginPath();
        let drawing = false;
        const steps = w * 2;
        for (let i = 0; i <= steps; i++) {
            const x = xmin + (xmax - xmin) * (i / steps);
            let y;
            try { y = fn(x); } catch (e) { drawing = false; continue; }
            if (!isFinite(y) || isNaN(y)) { drawing = false; continue; }
            // Clip to visible range with some margin
            if (y < ymin - (ymax - ymin) * 2 || y > ymax + (ymax - ymin) * 2) {
                drawing = false;
                continue;
            }
            const px = mapX(x);
            const py = mapY(y);
            if (!drawing) {
                ctx.moveTo(px, py);
                drawing = true;
            } else {
                ctx.lineTo(px, py);
            }
        }
        ctx.stroke();
    }

    // Store mapping for mouse tracking
    canvas._graphState = { xmin, xmax, ymin, ymax, w, h };
}

function niceStep(range) {
    const rough = range / 8;
    const mag = Math.pow(10, Math.floor(Math.log10(rough)));
    const norm = rough / mag;
    if (norm < 1.5) return mag;
    if (norm < 3.5) return 2 * mag;
    if (norm < 7.5) return 5 * mag;
    return 10 * mag;
}

function formatNum(n) {
    return Math.abs(n) >= 1000 || (Math.abs(n) < 0.01 && n !== 0)
        ? n.toExponential(1)
        : parseFloat(n.toPrecision(4)).toString();
}

function setFunction(expr) {
    const el = document.getElementById('func-expr');
    if (el) {
        el.value = expr;
        drawFunctionGraph();
    }
    // Update active button state
    document.querySelectorAll('.preset-functions .btn--ghost').forEach(btn => btn.classList.remove('active'));
    event?.target?.classList.add('active');
}

function initFunctionGraph() {
    const canvas = document.getElementById('function-graph-canvas');
    if (!canvas) return;

    // Mouse tracking
    canvas.addEventListener('mousemove', (e) => {
        const state = canvas._graphState;
        if (!state) return;
        const rect = canvas.getBoundingClientRect();
        const mx = e.clientX - rect.left;
        const my = e.clientY - rect.top;
        const x = state.xmin + (mx / state.w) * (state.xmax - state.xmin);
        const y = state.ymax - (my / state.h) * (state.ymax - state.ymin);
        const coordEl = document.getElementById('graph-coord-display');
        if (coordEl) coordEl.textContent = `(${x.toFixed(2)}, ${y.toFixed(2)})`;
    });

    canvas.addEventListener('mouseleave', () => {
        const coordEl = document.getElementById('graph-coord-display');
        if (coordEl) coordEl.textContent = '';
    });

    // Handle resize
    let resizeTimer;
    window.addEventListener('resize', () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(drawFunctionGraph, 150);
    });

    // Initial draw
    drawFunctionGraph();
}

// 导出全局
window.updateAbacus = updateAbacus;
window.calculateAbacus = calculateAbacus;
window.drawFunctionGraph = drawFunctionGraph;
window.setFunction = setFunction;
window.initFunctionGraph = initFunctionGraph;


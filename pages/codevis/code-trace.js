/* ===== Code Trace · 代码执行追踪 (v5.0) =====
 * 纯前端 JS：预先生成 trace 步骤，回放展示。
 * 后续可接 Pyodide / 自研解释器以支持真实代码运行。
 */
(function (global) {
    'use strict';

    // ============== Trace 生成器 ==============
    function traceBubbleSort(input) {
        const arr = input.slice();
        const steps = [];
        const out = [];
        const snap = (line, vars, hi, msg) => steps.push({
            line, vars: Object.assign({ arr: arr.slice() }, vars),
            highlight: hi || {}, msg: msg || '', stdout: out.slice()
        });
        snap(1, { n: arr.length }, {}, '开始排序');
        const n = arr.length;
        for (let i = 0; i < n - 1; i++) {
            snap(2, { i, n }, { i }, `外层循环 i = ${i}`);
            let swapped = false;
            snap(3, { i, swapped, n }, { i }, '');
            for (let j = 0; j < n - i - 1; j++) {
                snap(4, { i, j, swapped, n }, { i, j, j2: j + 1 }, `比较 arr[${j}] 与 arr[${j + 1}]`);
                snap(5, { i, j, swapped, n, 'arr[j]': arr[j], 'arr[j+1]': arr[j + 1] }, { i, j, j2: j + 1 }, '');
                if (arr[j] > arr[j + 1]) {
                    snap(6, { i, j, swapped, n }, { i, j, j2: j + 1, swap: true }, `交换 ${arr[j]} ↔ ${arr[j + 1]}`);
                    const t = arr[j]; arr[j] = arr[j + 1]; arr[j + 1] = t;
                    swapped = true;
                    snap(7, { i, j, swapped, n }, { i, j, j2: j + 1, swap: true }, '已交换');
                }
            }
            if (!swapped) {
                out.push(`第 ${i + 1} 轮无交换，提前结束`);
                snap(9, { i, swapped, n }, { i }, '提前结束');
                break;
            }
            out.push(`第 ${i + 1} 轮结束 → [${arr.join(', ')}]`);
        }
        snap(10, { n }, {}, '排序完成');
        out.push(`最终: [${arr.join(', ')}]`);
        steps[steps.length - 1].stdout = out.slice();
        return steps;
    }

    function traceBinarySearch(input, target) {
        const arr = input.slice().sort((a, b) => a - b);
        const steps = [];
        const out = [`输入数组（已排序）: [${arr.join(', ')}], 查找 ${target}`];
        const snap = (line, vars, hi, msg) => steps.push({
            line, vars: Object.assign({ arr: arr.slice(), target }, vars),
            highlight: hi || {}, msg: msg || '', stdout: out.slice()
        });
        let lo = 0, hi = arr.length - 1;
        snap(1, { lo, hi }, {}, '初始化 lo, hi');
        while (lo <= hi) {
            const mid = Math.floor((lo + hi) / 2);
            snap(2, { lo, hi, mid }, { i: lo, j: mid, j2: hi }, `mid = ${mid}`);
            snap(3, { lo, hi, mid, 'arr[mid]': arr[mid] }, { i: lo, j: mid, j2: hi }, '');
            if (arr[mid] === target) {
                out.push(`找到 ${target} 在下标 ${mid}`);
                snap(4, { lo, hi, mid }, { j: mid, swap: true }, '命中！');
                steps[steps.length - 1].stdout = out.slice();
                return steps;
            } else if (arr[mid] < target) {
                lo = mid + 1;
                snap(6, { lo, hi, mid }, { i: lo, j: mid, j2: hi }, `arr[mid] < target → lo = mid + 1`);
            } else {
                hi = mid - 1;
                snap(8, { lo, hi, mid }, { i: lo, j: mid, j2: hi }, `arr[mid] > target → hi = mid - 1`);
            }
        }
        out.push(`未找到 ${target}`);
        snap(10, { lo, hi }, {}, '未找到');
        steps[steps.length - 1].stdout = out.slice();
        return steps;
    }

    function traceFib(n) {
        const steps = [];
        const out = [];
        const callStack = [];
        const snap = (line, vars, hi, msg) => steps.push({
            line, vars: Object.assign({ stack: callStack.slice() }, vars),
            highlight: hi || {}, msg: msg || '', stdout: out.slice(), arrOverride: callStack.slice()
        });
        function fib(k, depth) {
            callStack.push(`fib(${k})`);
            snap(2, { k, depth }, {}, `调用 fib(${k})`);
            if (k < 2) {
                snap(3, { k, depth }, { swap: true }, `基线 → 返回 ${k}`);
                callStack.pop();
                return k;
            }
            snap(4, { k, depth }, {}, '');
            const a = fib(k - 1, depth + 1);
            const b = fib(k - 2, depth + 1);
            snap(5, { k, depth, a, b }, { swap: true }, `fib(${k}) = ${a + b}`);
            callStack.pop();
            return a + b;
        }
        const r = fib(n, 0);
        out.push(`fib(${n}) = ${r}`);
        snap(6, { n, result: r }, {}, '完成');
        steps[steps.length - 1].stdout = out.slice();
        return steps;
    }

    // ============== Source 代码（与 trace 的 line 对应） ==============
    const SAMPLES = {
        bubble: {
            label: '冒泡排序',
            input: [5, 2, 8, 1, 9, 3],
            source: [
                'def bubble_sort(arr):',
                '    n = len(arr)',
                '    for i in range(n - 1):',
                '        swapped = False',
                '        for j in range(n - i - 1):',
                '            if arr[j] > arr[j+1]:',
                '                arr[j], arr[j+1] = arr[j+1], arr[j]',
                '                swapped = True',
                '        if not swapped:',
                '            break',
                '    return arr'
            ],
            build: (input) => traceBubbleSort(input)
        },
        binsearch: {
            label: '二分查找',
            input: [1, 3, 5, 7, 9, 11, 13, 15],
            target: 11,
            source: [
                'def binary_search(arr, target):',
                '    lo, hi = 0, len(arr) - 1',
                '    while lo <= hi:',
                '        mid = (lo + hi) // 2',
                '        if arr[mid] == target:',
                '            return mid',
                '        elif arr[mid] < target:',
                '            lo = mid + 1',
                '        else:',
                '            hi = mid - 1',
                '    return -1'
            ],
            build: (input, sample) => traceBinarySearch(input, sample.target)
        },
        fib: {
            label: '斐波那契递归',
            input: 5,
            source: [
                'def fib(n):',
                '    # 计算 fib(n)',
                '    if n < 2:',
                '        return n',
                '    # 递归两次',
                '    return fib(n - 1) + fib(n - 2)'
            ],
            build: (input) => traceFib(input)
        }
    };

    // ============== Player ==============
    const CodeTrace = {
        _inited: false,
        steps: [],
        sample: 'bubble',
        currentSampleData: null,
        idx: 0,
        playing: false,
        speed: 450,
        _timer: null,
        _prevVars: {},

        init() {
            if (this._inited) return;
            this._inited = true;
            this._cacheDOM();
            this._bind();
            this._loadSample('bubble');
        },

        destroy() {
            this._stop();
        },

        _cacheDOM() {
            this.$sample = document.getElementById('code-trace-sample');
            this.$prev = document.getElementById('code-trace-prev');
            this.$next = document.getElementById('code-trace-next');
            this.$play = document.getElementById('code-trace-play');
            this.$speed = document.getElementById('code-trace-speed');
            this.$source = document.getElementById('code-trace-source');
            this.$vars = document.getElementById('code-trace-vars');
            this.$array = document.getElementById('code-trace-array');
            this.$stdout = document.getElementById('code-trace-stdout');
            this.$seek = document.getElementById('code-trace-seek');
            this.$stepLabel = document.getElementById('code-trace-step-label');
        },

        _bind() {
            this.$sample.addEventListener('change', (e) => { this._stop(); this._loadSample(e.target.value); });
            this.$prev.addEventListener('click', () => { this._stop(); this._goto(this.idx - 1); });
            this.$next.addEventListener('click', () => { this._stop(); this._goto(this.idx + 1); });
            this.$play.addEventListener('click', () => this.playing ? this._stop() : this._play());
            this.$speed.addEventListener('change', (e) => {
                this.speed = parseInt(e.target.value, 10) || 450;
                if (this.playing) { this._stop(); this._play(); }
            });
            this.$seek.addEventListener('input', (e) => {
                this._stop();
                this._goto(parseInt(e.target.value, 10) || 0);
            });
        },

        _loadSample(key) {
            const s = SAMPLES[key];
            if (!s) return;
            this.sample = key;
            this.currentSampleData = s;
            this.steps = s.build(s.input, s);
            this.idx = 0;
            this._prevVars = {};
            this._renderSource(s.source);
            this.$seek.max = String(Math.max(0, this.steps.length - 1));
            this.$seek.value = '0';
            this._renderStep();
        },

        _renderSource(lines) {
            this.$source.innerHTML = lines
                .map((ln) => `<span class="code-trace-line">${this._esc(ln) || ' '}</span>`)
                .join('');
        },

        _esc(s) {
            return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        },

        _goto(i) {
            if (!this.steps.length) return;
            this.idx = Math.max(0, Math.min(this.steps.length - 1, i));
            this.$seek.value = String(this.idx);
            this._renderStep();
        },

        _play() {
            if (!this.steps.length) return;
            this.playing = true;
            this.$play.textContent = '⏸ 暂停';
            this._timer = setInterval(() => {
                if (this.idx >= this.steps.length - 1) { this._stop(); return; }
                this._goto(this.idx + 1);
            }, this.speed);
        },

        _stop() {
            this.playing = false;
            this.$play.textContent = '▶ 播放';
            if (this._timer) { clearInterval(this._timer); this._timer = null; }
        },

        _renderStep() {
            const step = this.steps[this.idx];
            if (!step) return;
            this.$stepLabel.textContent = `${this.idx + 1} / ${this.steps.length}`;

            // 高亮当前行
            const lines = this.$source.querySelectorAll('.code-trace-line');
            lines.forEach((el, i) => el.classList.toggle('code-trace-line--active', i === (step.line - 1)));
            const activeEl = lines[step.line - 1];
            if (activeEl && activeEl.scrollIntoView) {
                activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
            }

            // 变量面板
            const varEntries = Object.entries(step.vars).filter(([k]) => k !== 'arr' && k !== 'stack');
            this.$vars.innerHTML = varEntries.map(([k, v]) => {
                const changed = JSON.stringify(this._prevVars[k]) !== JSON.stringify(v);
                const valStr = this._fmtVal(v);
                return `<div class="code-trace-var${changed ? ' code-trace-var--changed' : ''}">
                    <span class="code-trace-var__name">${this._esc(k)}</span>
                    <span class="code-trace-var__val">${this._esc(valStr)}</span>
                </div>`;
            }).join('') || '<div class="code-trace-var" style="opacity:.5">(无变量)</div>';
            this._prevVars = {};
            varEntries.forEach(([k, v]) => { this._prevVars[k] = v; });

            // 数组
            const arr = step.arrOverride || step.vars.arr;
            if (Array.isArray(arr)) {
                this.$array.innerHTML = arr.map((v, i) => {
                    const hi = step.highlight || {};
                    const cls = ['code-trace-cell'];
                    if (hi.i === i || hi.j === i) cls.push('code-trace-cell--ptr');
                    if (hi.j2 === i) cls.push('code-trace-cell--ptr2');
                    if (hi.swap && (hi.j === i || hi.j2 === i)) cls.push('code-trace-cell--swap');
                    return `<div class="${cls.join(' ')}">
                        <span>${this._esc(String(v))}</span>
                        <span class="code-trace-cell__idx">[${i}]</span>
                    </div>`;
                }).join('');
            } else {
                this.$array.innerHTML = '<div style="opacity:.5;font-family:monospace">(无数组)</div>';
            }

            // stdout
            this.$stdout.textContent = (step.stdout || []).join('\n') + (step.msg ? `\n# ${step.msg}` : '');
        },

        _fmtVal(v) {
            if (Array.isArray(v)) return '[' + v.join(', ') + ']';
            if (v === undefined) return 'undefined';
            if (v === null) return 'null';
            if (typeof v === 'object') return JSON.stringify(v);
            return String(v);
        }
    };

    global.CodeTrace = CodeTrace;
    global.initCodeTrace = function () { CodeTrace.init(); };
    global.destroyCodeTrace = function () { CodeTrace.destroy(); };
})(window);

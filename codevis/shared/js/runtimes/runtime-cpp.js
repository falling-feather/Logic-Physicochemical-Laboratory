/**
 * Codevis · C/C++ Runtime backend
 *
 * 基于 JSCPP（纯 JS C++ 子集解释器，~1MB）。
 *
 * Trace 策略：prelude + stdout 协议
 *   - 我们在用户代码前拼接一段 inline helper（markPtr/markSwap/markArray/snap），
 *     这些 helper 把特殊指令打到 stdout：
 *       @@CV_PTR <i> <j> <j2>
 *       @@CV_SWAP
 *       @@CV_ARR <n> <v0> <v1> ... <vn-1>
 *       @@CV_SNAP <name> <int>
 *   - runtime 拦截 stdout，把指令行翻译为 trace 帧，其他行进 STDOUT 面板。
 *
 * 共享给 'c' 和 'cpp' 两种语言键。
 */
(function (global) {
    'use strict';
    if (!global.CvRuntime) {
        console.error('[runtime-cpp] CvRuntime not loaded');
        return;
    }

    const PRELUDE = `
#include <cstdio>
inline void markPtr(int i, int j, int j2) { printf("@@CV_PTR %d %d %d\\n", i, j, j2); }
inline void markPtr2(int i, int j) { printf("@@CV_PTR %d %d -1\\n", i, j); }
inline void markSwap() { printf("@@CV_SWAP\\n"); }
inline void markArray(int* a, int n) { printf("@@CV_ARR %d", n); for (int _i = 0; _i < n; _i++) printf(" %d", a[_i]); printf("\\n"); }
inline void snapInt(const char* name, int v) { printf("@@CV_SNAP %s %d\\n", name, v); }
`;

    function parseTraceLine(line, state) {
        // 返回 { frame?, append? } 或 null（无法识别，按 stdout 处理）
        const m = line.match(/^@@CV_(PTR|SWAP|ARR|SNAP)\b(.*)$/);
        if (!m) return null;
        const tag = m[1];
        const rest = m[2].trim();
        if (tag === 'PTR') {
            const parts = rest.split(/\s+/).map(Number);
            const h = { i: parts[0], j: parts[1] };
            if (!isNaN(parts[2]) && parts[2] >= 0) h.j2 = parts[2];
            state.lastVars.i = h.i;
            state.lastVars.j = h.j;
            return { frame: { highlight: h } };
        }
        if (tag === 'SWAP') {
            return { frame: { highlight: { swap: true } } };
        }
        if (tag === 'ARR') {
            const parts = rest.split(/\s+/).map(Number);
            const n = parts[0];
            const arr = parts.slice(1, 1 + n);
            state.lastArr = arr;
            state.lastVars.arr = arr.slice();
            return { frame: { highlight: {}, arrOverride: arr.slice() } };
        }
        if (tag === 'SNAP') {
            const sp = rest.indexOf(' ');
            const name = sp > 0 ? rest.slice(0, sp) : rest;
            const val = sp > 0 ? Number(rest.slice(sp + 1)) : 0;
            state.lastVars[name] = val;
            return { append: true }; // 不产生新帧
        }
        return null;
    }

    const cppBackend = {
        async trace({ code, input = '', maxSteps = 3000 }) {
            if (typeof JSCPP === 'undefined') {
                return { steps: [], error: 'JSCPP 未加载，无法执行 C/C++。' };
            }

            const steps = [];
            const stdout = [];
            const state = { lastVars: {}, lastArr: null };
            let buffer = '';

            const pushFrame = (info) => {
                if (steps.length >= maxSteps) {
                    throw new Error('__cv_abort__:' + maxSteps);
                }
                const frame = {
                    line: 0,
                    vars: Object.assign({}, state.lastVars),
                    highlight: info.highlight || {},
                    msg: '',
                    stdout: stdout.slice()
                };
                if (info.arrOverride) frame.arrOverride = info.arrOverride;
                else if (state.lastArr) frame.arrOverride = state.lastArr.slice();
                steps.push(frame);
            };

            const handleLine = (line) => {
                const parsed = parseTraceLine(line, state);
                if (parsed && parsed.frame) {
                    pushFrame(parsed.frame);
                } else if (parsed && parsed.append) {
                    // snap：只更新 vars，不新帧
                } else {
                    // 普通 stdout
                    stdout.push(line);
                }
            };

            const config = {
                stdio: {
                    write: (s) => {
                        buffer += s;
                        let nl;
                        while ((nl = buffer.indexOf('\n')) >= 0) {
                            const line = buffer.slice(0, nl);
                            buffer = buffer.slice(nl + 1);
                            handleLine(line);
                        }
                    }
                },
                unsigned_overflow: 'warn',
                maxTimeout: 8000
            };

            const fullCode = PRELUDE + '\n' + code;

            try {
                // JSCPP.run 是同步的；包在 Promise 里让 UI 不卡死
                await new Promise((resolve, reject) => {
                    setTimeout(() => {
                        try {
                            JSCPP.run(fullCode, input, config);
                            // 处理 buffer 残留
                            if (buffer.length > 0) {
                                handleLine(buffer);
                                buffer = '';
                            }
                            resolve();
                        } catch (e) {
                            reject(e);
                        }
                    }, 0);
                });
            } catch (err) {
                const msg = (err && err.message) ? err.message : String(err);
                if (msg.startsWith('__cv_abort__')) {
                    return { steps, error: `执行超过最大步数 ${maxSteps}，已中断。` };
                }
                return { steps, error: 'C/C++ 错误：' + msg };
            }

            if (steps.length === 0 && (stdout.length > 0 || Object.keys(state.lastVars).length > 0)) {
                steps.push({
                    line: 0,
                    vars: Object.assign({}, state.lastVars),
                    highlight: {},
                    msg: '',
                    stdout: stdout.slice(),
                    arrOverride: state.lastArr ? state.lastArr.slice() : undefined
                });
            } else if (steps.length > 0) {
                // \u8865\u4e00\u4e2a final \u5e27\uff0c\u4ee5\u4fbf UI \u770b\u5230\u6700\u540e\u4e00\u6b21 mark \u4e4b\u540e\u624d\u4ea7\u751f\u7684 stdout\uff08\u4f8b\u5982 \u201cfound index\u201d\uff09
                const last = steps[steps.length - 1];
                if (stdout.length > (last.stdout ? last.stdout.length : 0)) {
                    steps.push({
                        line: 0,
                        vars: Object.assign({}, state.lastVars),
                        highlight: {},
                        msg: '',
                        stdout: stdout.slice(),
                        arrOverride: state.lastArr ? state.lastArr.slice() : undefined
                    });
                }
            }

            return { steps };
        }
    };

    global.CvRuntime.register('cpp', cppBackend);
    global.CvRuntime.register('c', cppBackend);
})(window);

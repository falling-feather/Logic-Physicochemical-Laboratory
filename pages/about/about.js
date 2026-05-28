/* ═══════════════════════════════════════════════════════════════
 * About 模块 —— 自动同步仓库 Markdown 渲染（开源协议 / 更新日志）
 *
 * - 开源协议：从 LICENSE.md 拉取并整段渲染
 * - 更新日志：从 README.md 拉取，截取 "## 📝 更新日志" 段落
 *
 * 按需懒加载 marked.js（jsDelivr CDN），结果在内存中缓存，
 * 同一会话内不再重复网络请求。
 * ═══════════════════════════════════════════════════════════════ */

(() => {
    'use strict';

    const MARKED_CDN = 'https://cdn.jsdelivr.net/npm/marked@12.0.0/marked.min.js';
    const cache = Object.create(null);
    let markedPromise = null;

    /** 懒加载 marked.js */
    function loadMarked() {
        if (window.marked) return Promise.resolve(window.marked);
        if (markedPromise) return markedPromise;
        markedPromise = new Promise((resolve, reject) => {
            const s = document.createElement('script');
            s.src = MARKED_CDN;
            s.crossOrigin = 'anonymous';
            s.onload = () => {
                if (window.marked) resolve(window.marked);
                else reject(new Error('marked.js 已加载但全局变量缺失'));
            };
            s.onerror = () => reject(new Error('marked.js 加载失败（请检查网络或 CDN 可达性）'));
            document.head.appendChild(s);
        });
        return markedPromise;
    }

    /** 拉取文本，会话内缓存 */
    async function fetchText(url) {
        if (cache[url]) return cache[url];
        const res = await fetch(url, { cache: 'no-cache' });
        if (!res.ok) throw new Error(`无法加载 ${url}（HTTP ${res.status}）`);
        const txt = await res.text();
        cache[url] = txt;
        return txt;
    }

    /** 从 README.md 中截取 "## 📝 更新日志" 起到下一个二级标题之前的内容 */
    function extractChangelog(readme) {
        const lines = readme.split(/\r?\n/);
        const startIdx = lines.findIndex((l) => /^##\s+📝\s*更新日志/.test(l));
        if (startIdx === -1) return readme;
        let endIdx = lines.length;
        for (let i = startIdx + 1; i < lines.length; i++) {
            if (/^##\s+/.test(lines[i])) {
                endIdx = i;
                break;
            }
        }
        return lines.slice(startIdx, endIdx).join('\n');
    }

    /** 简单的 HTML 转义（用于内容回退） */
    function escapeHtml(s) {
        return String(s)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    /** 时间戳格式化 */
    function fmtTime(d) {
        const pad = (n) => String(n).padStart(2, '0');
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    }

    /** 主渲染函数 */
    async function render(targetId, { url, transform, title, subtitle }) {
        const root = document.getElementById(targetId);
        if (!root) return;
        root.innerHTML = `<div class="about-doc__loading">正在加载内容…</div>`;

        try {
            const [marked, src] = await Promise.all([loadMarked(), fetchText(url)]);
            const md = transform ? transform(src) : src;

            // marked v12 推荐 API：marked.parse(md, options)
            const html = marked.parse(md, { gfm: true, breaks: false });

            root.innerHTML = `
                <header class="about-doc__header">
                    <span class="about-doc__eyebrow">${escapeHtml(subtitle)}</span>
                    <h1 class="about-doc__title">${escapeHtml(title)}</h1>
                    <p class="about-doc__source">
                        <span>内容自动同步自仓库 <code>${escapeHtml(url)}</code></span>
                        <span>· 加载时间 ${fmtTime(new Date())}</span>
                        <button type="button" data-action="refresh" title="清除缓存并重新拉取">⟳ 重新拉取</button>
                    </p>
                </header>
                <article class="about-doc__body markdown-body">${html}</article>
            `;

            const refreshBtn = root.querySelector('[data-action="refresh"]');
            if (refreshBtn) {
                refreshBtn.addEventListener('click', () => {
                    delete cache[url];
                    render(targetId, { url, transform, title, subtitle });
                });
            }
        } catch (err) {
            root.innerHTML = `
                <div class="about-doc__error">
                    <h2>加载失败</h2>
                    <p>${escapeHtml(err.message || String(err))}</p>
                    <p>可尝试刷新页面，或前往仓库查看：<code>${escapeHtml(url)}</code></p>
                </div>
            `;
        }
    }

    // ─── 暴露给 router.js 调用 ─────────────────────────────────────
    window.initLicense = function () {
        render('about-license-content', {
            url: 'LICENSE.md',
            title: '开源协议',
            subtitle: 'LICENSE · 使用许可',
        });
    };

    window.initChangelog = function () {
        render('about-changelog-content', {
            url: 'README.md',
            transform: extractChangelog,
            title: '更新日志',
            subtitle: 'CHANGELOG · 从 README 自动同步',
        });
    };
})();

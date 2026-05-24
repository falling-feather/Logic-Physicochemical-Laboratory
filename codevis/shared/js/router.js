/* ============================================================
 * Codevis · 简化路由
 * hash 路由 + page enter/leave 回调
 * ============================================================ */
(function (global) {
    'use strict';

    const CvRouter = {
        currentPage: 'home',
        pages: {},

        register(pageId, hooks) {
            // hooks: { onEnter?: fn, onLeave?: fn }
            this.pages[pageId] = hooks || {};
        },

        init() {
            window.addEventListener('hashchange', () => this._handle());
            this._handle(true);
        },

        navigateTo(pageId) {
            if (this.currentPage === pageId) return;
            window.location.hash = '#' + pageId;
        },

        _handle(isInitial) {
            const hash = (window.location.hash || '#home').slice(1).split('?')[0] || 'home';
            const target = document.getElementById('cv-page-' + hash) ? hash : 'home';

            if (!isInitial && this.currentPage && this.pages[this.currentPage]) {
                try { this.pages[this.currentPage].onLeave && this.pages[this.currentPage].onLeave(); }
                catch (e) { console.warn('[CvRouter] onLeave error', e); }
            }

            document.querySelectorAll('.cv-page').forEach(el => el.classList.remove('cv-page--active'));
            const pageEl = document.getElementById('cv-page-' + target);
            if (pageEl) pageEl.classList.add('cv-page--active');

            // nav 高亮
            document.querySelectorAll('.cv-nav-item').forEach(el => {
                el.classList.toggle('cv-nav-item--active', el.dataset.page === target);
            });

            this.currentPage = target;

            // 滚动复位
            window.scrollTo({ top: 0, behavior: isInitial ? 'auto' : 'smooth' });

            if (this.pages[target]) {
                try { this.pages[target].onEnter && this.pages[target].onEnter(); }
                catch (e) { console.warn('[CvRouter] onEnter error', e); }
            }
        }
    };

    global.CvRouter = CvRouter;
})(window);

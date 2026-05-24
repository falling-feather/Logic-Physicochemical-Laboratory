/* ============================================================
 * Codevis · 应用入口
 * ============================================================ */
(function () {
    'use strict';

    function bootstrap() {
        // 注册页面
        if (window.CvRouter) {
            CvRouter.register('home', {
                onEnter: () => window.CvHome && CvHome.init(),
                onLeave: () => window.CvHome && CvHome.destroy && CvHome.destroy()
            });
            CvRouter.register('trace', {
                onEnter: () => window.CodeTrace && CodeTrace.init(),
                onLeave: () => window.CodeTrace && CodeTrace.destroy && CodeTrace.destroy()
            });

            CvRouter.init();
        }

        // 导航事件
        document.querySelectorAll('.cv-nav-item').forEach(el => {
            el.addEventListener('click', (e) => {
                const page = el.dataset.page;
                if (!page) return;
                e.preventDefault();
                CvRouter.navigateTo(page);
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', bootstrap);
    } else {
        bootstrap();
    }
})();

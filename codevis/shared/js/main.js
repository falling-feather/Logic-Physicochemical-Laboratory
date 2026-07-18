/* ============================================================
 * Codevis · 应用入口
 * ============================================================ */
(function () {
    'use strict';

    function bootstrap() {
        // 注册页面
        if (window.CvRouter) {
            CvRouter.register('catalog', { onEnter: () => window.CvCourseCatalog && CvCourseCatalog.init() });
            CvRouter.register('lesson', { onEnter: () => window.CvCourseCatalog && CvCourseCatalog.renderLesson() });
            CvRouter.register('challenge', {
                onEnter: () => window.CvCourseChallenge && CvCourseChallenge.init(),
                onLeave: () => window.CvCourseChallenge && CvCourseChallenge.cancel()
            });
            CvRouter.register('trace', {
                onEnter: () => window.CodeTrace && CodeTrace.init(),
                onLeave: () => {
                    window.CodeTrace && CodeTrace.destroy && CodeTrace.destroy();
                    window.CvRuntime && CvRuntime.cancel();
                }
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

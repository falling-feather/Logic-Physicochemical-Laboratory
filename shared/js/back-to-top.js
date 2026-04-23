/**
 * 返回顶部 FAB（v4.2.17）
 * 在非首页页面，滚动超过 1 屏后出现；点击平滑滚动至顶部。
 */
(function() {
    'use strict';

    const BackToTop = {
        _btn: null,
        _onScroll: null,
        _enabled: false,

        show() {
            if (this._btn) return;
            const btn = document.createElement('button');
            btn.className = 'back-to-top-fab';
            btn.setAttribute('aria-label', '返回顶部');
            btn.setAttribute('data-tip', '返回顶部');
            btn.innerHTML = '<i data-lucide="arrow-up"></i>';
            btn.style.display = 'none'; // 默认隐藏，滚动到位才显示
            btn.addEventListener('click', () => {
                btn.classList.remove('is-rippling');
                void btn.offsetWidth;
                btn.classList.add('is-rippling');
                setTimeout(() => btn.classList.remove('is-rippling'), 600);
                window.scrollTo({ top: 0, behavior: 'smooth' });
            });
            document.body.appendChild(btn);
            this._btn = btn;
            if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [btn] });

            this._onScroll = () => this._update();
            window.addEventListener('scroll', this._onScroll, { passive: true });
            this._enabled = true;
            this._update();
        },

        hide() {
            if (this._btn && this._btn.parentNode) this._btn.parentNode.removeChild(this._btn);
            this._btn = null;
            if (this._onScroll) {
                window.removeEventListener('scroll', this._onScroll);
                this._onScroll = null;
            }
            this._enabled = false;
        },

        _update() {
            if (!this._btn) return;
            const visible = window.scrollY > window.innerHeight;
            if (visible) {
                this._btn.style.display = 'flex';
                this._btn.classList.add('back-to-top-fab--visible');
            } else {
                this._btn.classList.remove('back-to-top-fab--visible');
                // 等淡出后隐藏
                setTimeout(() => {
                    if (this._btn && window.scrollY <= window.innerHeight) {
                        this._btn.style.display = 'none';
                    }
                }, 220);
            }
        }
    };

    window.BackToTop = BackToTop;
})();

// ===== X-03: Theme Switch =====
// v4.2.4 重构：以右下角浮动按钮（FAB）形式呈现，默认黑夜模式，
//        仅在非首页页面显示（由 router 调度 show/hide）。

const ThemeSwitch = {
    _KEY: 'englab-theme',
    _btn: null,

    init() {
        const theme = this._resolve();
        this._apply(theme);
        // 不再默认注入按钮；由 router 在进入非首页时调用 show()
    },

    /** v4.2.4：默认黑夜模式。仅当用户显式存过 'light' 才返回 light。 */
    _resolve() {
        const stored = localStorage.getItem(this._KEY);
        if (stored === 'light') return 'light';
        return 'dark';
    },

    _apply(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        this._updateIcon(theme);
    },

    toggle() {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        const next = current === 'dark' ? 'light' : 'dark';
        localStorage.setItem(this._KEY, next);

        // v4.2.10：图标切换 180° 旋转动画
        if (this._btn) {
            this._btn.classList.add('theme-fab--spinning');
            setTimeout(() => this._btn && this._btn.classList.remove('theme-fab--spinning'), 360);
        }

        // Enable transition, then apply
        document.documentElement.classList.add('theme-transitioning');
        this._apply(next);

        // Update meta theme-color
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.content = next === 'light' ? '#f5f6fa' : '#08090e';

        // Remove transition class after animation
        setTimeout(() => document.documentElement.classList.remove('theme-transitioning'), 350);
    },

    /** v4.2.4：在右下角浮动控件区注入主题切换按钮（由 router 在非首页时调用） */
    show() {
        if (this._btn) return; // 已存在
        const btn = document.createElement('button');
        btn.className = 'theme-fab';
        btn.setAttribute('aria-label', '切换暗/亮主题');
        btn.setAttribute('data-tip', '切换主题');
        btn.addEventListener('click', () => this.toggle());
        document.body.appendChild(btn);
        this._btn = btn;
        this._updateIcon(document.documentElement.getAttribute('data-theme') || 'dark');
    },

    /** v4.2.4：移除右下角主题切换按钮（由 router 在返回首页时调用） */
    hide() {
        if (this._btn && this._btn.parentNode) this._btn.parentNode.removeChild(this._btn);
        this._btn = null;
    },

    _updateIcon(theme) {
        if (!this._btn) return;
        // theme === 'dark' 时显示太阳图标（表示点击切到亮色），反之亮色显示月亮
        const iconName = theme === 'dark' ? 'sun' : 'moon';
        this._btn.innerHTML = `<i data-lucide="${iconName}"></i>`;
        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [this._btn] });
    }
};

window.ThemeSwitch = ThemeSwitch;

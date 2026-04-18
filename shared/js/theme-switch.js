// ===== X-03: Theme Switch =====
// Respects prefers-color-scheme, persists user choice in localStorage.
// Adds a toggle button to the navbar.

const ThemeSwitch = {
    _KEY: 'englab-theme',
    _btn: null,

    init() {
        const theme = this._resolve();
        this._apply(theme);
        this._injectToggle();
    },

    /** Determine the active theme: stored preference > system preference > dark */
    _resolve() {
        const stored = localStorage.getItem(this._KEY);
        if (stored === 'light' || stored === 'dark') return stored;
        if (window.matchMedia && window.matchMedia('(prefers-color-scheme: light)').matches) return 'light';
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

        // Enable transition, then apply
        document.documentElement.classList.add('theme-transitioning');
        this._apply(next);

        // Update meta theme-color
        const meta = document.querySelector('meta[name="theme-color"]');
        if (meta) meta.content = next === 'light' ? '#f5f6fa' : '#08090e';

        // Remove transition class after animation
        setTimeout(() => document.documentElement.classList.remove('theme-transitioning'), 350);
    },

    _injectToggle() {
        const navContainer = document.querySelector('.nav-container');
        if (!navContainer) return;

        const btn = document.createElement('button');
        btn.className = 'theme-toggle';
        btn.setAttribute('aria-label', '切换主题');
        btn.setAttribute('title', '切换暗/亮主题');
        btn.innerHTML = '<i data-lucide="moon"></i>';
        btn.addEventListener('click', () => this.toggle());

        navContainer.appendChild(btn);
        this._btn = btn;

        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [btn] });

        this._updateIcon(document.documentElement.getAttribute('data-theme') || 'dark');

        // Listen for system theme changes
        if (window.matchMedia) {
            window.matchMedia('(prefers-color-scheme: light)').addEventListener('change', (e) => {
                // Only auto-switch if user hasn't set explicit preference
                if (!localStorage.getItem(this._KEY)) {
                    this._apply(e.matches ? 'light' : 'dark');
                }
            });
        }
    },

    _updateIcon(theme) {
        if (!this._btn) return;
        const iconName = theme === 'dark' ? 'sun' : 'moon';
        this._btn.innerHTML = `<i data-lucide="${iconName}"></i>`;
        if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [this._btn] });
    }
};

/**
 * FAB 折叠触发器（v4.2.19）
 * 默认折叠状态：仅显示主控按钮；点击展开 4 个功能 FAB（错峰飞入）。
 */
(function() {
    'use strict';

    const FabTrigger = {
        _btn: null,
        _scrim: null,
        _trace: null,
        _expanded: false,
        _onDocClick: null,
        _onKeyDown: null,

        show() {
            if (this._btn) return;
            // 默认折叠
            document.body.setAttribute('data-fab-expanded', 'false');
            this._expanded = false;

            const btn = document.createElement('button');
            btn.className = 'fab-trigger';
            btn.setAttribute('aria-label', '展开/收起浮动按钮');
            btn.setAttribute('data-tip', '更多操作');
            btn.innerHTML = '<i class="fab-trigger-icon fab-trigger-icon--menu" data-lucide="more-vertical"></i><i class="fab-trigger-icon fab-trigger-icon--close" data-lucide="x"></i><span class="fab-trigger-badge" aria-hidden="true">4</span>';
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.toggle();
                // v4.2.26：点击 ripple 水波
                btn.classList.remove('is-rippling');
                void btn.offsetWidth;
                btn.classList.add('is-rippling');
                setTimeout(() => btn.classList.remove('is-rippling'), 600);
            });
            document.body.appendChild(btn);
            this._btn = btn;
            if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [btn] });

            // v4.2.27：创建半透明遮罩（默认隐藏）
            const scrim = document.createElement('div');
            scrim.className = 'fab-scrim';
            scrim.addEventListener('click', () => this.collapse());
            document.body.appendChild(scrim);
            this._scrim = scrim;

            // v4.2.32：fan-out 弧形轨迹 SVG（仅桌面可见）
            // v4.2.36：内嵌走马灯微粒（SMIL animateMotion 沿 path 循环）
            const trace = document.createElement('div');
            trace.className = 'fab-trace';
            trace.innerHTML = '<svg width="250" height="250" viewBox="0 0 250 250" aria-hidden="true">'
                + '<defs>'
                + '<linearGradient id="fab-trace-grad" gradientUnits="userSpaceOnUse" x1="125" y1="15" x2="23" y2="83">'
                + '<stop offset="0%" stop-color="#5b8dce"/>'
                + '<stop offset="33%" stop-color="#f472b6"/>'
                + '<stop offset="66%" stop-color="#00ffd5"/>'
                + '<stop offset="100%" stop-color="#a78bfa"/>'
                + '</linearGradient>'
                + '<path id="fab-trace-path" d="M 125 15 A 110 110 0 0 0 23 83"/>'
                + '</defs>'
                + '<use class="fab-trace-line" href="#fab-trace-path" stroke="url(#fab-trace-grad)" fill="none"/>'
                // v4.2.41：4 个静默定位锚点（与 4 FAB 弧线角度对应）
                + '<g class="fab-trace-anchors">'
                + '<circle cx="125" cy="15"  r="2.5" fill="#5b8dce" opacity="0.85"/>'
                + '<circle cx="83.4" cy="22.9" r="2.5" fill="#f472b6" opacity="0.85"/>'
                + '<circle cx="47.2" cy="47.2" r="2.5" fill="#00ffd5" opacity="0.85"/>'
                + '<circle cx="22.9" cy="83.4" r="2.5" fill="#a78bfa" opacity="0.85"/>'
                + '</g>'
                + '<circle class="fab-trace-particle" r="3.5" fill="#00ffd5">'
                + '<animateMotion dur="2.4s" repeatCount="indefinite" rotate="auto">'
                + '<mpath href="#fab-trace-path"/>'
                + '</animateMotion>'
                + '</circle>'
                + '<circle class="fab-trace-particle fab-trace-particle--alt" r="3" fill="#a78bfa">'
                + '<animateMotion dur="2.4s" begin="1.2s" repeatCount="indefinite" rotate="auto">'
                + '<mpath href="#fab-trace-path"/>'
                + '</animateMotion>'
                + '</circle>'
                + '</svg>';
            document.body.appendChild(trace);
            this._trace = trace;

            // v4.2.25：每会话首次出现时跳动 2 次，提示用户发现
            try {
                if (!sessionStorage.getItem('englab-fab-discovered')) {
                    btn.classList.add('fab-trigger--bouncing');
                    setTimeout(() => btn.classList.remove('fab-trigger--bouncing'), 1500);
                    sessionStorage.setItem('englab-fab-discovered', '1');
                }
            } catch (e) { /* sessionStorage 不可用则跳过 */ }

            // v4.2.20：点击 FAB 面板外区域自动收起
            this._onDocClick = (e) => {
                if (!this._expanded) return;
                const t = e.target;
                if (!t || !t.closest) return;
                if (t.closest('.fab-trigger') ||
                    t.closest('.theme-fab') ||
                    t.closest('.favorite-fab') ||
                    t.closest('.experiment-guide-help-btn') ||
                    t.closest('.back-to-top-fab') ||
                    t.closest('.experiment-export-btn') ||
                    t.closest('.experiment-export-menu')) {
                    return; // 点击在任何 FAB / 导出菜单 上，不收起
                }
                this.collapse();
            };
            document.addEventListener('click', this._onDocClick, true);

            // v4.2.21：ESC 键收起菜单（键盘友好）
            this._onKeyDown = (e) => {
                if (e.key === 'Escape' && this._expanded) {
                    this.collapse();
                }
            };
            document.addEventListener('keydown', this._onKeyDown);
        },

        hide() {
            if (this._btn && this._btn.parentNode) this._btn.parentNode.removeChild(this._btn);
            this._btn = null;
            if (this._scrim && this._scrim.parentNode) this._scrim.parentNode.removeChild(this._scrim);
            this._scrim = null;
            if (this._trace && this._trace.parentNode) this._trace.parentNode.removeChild(this._trace);
            this._trace = null;
            document.body.removeAttribute('data-fab-expanded');
            this._expanded = false;
            if (this._onDocClick) {
                document.removeEventListener('click', this._onDocClick, true);
                this._onDocClick = null;
            }
            if (this._onKeyDown) {
                document.removeEventListener('keydown', this._onKeyDown);
                this._onKeyDown = null;
            }
        },

        collapse() {
            if (!this._expanded) return;
            this._expanded = false;
            document.body.setAttribute('data-fab-expanded', 'false');
            // v4.2.33：收起时反向错峰（远端先归位 → 近端最后）
            document.body.setAttribute('data-fab-collapsing', 'true');
            setTimeout(() => {
                // 仅当此刻仍是收起状态才清除（防止用户瞬间再次展开）
                if (!this._expanded) document.body.removeAttribute('data-fab-collapsing');
            }, 450);
            if (this._btn) {
                this._btn.classList.remove('fab-trigger--open');
                this._btn.setAttribute('data-tip', '更多操作');
            }
            if (this._scrim) this._scrim.classList.remove('fab-scrim--visible');
        },

        toggle() {
            // v4.2.33：收起路径走 collapse() 以复用反向动画逻辑
            if (this._expanded) {
                this.collapse();
                return;
            }
            this._expanded = true;
            document.body.setAttribute('data-fab-expanded', 'true');
            document.body.removeAttribute('data-fab-collapsing');
            if (this._btn) {
                this._btn.classList.toggle('fab-trigger--open', this._expanded);
                this._btn.setAttribute('data-tip', this._expanded ? '收起菜单' : '更多操作');
            }
            if (this._scrim) this._scrim.classList.toggle('fab-scrim--visible', this._expanded);
            // v4.2.29：展开瞬间发出青色光环
            if (this._expanded) {
                const halo = document.createElement('span');
                halo.className = 'fab-trigger-halo';
                document.body.appendChild(halo);
                setTimeout(() => { if (halo.parentNode) halo.parentNode.removeChild(halo); }, 650);
            }
        }
    };

    window.FabTrigger = FabTrigger;
})();

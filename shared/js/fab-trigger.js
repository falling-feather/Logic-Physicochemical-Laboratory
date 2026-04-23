/**
 * FAB 折叠触发器（v4.2.19）
 * 默认折叠状态：仅显示主控按钮；点击展开 4 个功能 FAB（错峰飞入）。
 */
(function() {
    'use strict';

    const FabTrigger = {
        _btn: null,
        _expanded: false,

        show() {
            if (this._btn) return;
            // 默认折叠
            document.body.setAttribute('data-fab-expanded', 'false');
            this._expanded = false;

            const btn = document.createElement('button');
            btn.className = 'fab-trigger';
            btn.setAttribute('aria-label', '展开/收起浮动按钮');
            btn.setAttribute('data-tip', '更多操作');
            btn.innerHTML = '<i data-lucide="more-vertical"></i>';
            btn.addEventListener('click', () => this.toggle());
            document.body.appendChild(btn);
            this._btn = btn;
            if (typeof lucide !== 'undefined') lucide.createIcons({ nodes: [btn] });
        },

        hide() {
            if (this._btn && this._btn.parentNode) this._btn.parentNode.removeChild(this._btn);
            this._btn = null;
            document.body.removeAttribute('data-fab-expanded');
            this._expanded = false;
        },

        toggle() {
            this._expanded = !this._expanded;
            document.body.setAttribute('data-fab-expanded', this._expanded ? 'true' : 'false');
            if (this._btn) {
                this._btn.classList.toggle('fab-trigger--open', this._expanded);
                this._btn.setAttribute('data-tip', this._expanded ? '收起菜单' : '更多操作');
            }
        }
    };

    window.FabTrigger = FabTrigger;
})();

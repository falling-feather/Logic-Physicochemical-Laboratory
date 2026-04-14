// Shared zoom modal for physics experiments.
const PhysicsZoom = {
    modal: null,
    host: null,
    titleEl: null,
    closeBtn: null,
    originalParent: null,
    movedCanvas: null,
    movedPlaceholder: null,
    originalInlineStyle: null,
    originalRect: null,
    _resizeHandlerBound: null,

    init() {
        this._ensureModal();
        this._attachButtons();
    },

    _ensureModal() {
        if (document.getElementById('physics-zoom-modal')) {
            this.modal = document.getElementById('physics-zoom-modal');
            this.host = document.getElementById('physics-zoom-host');
            this.titleEl = document.getElementById('physics-zoom-title');
            this.closeBtn = document.getElementById('physics-zoom-close');
            return;
        }

        const modal = document.createElement('div');
        modal.id = 'physics-zoom-modal';
        modal.className = 'physics-zoom-modal';
        modal.innerHTML = `
            <div class="physics-zoom-modal__inner" role="dialog" aria-modal="true" aria-label="物理实验放大视图">
                <div class="physics-zoom-modal__toolbar">
                    <span id="physics-zoom-title" class="physics-zoom-modal__title">放大视图</span>
                    <button id="physics-zoom-close" class="physics-zoom-modal__close" type="button">关闭</button>
                </div>
                <div id="physics-zoom-host" class="physics-zoom-modal__host"></div>
            </div>
        `;
        document.body.appendChild(modal);

        this.modal = modal;
        this.host = document.getElementById('physics-zoom-host');
        this.titleEl = document.getElementById('physics-zoom-title');
        this.closeBtn = document.getElementById('physics-zoom-close');

        this.closeBtn.addEventListener('click', () => this.close());
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) this.close();
        });
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.classList.contains('open')) this.close();
        });
        this._resizeHandlerBound = () => this._syncScale();
        window.addEventListener('resize', this._resizeHandlerBound);
    },

    _attachButtons() {
        const sections = document.querySelectorAll('#page-physics .content-section[data-module]');
        sections.forEach(section => {
            const canvas = section.querySelector('canvas');
            if (!canvas) return;
            if (section.querySelector('.physics-zoom-btn')) return;

            const controls = section.querySelector(
                '.physics-controls, .em-controls, .wave-controls, .rel-actions, .circ-btns, .energy-controls, .circuit-controls, .emi-controls, .ac-controls, .grav-controls, .proj-action-row, .kin-action-row'
            );
            if (!controls) return;

            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'physics-zoom-btn';
            btn.textContent = '放大';
            btn.addEventListener('click', () => {
                const title = section.querySelector('h2, h3')?.textContent?.trim() || '物理实验';
                this.open(canvas, title);
            });
            controls.appendChild(btn);
        });
    },

    open(canvas, title) {
        if (!canvas || this.movedCanvas) return;
        // 画布暂时挂到 modal 宿主时，各实验 resize 必须用 movedCanvas 判断并跳过，否则会按宿主宽度重算而破坏原比例与缓冲区。
        this.originalParent = canvas.parentElement;
        this.movedCanvas = canvas;
        this.movedPlaceholder = document.createComment('physics-zoom-placeholder');
        this.originalInlineStyle = canvas.getAttribute('style') || '';
        this.originalRect = canvas.getBoundingClientRect();
        this.originalParent.insertBefore(this.movedPlaceholder, canvas);
        this.host.appendChild(canvas);
        this.titleEl.textContent = title + ' · 放大视图';

        // 按原始尺寸作为基准，只做等比缩放，避免填充导致比例变化
        this.movedCanvas.style.width = this.originalRect.width + 'px';
        this.movedCanvas.style.height = this.originalRect.height + 'px';
        this.movedCanvas.style.transformOrigin = 'center center';

        this.modal.classList.add('open');
        this._syncScale();
    },

    _syncScale() {
        if (!this.movedCanvas || !this.originalRect || !this.host) return;
        const hostRect = this.host.getBoundingClientRect();
        if (hostRect.width <= 0 || hostRect.height <= 0 || this.originalRect.width <= 0 || this.originalRect.height <= 0) return;

        const sx = hostRect.width / this.originalRect.width;
        const sy = hostRect.height / this.originalRect.height;
        const scale = Math.min(sx, sy);
        this.movedCanvas.style.transform = `scale(${scale})`;
    },

    close() {
        if (!this.movedCanvas || !this.originalParent || !this.movedPlaceholder) return;
        // 先还原原始 inline 样式，确保缩小后尺寸完全回到放大前
        if (this.originalInlineStyle) {
            this.movedCanvas.setAttribute('style', this.originalInlineStyle);
        } else {
            this.movedCanvas.removeAttribute('style');
        }
        this.originalParent.insertBefore(this.movedCanvas, this.movedPlaceholder);
        this.originalParent.removeChild(this.movedPlaceholder);
        this.movedCanvas = null;
        this.originalParent = null;
        this.movedPlaceholder = null;
        this.originalInlineStyle = null;
        this.originalRect = null;
        this.modal.classList.remove('open');
    }
};

window.PhysicsZoom = PhysicsZoom;
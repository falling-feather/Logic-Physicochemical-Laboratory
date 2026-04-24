// ===== Global Experiment Search (v4.5-α1) =====
// 全局搜索：实验名 + 描述模糊匹配，跨学科聚合，键盘 ↑↓ Enter ESC 全支持
// 触发：导航栏放大镜按钮 / Ctrl+K / Cmd+K

const GlobalSearch = {
    overlay: null,
    input: null,
    list: null,
    items: [],          // 扁平化所有 {subjectId, subjectLabel, subjectColor, id, title, description}
    results: [],        // 当前过滤结果
    activeIndex: 0,
    isOpen: false,
    _trigger: null,

    init() {
        this.overlay = document.getElementById('global-search-overlay');
        if (!this.overlay) return; // HTML 未注入则跳过
        this.input = this.overlay.querySelector('.gsearch__input');
        this.list = this.overlay.querySelector('.gsearch__list');
        this._trigger = document.getElementById('nav-search-trigger');
        this._buildIndex();

        // 绑定触发按钮
        if (this._trigger) this._trigger.addEventListener('click', () => this.open());
        // 全局快捷键 Ctrl+K / Cmd+K
        window.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'k') {
                e.preventDefault();
                this.isOpen ? this.close() : this.open();
            } else if (e.key === 'Escape' && this.isOpen) {
                e.preventDefault();
                this.close();
            } else if (this.isOpen && (e.key === 'ArrowDown' || e.key === 'ArrowUp' || e.key === 'Enter')) {
                e.preventDefault();
                if (e.key === 'ArrowDown') this._move(1);
                else if (e.key === 'ArrowUp') this._move(-1);
                else this._activate();
            }
        });
        // 点击遮罩关闭
        this.overlay.addEventListener('click', (e) => {
            if (e.target === this.overlay) this.close();
        });
        // 输入框监听
        this.input.addEventListener('input', () => this._updateResults());
        // 列表点击委托
        this.list.addEventListener('click', (e) => {
            const li = e.target.closest('.gsearch__item');
            if (!li) return;
            this.activeIndex = parseInt(li.dataset.index, 10) || 0;
            this._activate();
        });
        // 鼠标悬停高亮
        this.list.addEventListener('mousemove', (e) => {
            const li = e.target.closest('.gsearch__item');
            if (!li) return;
            const idx = parseInt(li.dataset.index, 10);
            if (idx !== this.activeIndex) {
                this.activeIndex = idx;
                this._highlight();
            }
        });
    },

    _buildIndex() {
        if (typeof CONFIG === 'undefined' || !CONFIG.experiments) return;
        const out = [];
        for (const [subjectId, list] of Object.entries(CONFIG.experiments)) {
            const meta = (CONFIG.pages && CONFIG.pages[subjectId]) || { label: subjectId, accent: 'blue' };
            const color = this._accentColor(meta.accent);
            for (const exp of list) {
                out.push({
                    subjectId,
                    subjectLabel: meta.label,
                    subjectColor: color,
                    id: exp.id,
                    title: exp.title,
                    description: exp.description || '',
                    icon: exp.icon || 'square',
                    upcoming: exp.variant === 'upcoming'
                });
            }
        }
        this.items = out;
    },

    _accentColor(accent) {
        switch (accent) {
            case 'blue':   return '#3aa9ff';
            case 'purple': return '#a98aff';
            case 'green':  return '#4ade80';
            case 'orange': return '#fb923c';
            case 'teal':   return '#2dd4bf';
            default:       return '#3aa9ff';
        }
    },

    open() {
        if (this.isOpen) return;
        this.isOpen = true;
        this.overlay.classList.add('gsearch--visible');
        this.input.value = '';
        this.activeIndex = 0;
        this._updateResults();
        // 锁滚动
        document.body.style.overflow = 'hidden';
        // 自动 focus，等过渡生效
        setTimeout(() => this.input.focus(), 30);
    },

    close() {
        if (!this.isOpen) return;
        this.isOpen = false;
        this.overlay.classList.remove('gsearch--visible');
        document.body.style.overflow = '';
        // 还焦点给触发按钮
        if (this._trigger) this._trigger.focus();
    },

    _updateResults() {
        const q = (this.input.value || '').trim().toLowerCase();
        if (!q) {
            // 空查询：展示前 12 条作为推荐
            this.results = this.items.slice(0, 12);
        } else {
            const tokens = q.split(/\s+/).filter(Boolean);
            const scored = [];
            for (const it of this.items) {
                const hay = (it.title + ' ' + it.description + ' ' + it.subjectLabel).toLowerCase();
                let score = 0;
                let allMatch = true;
                for (const t of tokens) {
                    if (!hay.includes(t)) { allMatch = false; break; }
                    if (it.title.toLowerCase().includes(t)) score += 10;
                    else if (it.subjectLabel.toLowerCase().includes(t)) score += 5;
                    else score += 2;
                }
                if (allMatch) scored.push({ it, score });
            }
            scored.sort((a, b) => b.score - a.score);
            this.results = scored.slice(0, 30).map(x => x.it);
        }
        this.activeIndex = 0;
        this._render();
    },

    _render() {
        if (!this.results.length) {
            this.list.innerHTML = `<div class="gsearch__empty">无匹配结果，换个关键词试试</div>`;
            return;
        }
        const q = (this.input.value || '').trim().toLowerCase();
        const html = this.results.map((it, i) => {
            const titleHl = this._highlightTerm(it.title, q);
            const descHl = this._highlightTerm(it.description, q);
            return `<button type="button" class="gsearch__item" data-index="${i}" style="--gs-color:${it.subjectColor}">
                <span class="gsearch__icon"><i data-lucide="${it.icon}"></i></span>
                <span class="gsearch__body">
                    <span class="gsearch__title">${titleHl}${it.upcoming ? ' <span class="gsearch__badge">即将上线</span>' : ''}</span>
                    <span class="gsearch__desc">${descHl}</span>
                </span>
                <span class="gsearch__tag">${it.subjectLabel}</span>
            </button>`;
        }).join('');
        this.list.innerHTML = html;
        if (typeof lucide !== 'undefined') lucide.createIcons({ nameAttr: 'data-lucide', attrs: {} });
        this._highlight();
    },

    _highlightTerm(text, q) {
        if (!q || !text) return this._escapeHtml(text);
        const safe = this._escapeHtml(text);
        const tokens = q.split(/\s+/).filter(Boolean);
        let result = safe;
        for (const t of tokens) {
            if (!t) continue;
            const re = new RegExp(`(${t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
            result = result.replace(re, '<mark class="gsearch__mark">$1</mark>');
        }
        return result;
    },

    _escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
    },

    _move(delta) {
        if (!this.results.length) return;
        this.activeIndex = (this.activeIndex + delta + this.results.length) % this.results.length;
        this._highlight();
        // 滚动到可见
        const el = this.list.querySelector(`[data-index="${this.activeIndex}"]`);
        if (el) el.scrollIntoView({ block: 'nearest' });
    },

    _highlight() {
        const items = this.list.querySelectorAll('.gsearch__item');
        items.forEach((el, i) => el.classList.toggle('gsearch__item--active', i === this.activeIndex));
    },

    _activate() {
        const it = this.results[this.activeIndex];
        if (!it) return;
        this.close();
        // 触发跳转：先 hash → router 进入学科 → ModuleSelector.openModule
        if (location.hash !== '#' + it.subjectId) {
            location.hash = it.subjectId;
            // 等 router 转场结束后再 deep-link
            setTimeout(() => {
                try { if (typeof ModuleSelector !== 'undefined') ModuleSelector.openModule(it.subjectId, it.id); } catch (e) {}
            }, 700);
        } else {
            // 已在该学科页：直接 openModule
            try { if (typeof ModuleSelector !== 'undefined') ModuleSelector.openModule(it.subjectId, it.id); } catch (e) {}
        }
    }
};

if (typeof window !== 'undefined') window.GlobalSearch = GlobalSearch;

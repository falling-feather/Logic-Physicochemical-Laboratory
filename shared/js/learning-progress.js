// ===== X-01: Learning Progress System =====
// Tracks which experiments the user has visited using localStorage.
// Renders ✓ badges on gallery cards and a progress bar in page heroes.

const LearningProgress = {
    _KEY: 'englab-progress',
    _data: null, // { visited: { "function-graph": timestamp, ... } }

    init() {
        this._load();
        // Render badges & bars whenever a subject page becomes visible
        this._renderAll();
    },

    // ── Public API ──

    markVisited(moduleId) {
        this._load();
        if (!this._data.visited[moduleId]) {
            this._data.visited[moduleId] = Date.now();
            this._save();
        }
        // Update UI immediately
        this._setBadge(moduleId, true);
        this._updateBarsForModule(moduleId);
    },

    isVisited(moduleId) {
        this._load();
        return !!this._data.visited[moduleId];
    },

    getSubjectProgress(page) {
        const exps = (CONFIG.experiments[page] || []).filter(e => e.variant !== 'upcoming');
        const total = exps.length;
        const visited = exps.filter(e => this.isVisited(e.id)).length;
        return { visited, total, percent: total ? Math.round(visited / total * 100) : 0 };
    },

    getOverallProgress() {
        let visited = 0, total = 0;
        Object.keys(CONFIG.experiments).forEach(page => {
            const p = this.getSubjectProgress(page);
            visited += p.visited;
            total += p.total;
        });
        return { visited, total, percent: total ? Math.round(visited / total * 100) : 0 };
    },

    reset() {
        this._data = { visited: {} };
        this._save();
        this._renderAll();
    },

    // ── Storage ──

    _load() {
        if (this._data) return;
        try {
            const raw = localStorage.getItem(this._KEY);
            this._data = raw ? JSON.parse(raw) : { visited: {} };
        } catch (_) {
            this._data = { visited: {} };
        }
    },

    _save() {
        try {
            localStorage.setItem(this._KEY, JSON.stringify(this._data));
        } catch (_) { /* quota exceeded — silently ignore */ }
    },

    // ── UI Rendering ──

    _renderAll() {
        Object.keys(CONFIG.experiments).forEach(page => {
            this._renderBadges(page);
            this._renderProgressBar(page);
        });
        this._renderHomeProgress();
    },

    /** Add ✓ badges on visited gallery cards */
    _renderBadges(page) {
        const gallery = document.getElementById(`gallery-${page}`);
        if (!gallery) return;
        const cards = gallery.querySelectorAll('.module-card[data-module-target]');
        cards.forEach(card => {
            const mid = card.dataset.moduleTarget;
            this._setBadge(mid, this.isVisited(mid), card);
        });
    },

    _setBadge(moduleId, visited, card) {
        if (!card) {
            // Find across all galleries
            card = document.querySelector(`.module-card[data-module-target="${moduleId}"]`);
        }
        if (!card) return;
        if (visited) {
            card.classList.add('module-card--visited');
        } else {
            card.classList.remove('module-card--visited');
        }
    },

    /** Inject or update a progress bar inside the page hero */
    _renderProgressBar(page) {
        const pageEl = document.getElementById(`page-${page}`);
        if (!pageEl) return;
        const hero = pageEl.querySelector('.page-hero__text');
        if (!hero) return;

        const { visited, total, percent } = this.getSubjectProgress(page);

        let bar = hero.querySelector('.progress-bar');
        if (!bar) {
            bar = document.createElement('div');
            bar.className = 'progress-bar';
            bar.innerHTML = `
                <div class="progress-bar__track">
                    <div class="progress-bar__fill"></div>
                </div>
                <span class="progress-bar__text"></span>
            `;
            hero.appendChild(bar);
        }

        bar.querySelector('.progress-bar__fill').style.width = percent + '%';
        bar.querySelector('.progress-bar__text').textContent =
            visited === 0 ? `共 ${total} 个实验` : `已探索 ${visited}/${total} 个实验`;
    },

    /** Update bars for the subject that owns this moduleId */
    _updateBarsForModule(moduleId) {
        for (const page of Object.keys(CONFIG.experiments)) {
            if (CONFIG.experiments[page].some(e => e.id === moduleId)) {
                this._renderProgressBar(page);
                break;
            }
        }
    },

    /** Render overall progress on the home page */
    _renderHomeProgress() {
        // ── Overall progress widget below tagline ──
        const tagline = document.getElementById('home-tagline');
        if (tagline) {
            const { visited, total, percent } = this.getOverallProgress();
            let widget = document.getElementById('home-progress-widget');
            if (!widget) {
                widget = document.createElement('div');
                widget.id = 'home-progress-widget';
                widget.className = 'home-progress-widget';
                widget.innerHTML = `
                    <div class="home-progress-widget__bar">
                        <div class="home-progress-widget__fill"></div>
                    </div>
                    <span class="home-progress-widget__text"></span>
                `;
                tagline.parentElement.appendChild(widget);
            }
            widget.querySelector('.home-progress-widget__fill').style.width = percent + '%';
            widget.querySelector('.home-progress-widget__text').textContent =
                visited === 0 ? `共 ${total} 个实验等你探索` : `已探索 ${visited}/${total} 个实验`;
        }

        // ── Per-satellite progress chips ──
        const subjects = ['mathematics', 'physics', 'chemistry', 'algorithms', 'biology'];
        subjects.forEach((page, i) => {
            const sat = document.querySelector(`.satellite-${i + 1}[data-target="${page}"]`);
            if (!sat) return;
            const container = sat.querySelector('.satellite-label-container');
            if (!container) return;

            const { visited, total } = this.getSubjectProgress(page);
            let chip = container.querySelector('.satellite-progress');
            if (!chip) {
                chip = document.createElement('span');
                chip.className = 'satellite-progress';
                container.appendChild(chip);
            }
            chip.textContent = `${visited}/${total}`;
            chip.classList.toggle('satellite-progress--active', visited > 0);
        });
    }
};

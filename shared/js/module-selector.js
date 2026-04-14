// ===== Module Selector =====
// Provides module gallery + show/hide per subject page

const ModuleSelector = {
    activeModule: {},   // { pageName: 'module-id' | null }

    init() {
        const pages = ['mathematics', 'physics', 'chemistry', 'algorithms', 'biology'];
        pages.forEach(page => {
            const pageEl = document.getElementById(`page-${page}`);
            if (!pageEl) return;

            // Add class for subject-specific styling
            pageEl.classList.add(`page-${page}`);

            this.activeModule[page] = null;
            this.createGallery(page, pageEl);
        });
    },

    createGallery(page, pageEl) {
        const experiments = CONFIG.experiments[page];
        if (!experiments || experiments.length === 0) return;

        const hero = pageEl.querySelector('.page-hero');
        if (!hero) return;

        // Create gallery container
        const gallery = document.createElement('div');
        gallery.className = 'module-gallery';
        gallery.id = `gallery-${page}`;

        const accentMap = {
            mathematics: 'var(--accent-blue)',
            physics: 'var(--accent-purple)',
            chemistry: 'var(--accent-green)',
            algorithms: 'var(--accent-orange)',
            biology: 'var(--accent-teal)'
        };

        experiments.forEach((exp, idx) => {
            if (exp.variant === 'upcoming') return;

            const card = document.createElement('div');
            card.className = 'module-card';
            card.dataset.moduleTarget = exp.id;
            card.setAttribute('role', 'button');
            card.setAttribute('tabindex', '0');
            card.setAttribute('aria-label', exp.title);

            card.innerHTML = `
                <div class="module-card__icon"><i data-lucide="${exp.icon || 'box'}"></i></div>
                <div class="module-card__title">${exp.title}</div>
                <div class="module-card__desc">${exp.description}</div>
                <div class="module-card__badge">${String(idx + 1).padStart(2, '0')}</div>
            `;

            card.addEventListener('click', () => this.openModule(page, exp.id));
            card.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    this.openModule(page, exp.id);
                }
            });
            gallery.appendChild(card);
        });

        // Insert gallery after hero
        hero.insertAdjacentElement('afterend', gallery);

        // Mark page as gallery-active
        pageEl.classList.add('module-gallery-active');

        // Re-initialize Lucide icons for the new cards
        if (typeof lucide !== 'undefined') {
            lucide.createIcons();
        }
    },

    openModule(page, moduleId) {
        const pageEl = document.getElementById(`page-${page}`);
        if (!pageEl) return;

        // Hide gallery
        const gallery = document.getElementById(`gallery-${page}`);
        if (gallery) gallery.style.display = 'none';

        // Show matching content sections
        const sections = pageEl.querySelectorAll(`[data-module="${moduleId}"]`);
        sections.forEach(s => s.classList.add('module-active'));

        // Show back button
        this.showBackButton(page, pageEl, gallery);

        // Hide bento-grid
        pageEl.classList.remove('module-gallery-active');

        this.activeModule[page] = moduleId;

        // Scroll to top of page
        window.scrollTo({ top: 0, behavior: 'smooth' });

        // Trigger resize for canvas elements that may need to recalculate
        setTimeout(() => window.dispatchEvent(new Event('resize')), 100);
    },

    showBackButton(page, pageEl, gallery) {
        // Remove existing back button
        const existing = pageEl.querySelector('.module-back-btn');
        if (existing) existing.remove();

        const btn = document.createElement('button');
        btn.className = 'module-back-btn';
        btn.setAttribute('aria-label', '返回模块列表');
        btn.innerHTML = '<i data-lucide="arrow-left"></i> 返回模块列表';
        btn.addEventListener('click', () => this.closeModule(page));

        const hero = pageEl.querySelector('.page-hero');
        if (hero) hero.insertAdjacentElement('afterend', btn);

        if (typeof lucide !== 'undefined') lucide.createIcons();
    },

    closeModule(page) {
        const pageEl = document.getElementById(`page-${page}`);
        if (!pageEl) return;

        // Hide all module sections
        pageEl.querySelectorAll('[data-module].module-active').forEach(s => {
            s.classList.remove('module-active');
        });

        // Remove back button
        const btn = pageEl.querySelector('.module-back-btn');
        if (btn) btn.remove();

        // Show gallery
        const gallery = document.getElementById(`gallery-${page}`);
        if (gallery) gallery.style.display = '';

        // Restore bento-grid visibility
        pageEl.classList.add('module-gallery-active');

        this.activeModule[page] = null;

        window.scrollTo({ top: 0, behavior: 'smooth' });
    }
};

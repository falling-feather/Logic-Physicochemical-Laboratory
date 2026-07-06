const BackendContent = {
    _schemaCache: {},

    isEnabled() {
        try {
            const params = new URLSearchParams(window.location.search || '');
            if (params.get('backendSchema') === '1') return true;
            if (params.get('backendSchema') === '0') return false;
            return window.localStorage && window.localStorage.getItem('astra-backend-schema') === '1';
        } catch (e) {
            return false;
        }
    },

    getApiBaseUrl() {
        try {
            const params = new URLSearchParams(window.location.search || '');
            const queryBase = params.get('apiBase');
            const configured = typeof CONFIG !== 'undefined' && CONFIG.backend && CONFIG.backend.apiBaseUrl;
            const stored = window.localStorage && window.localStorage.getItem('astra-api-base');
            return (queryBase || stored || configured || '').replace(/\/$/, '');
        } catch (e) {
            return '';
        }
    },

    fetchPageSchema(slug) {
        if (!this.isEnabled() || !slug) return Promise.resolve(null);
        if (this._schemaCache[slug]) return this._schemaCache[slug];

        const encodedSlug = slug.split('/').map(encodeURIComponent).join('/');
        const url = `${this.getApiBaseUrl()}/api/render/page/${encodedSlug}`;
        this._schemaCache[slug] = fetch(url, {
            method: 'GET',
            credentials: 'include',
            cache: 'no-store',
            headers: { 'Accept': 'application/json' }
        })
            .then((response) => {
                if (!response.ok) return null;
                return response.json();
            })
            .catch(() => null);
        return this._schemaCache[slug];
    },

    applyExperimentSchema(page, moduleId) {
        if (!this.isEnabled() || !page || !moduleId) return;
        const slug = `${page}/${moduleId}`;
        this.fetchPageSchema(slug).then((schema) => {
            if (!schema || schema.layout !== 'experiment-page') return;
            const target = document.querySelector(`#page-${page} [data-module="${moduleId}"]`);
            if (!target) return;
            this._renderLearningTask(target, schema);
        });
    },

    _renderLearningTask(target, schema) {
        const task = Array.isArray(schema.sections)
            ? schema.sections.find((section) => section.type === 'learning-task')
            : null;
        if (!task) return;

        let card = target.querySelector('[data-backend-schema-card]');
        if (!card) {
            card = document.createElement('aside');
            card.className = 'backend-learning-card';
            card.setAttribute('data-backend-schema-card', 'true');
            const insertBefore = Array.from(target.children).find((child) =>
                child.matches && child.matches('.experiment-container, .physics-canvas-wrap, .lab-shell')
            );
            target.insertBefore(card, insertBefore || target.firstElementChild);
        }

        const concepts = task.props && Array.isArray(task.props.concepts)
            ? task.props.concepts.slice(0, 4)
            : [];
        card.innerHTML = `
            <div class="backend-learning-card__body">
                <div class="backend-learning-card__eyebrow">${this._escape(schema.title || '学习任务')}</div>
                <h3 class="backend-learning-card__title">${this._escape(task.title || '观察任务')}</h3>
                <p class="backend-learning-card__summary">${this._escape(task.summary || schema.summary || '')}</p>
                ${concepts.length ? `<div class="backend-learning-card__concepts">${concepts.map((item) => `<span>${this._escape(item)}</span>`).join('')}</div>` : ''}
            </div>
        `;
    },

    _escape(value) {
        const div = document.createElement('div');
        div.textContent = String(value || '');
        return div.innerHTML;
    }
};

window.BackendContent = BackendContent;

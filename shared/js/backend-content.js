const BackendContent = {
    _schemaCache: {},
    _sandboxControllers: new WeakMap(),
    _sandboxReadyTimeoutMs: 10000,

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
            this._renderScriptSandbox(target, schema, moduleId);
        });
    },

    destroyExperimentSchema(page, moduleId) {
        const target = document.querySelector(`#page-${page} [data-module="${moduleId}"]`);
        if (target) this._destroyScriptSandbox(target);
    },

    destroyPage(page) {
        const root = document.getElementById(`page-${page}`);
        if (!root) return;
        root.querySelectorAll('[data-module]').forEach((target) => this._destroyScriptSandbox(target));
    },

    destroyAll() {
        document.querySelectorAll('[data-module]').forEach((target) => this._destroyScriptSandbox(target));
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

    _renderScriptSandbox(target, schema, moduleId) {
        const entry = this._findScriptManifest(schema, moduleId);
        if (!entry || !entry.manifest) {
            this._destroyScriptSandbox(target);
            return;
        }

        const embed = entry.manifest.embed;
        if (!embed || embed.status !== 'embeddable' || !embed.iframe) {
            this._renderBlockedSandbox(target, entry);
            return;
        }

        this._mountScriptSandbox(target, schema, entry, embed);
    },

    _mountScriptSandbox(target, schema, entry, embed, options = {}) {
        const iframeConfig = embed.iframe || {};
        const src = this._absoluteApiUrl(iframeConfig.src);
        if (!src) {
            this._renderBlockedSandbox(target, entry);
            return;
        }
        const sandboxId = String(embed.sandboxId || entry.manifest.sandboxId || '');
        const existing = this._sandboxControllers.get(target);
        if (!options.force && existing && !existing.destroyed && existing.src === src && existing.sandboxId === sandboxId) {
            return;
        }

        this._destroyScriptSandbox(target);

        const shell = document.createElement('aside');
        shell.className = 'backend-sandbox-card';
        shell.setAttribute('data-backend-sandbox-card', 'true');
        shell.dataset.state = 'loading';
        shell.dataset.sandboxId = String(embed.sandboxId || '');

        shell.innerHTML = `
            <div class="backend-sandbox-card__header">
                <div>
                    <div class="backend-sandbox-card__eyebrow">${this._escape(schema.title || '脚本沙箱')}</div>
                    <h3 class="backend-sandbox-card__title">${this._escape(entry.sectionTitle || '交互实验')}</h3>
                </div>
                <div class="backend-sandbox-card__actions">
                    <span class="backend-sandbox-card__status" data-backend-sandbox-status>加载中</span>
                    <button class="backend-sandbox-card__refresh" type="button" aria-label="刷新沙箱" data-backend-sandbox-refresh title="刷新沙箱">
                        <i data-lucide="refresh-cw" aria-hidden="true"></i>
                    </button>
                </div>
            </div>
            <div class="backend-sandbox-card__frame-wrap">
                <iframe class="backend-sandbox-card__frame" data-backend-sandbox-frame></iframe>
            </div>
            <p class="backend-sandbox-card__message" data-backend-sandbox-message>等待隔离内容响应。</p>
        `;

        const insertBefore = Array.from(target.children).find((child) =>
            child.matches && child.matches('.demo-section, .experiment-container, .physics-canvas-wrap, .lab-shell')
        );
        target.insertBefore(shell, insertBefore || target.firstElementChild);

        const iframe = shell.querySelector('[data-backend-sandbox-frame]');
        const refresh = shell.querySelector('[data-backend-sandbox-refresh]');
        const protocol = embed.messageProtocol || {};
        const expectedSource = String(protocol.source || 'astra-content-script-sandbox');
        const expectedProtocolVersion = String(protocol.bootstrapProtocolVersion || '');
        const controller = {
            target,
            shell,
            iframe,
            src,
            sandboxId,
            expectedSource,
            expectedProtocolVersion,
            state: 'loading',
            destroyed: false,
            lastMessageType: '',
            timeoutId: null,
            onMessage: null,
            onLoad: null,
            onError: null,
        };

        controller.onMessage = (event) => this._handleSandboxMessage(controller, event);
        controller.onLoad = () => {
            if (controller.state === 'loading') {
                this._setSandboxState(controller, 'bootstrapping', '隔离文档已加载，等待脚本启动。');
            }
        };
        controller.onError = () => {
            this._setSandboxState(controller, 'error', '隔离内容加载失败。');
            this._clearSandboxTimer(controller);
        };

        window.addEventListener('message', controller.onMessage);
        iframe.addEventListener('load', controller.onLoad);
        iframe.addEventListener('error', controller.onError);
        if (refresh) {
            refresh.addEventListener('click', () => this._mountScriptSandbox(target, schema, entry, embed, { force: true }));
        }

        const sandboxTokens = String(iframeConfig.sandbox || '').trim();
        if (sandboxTokens) iframe.setAttribute('sandbox', sandboxTokens);
        iframe.referrerPolicy = String(iframeConfig.referrerPolicy || 'no-referrer');
        iframe.loading = String(iframeConfig.loading || 'lazy');
        iframe.title = String(iframeConfig.title || 'Astra Script Sandbox');
        iframe.src = src;

        controller.timeoutId = window.setTimeout(() => {
            const detail = controller.lastMessageType === 'assets-ready'
                ? '脚本资产已加载，但内容尚未发出 ready。'
                : '隔离内容响应超时。';
            this._setSandboxState(controller, 'timeout', detail);
        }, this._sandboxReadyTimeoutMs);

        this._sandboxControllers.set(target, controller);
        this._refreshIcons(shell);
    },

    _handleSandboxMessage(controller, event) {
        if (controller.destroyed || event.source !== controller.iframe.contentWindow) return;
        const data = event.data || {};
        if (!data || data.source !== controller.expectedSource) return;
        const metadata = data.metadata || {};
        if (metadata.sandboxId !== controller.sandboxId) return;
        if (controller.expectedProtocolVersion && metadata.protocolVersion !== controller.expectedProtocolVersion) {
            return;
        }

        const type = String(data.type || '');
        controller.lastMessageType = type;
        if (type === 'bootstrap-ready') {
            this._setSandboxState(controller, 'bootstrapping', '脚本启动中。');
            return;
        }
        if (type === 'assets-ready') {
            const assetCount = data.payload && Number.isFinite(data.payload.assetCount)
                ? data.payload.assetCount
                : null;
            const suffix = assetCount === null ? '' : `（${assetCount} 个资产）`;
            this._setSandboxState(controller, 'assets', `脚本资产已加载${suffix}。`);
            return;
        }
        if (type === 'ready') {
            this._setSandboxState(controller, 'ready', '隔离内容已就绪。');
            this._clearSandboxTimer(controller);
            return;
        }
        if (type === 'error' || type === 'unhandledrejection') {
            const message = data.payload && data.payload.message ? String(data.payload.message) : '隔离脚本报告异常。';
            this._setSandboxState(controller, 'error', message);
            this._clearSandboxTimer(controller);
        }
    },

    _renderBlockedSandbox(target, entry) {
        this._destroyScriptSandbox(target);

        const shell = document.createElement('aside');
        shell.className = 'backend-sandbox-card backend-sandbox-card--blocked';
        shell.setAttribute('data-backend-sandbox-card', 'true');
        shell.dataset.state = 'blocked';
        shell.innerHTML = `
            <div class="backend-sandbox-card__header">
                <div>
                    <div class="backend-sandbox-card__eyebrow">脚本沙箱</div>
                    <h3 class="backend-sandbox-card__title">${this._escape(entry.sectionTitle || '交互实验')}</h3>
                </div>
                <span class="backend-sandbox-card__status" data-backend-sandbox-status>已阻止</span>
            </div>
            <p class="backend-sandbox-card__message" data-backend-sandbox-message>当前脚本未进入可执行隔离路径。</p>
        `;

        const insertBefore = Array.from(target.children).find((child) =>
            child.matches && child.matches('.demo-section, .experiment-container, .physics-canvas-wrap, .lab-shell')
        );
        target.insertBefore(shell, insertBefore || target.firstElementChild);
    },

    _destroyScriptSandbox(target) {
        const controller = this._sandboxControllers.get(target);
        if (controller) {
            controller.destroyed = true;
            this._clearSandboxTimer(controller);
            if (controller.onMessage) window.removeEventListener('message', controller.onMessage);
            if (controller.iframe && controller.onLoad) controller.iframe.removeEventListener('load', controller.onLoad);
            if (controller.iframe && controller.onError) controller.iframe.removeEventListener('error', controller.onError);
            if (controller.iframe) controller.iframe.removeAttribute('src');
            if (controller.shell) controller.shell.remove();
            this._sandboxControllers.delete(target);
            return;
        }

        const stray = target.querySelector('[data-backend-sandbox-card]');
        if (stray) stray.remove();
    },

    _clearSandboxTimer(controller) {
        if (controller.timeoutId) {
            window.clearTimeout(controller.timeoutId);
            controller.timeoutId = null;
        }
    },

    _setSandboxState(controller, state, message) {
        if (controller.destroyed) return;
        controller.state = state;
        controller.shell.dataset.state = state;
        const status = controller.shell.querySelector('[data-backend-sandbox-status]');
        const text = controller.shell.querySelector('[data-backend-sandbox-message]');
        const labels = {
            loading: '加载中',
            bootstrapping: '启动中',
            assets: '已加载',
            ready: '已就绪',
            error: '加载失败',
            timeout: '需刷新',
            blocked: '已阻止',
        };
        if (status) status.textContent = labels[state] || state;
        if (text) text.textContent = message || '';
    },

    _findScriptManifest(schema, moduleId) {
        const sections = Array.isArray(schema.sections) ? schema.sections : [];
        const matched = sections.find((section) => {
            if (!section || section.type !== 'experiment') return false;
            const props = section.props || {};
            return section.experimentId === moduleId || props.moduleSelectorId === moduleId;
        });
        const matchedManifest = matched && matched.props && matched.props.scriptManifest;
        if (matchedManifest) {
            return {
                manifest: matchedManifest,
                sectionTitle: matched.title || schema.title || '',
            };
        }

        const manifests = [];
        this._collectScriptManifests(schema, manifests);
        return manifests[0] || null;
    },

    _collectScriptManifests(value, manifests, sectionTitle) {
        if (Array.isArray(value)) {
            value.forEach((item) => this._collectScriptManifests(item, manifests, sectionTitle));
            return;
        }
        if (!value || typeof value !== 'object') return;
        const nextTitle = typeof value.title === 'string' ? value.title : sectionTitle;
        if (value.scriptManifest && typeof value.scriptManifest === 'object') {
            manifests.push({ manifest: value.scriptManifest, sectionTitle: nextTitle || '' });
        }
        Object.keys(value).forEach((key) => this._collectScriptManifests(value[key], manifests, nextTitle));
    },

    _absoluteApiUrl(src) {
        if (!src || typeof src !== 'string') return '';
        if (/^https?:\/\//i.test(src)) return src;
        if (!src.startsWith('/')) return src;
        const base = this.getApiBaseUrl();
        return base ? `${base}${src}` : src;
    },

    _refreshIcons(root) {
        if (typeof lucide !== 'undefined' && lucide && typeof lucide.createIcons === 'function') {
            try { lucide.createIcons({ attrs: { 'stroke-width': 1.8 }, root }); } catch (e) {}
        }
    },

    _escape(value) {
        const div = document.createElement('div');
        div.textContent = String(value || '');
        return div.innerHTML;
    }
};

window.BackendContent = BackendContent;

(function () {
    'use strict';

    const ADMIN_ASSET_VERSION = '20260711v740RoleShellP0';
    const API_BASE_STORAGE_KEY = 'astra-admin-api-base';

    const state = {
        root: null,
        apiBase: '',
        user: null,
        busy: false,
        initialized: false,
        active: false,
        online: navigator.onLine !== false,
        runtimeBound: false,
        lifecycleController: null,
        requestGeneration: 0,
        panelGenerations: Object.create(null),
        writeLock: null,
        pendingJoinReview: null,
        pendingUserUpdate: null,
        onOnline: null,
        onOffline: null,
        onAuthRequired: null,
        panels: {},
        panelData: {},
        summaryData: {}
    };

    const SUMMARY_CONFIGS = [
        {
            id: 'script-health',
            title: '脚本漂移',
            icon: 'shield-check',
            path: '/api/admin/content/script-assets/remote-drift-scan-runs/health',
            fields: [
                ['health_status', '健康'],
                ['total', '运行'],
                ['problem_count', '问题'],
                ['needs_attention_count', '关注']
            ]
        },
        {
            id: 'script-queue',
            title: '脚本队列',
            icon: 'list-checks',
            path: '/api/admin/content/script-assets/remote-drift-scan-runs/queue',
            fields: [
                ['queue_status', '状态'],
                ['backlog_count', '积压'],
                ['ready_count', '就绪'],
                ['blocked_count', '阻塞']
            ]
        },
        {
            id: 'snapshot-health',
            title: '快照运行',
            icon: 'activity',
            path: '/api/admin/knowledge-snapshot-runs/health',
            fields: [
                ['health_status', '健康'],
                ['total', '运行'],
                ['problem_count', '问题'],
                ['pending_count', '待处理']
            ]
        },
        {
            id: 'snapshot-queue',
            title: '快照队列',
            icon: 'clock',
            path: '/api/admin/knowledge-snapshot-runs/queue',
            fields: [
                ['queue_status', '状态'],
                ['backlog_count', '积压'],
                ['ready_count', '就绪'],
                ['blocked_count', '阻塞']
            ]
        },
        {
            id: 'outbox-queue',
            title: 'Outbox',
            icon: 'inbox',
            path: '/api/admin/alert-outbox/queue',
            fields: [
                ['queue_status', '状态'],
                ['pending_review_count', '待审'],
                ['ready_count', '就绪'],
                ['stale_count', '过期']
            ]
        }
    ];

    const PANEL_CONFIGS = [
        {
            id: 'users',
            title: '用户与权限',
            icon: 'users-round',
            path: '/api/admin/users',
            filters: [
                selectFilter('role', '角色', [
                    ['', '全部'], ['student', '学生'], ['teacher', '教师'], ['admin', '管理员']
                ]),
                selectFilter('status', '状态', [
                    ['', '全部'], ['active', '启用'], ['disabled', '停用']
                ]),
                textFilter('q', '账号或名称')
            ],
            columns: [
                col('id', 'ID'), col('username', '账号'), col('display_name', '显示名称'),
                badgeCol('role', '角色'), badgeCol('status', '状态'), dateCol('updated_at', '更新')
            ],
            details: ['created_at', 'updated_at'],
            actions: 'user-governance'
        },
        {
            id: 'schools',
            title: '学校与组织',
            icon: 'landmark',
            path: '/api/admin/schools',
            filters: [textFilter('q', '学校或区域')],
            columns: [
                col('id', 'ID'), col('name', '学校'), col('region', '区域'), badgeCol('status', '状态')
            ],
            details: ['id', 'name', 'region', 'status']
        },
        {
            id: 'classes',
            title: '全局班级',
            icon: 'school',
            path: '/api/admin/classes',
            filters: [textFilter('q', '班级、年级或学期'), textFilter('school_id', '学校 ID')],
            columns: [
                col('id', 'ID'), col('school_id', '学校 ID'), col('name', '班级'),
                col('grade', '年级'), col('term', '学期'), badgeCol('status', '状态')
            ],
            details: ['id', 'school_id', 'name', 'grade', 'term', 'status']
        },
        {
            id: 'join-requests',
            title: '班级加入请求',
            icon: 'user-plus',
            path: '/api/admin/class-join-requests',
            filters: [
                selectFilter('status', '状态', [
                    ['', '全部'],
                    ['pending', 'pending'],
                    ['approved', 'approved'],
                    ['rejected', 'rejected']
                ], 'pending'),
                selectFilter('role', '角色', [
                    ['', '全部'],
                    ['student', 'student'],
                    ['teacher', 'teacher']
                ]),
                textFilter('q', '搜索')
            ],
            columns: [
                col('id', 'ID'),
                col('user_display_name', '用户'),
                col('class_name', '班级'),
                col('school_name', '学校'),
                badgeCol('role', '角色'),
                badgeCol('status', '状态'),
                dateCol('created_at', '申请时间')
            ],
            details: ['message', 'review_note', 'reviewed_by_user_id', 'reviewed_at'],
            actions: 'join-request-review'
        },
        {
            id: 'content-drafts',
            title: '内容草稿',
            icon: 'file-pen-line',
            path: '/api/admin/content/drafts',
            filters: [
                selectFilter('status', '状态', [
                    ['', '全部'],
                    ['draft', 'draft'],
                    ['submitted', 'submitted'],
                    ['changes_requested', 'changes_requested'],
                    ['published', 'published'],
                    ['withdrawn', 'withdrawn']
                ]),
                selectFilter('script_review_status', '脚本审查', [
                    ['', '全部'],
                    ['pending', 'pending'],
                    ['approved', 'approved'],
                    ['rejected', 'rejected'],
                    ['not_required', 'not_required']
                ]),
                textFilter('q', '搜索')
            ],
            columns: [
                col('id', 'ID'),
                col('target_slug', 'Slug'),
                col('title', '标题'),
                col('author_username', '作者'),
                badgeCol('status', '状态'),
                badgeCol('script_review_status', '脚本审查'),
                badgeCol('script_risk_level', '风险'),
                dateCol('updated_at', '更新')
            ],
            details: ['schema_hash', 'base_version_id', 'allow_script', 'script_analysis', 'change_request_note']
        },
        {
            id: 'script-assets',
            title: '脚本资产',
            icon: 'file-code-2',
            path: '/api/admin/content/script-assets',
            filters: [
                textFilter('source_host', 'Host'),
                textFilter('q', '搜索')
            ],
            columns: [
                col('id', 'ID'),
                col('slug', 'Slug'),
                col('sandbox_id', '沙箱'),
                col('source_host', 'Host'),
                bytesCol('asset_size_bytes', '体积'),
                col('policy_version', '策略'),
                dateCol('published_at', '发布')
            ],
            details: ['reference_key', 'reference_value_sha256', 'source_url_sha256', 'asset_sha256', 'policy_context_hash']
        },
        {
            id: 'script-hosts',
            title: '脚本 Host 策略',
            icon: 'server-cog',
            path: '/api/admin/content/script-host-policies',
            filters: [
                selectFilter('status', '状态', [
                    ['', '全部'],
                    ['trusted', 'trusted'],
                    ['watch', 'watch'],
                    ['blocked', 'blocked']
                ]),
                textFilter('q', '搜索')
            ],
            columns: [
                col('source_host', 'Host'),
                badgeCol('status', '状态'),
                boolCol('configured_allowed', '配置允许'),
                col('observed_asset_count', '资产'),
                col('observed_page_count', '页面'),
                dateCol('last_observed_at', '最近发现')
            ],
            details: ['reason', 'reviewed_by_user_id', 'reviewed_at', 'created_at', 'updated_at']
        },
        {
            id: 'snapshot-runs',
            title: '知识快照运行',
            icon: 'database',
            path: '/api/admin/knowledge-snapshot-runs',
            filters: [
                selectFilter('status', '状态', [
                    ['', '全部'],
                    ['pending', 'pending'],
                    ['running', 'running'],
                    ['success', 'success'],
                    ['failed', 'failed'],
                    ['cancelled', 'cancelled']
                ]),
                selectFilter('granularity', '粒度', [
                    ['', '全部'],
                    ['daily', 'daily'],
                    ['weekly', 'weekly'],
                    ['monthly', 'monthly']
                ])
            ],
            columns: [
                col('id', 'ID'),
                col('run_key', 'Run Key'),
                badgeCol('granularity', '粒度'),
                badgeCol('status', '状态'),
                col('trigger_source', '触发'),
                col('user_snapshot_count', '用户快照'),
                col('class_snapshot_count', '班级快照'),
                dateCol('started_at', '开始')
            ],
            details: ['error_message', 'metadata_summary', 'scheduler_lease_owner', 'scheduler_lease_expires_at']
        },
        {
            id: 'outbox',
            title: '告警 Outbox',
            icon: 'send',
            path: '/api/admin/alert-outbox',
            filters: [
                selectFilter('status', '状态', [
                    ['', '全部'],
                    ['pending_review', 'pending_review'],
                    ['planned', 'planned'],
                    ['queued', 'queued'],
                    ['suppressed', 'suppressed'],
                    ['cancelled', 'cancelled']
                ]),
                textFilter('source_type', '来源'),
                textFilter('event_code', '事件')
            ],
            columns: [
                col('id', 'ID'),
                col('source_type', '来源'),
                col('event_code', '事件'),
                badgeCol('severity', '等级'),
                badgeCol('action_hint', '动作'),
                badgeCol('status', '状态'),
                col('seen_count', '次数'),
                dateCol('last_seen_at', '最近')
            ],
            details: ['source_key', 'delivery_target', 'external_delivery', 'payload_hash_prefix', 'review_note_present']
        },
        {
            id: 'audit-logs',
            title: '审计日志',
            icon: 'scroll-text',
            path: '/api/admin/audit-logs',
            filters: [
                selectFilter('event_result', '结果', [
                    ['', '全部'],
                    ['success', 'success'],
                    ['failure', 'failure']
                ]),
                textFilter('action', 'Action'),
                textFilter('resource_type', '资源')
            ],
            columns: [
                col('id', 'ID'),
                col('actor_user_id', 'Actor'),
                badgeCol('actor_role', '角色'),
                col('action', 'Action'),
                col('resource_type', '资源'),
                badgeCol('event_result', '结果'),
                col('request_id', 'Request'),
                dateCol('created_at', '时间')
            ],
            details: ['resource_id', 'failure_reason', 'request_method', 'request_path', 'snapshot_json']
        },
        {
            id: 'bugs',
            title: 'Bug 台账',
            icon: 'bug',
            path: '/api/admin/bugs',
            filters: [
                selectFilter('status', '状态', [
                    ['', '全部'],
                    ['open', 'open'],
                    ['triaged', 'triaged'],
                    ['in_progress', 'in_progress'],
                    ['closed', 'closed']
                ], 'open'),
                textFilter('q', '搜索')
            ],
            columns: [
                col('id', 'ID'),
                col('title', '标题'),
                col('category', '分类'),
                badgeCol('severity', '等级'),
                badgeCol('status', '状态'),
                col('source', '来源'),
                dateCol('updated_at', '更新')
            ],
            details: ['external_issue_provider', 'external_issue_id', 'external_issue_url', 'evidence', 'notes']
        }
    ];

    function col(key, label) {
        return { key, label };
    }

    function badgeCol(key, label) {
        return { key, label, badge: true };
    }

    function dateCol(key, label) {
        return { key, label, type: 'date' };
    }

    function bytesCol(key, label) {
        return { key, label, type: 'bytes' };
    }

    function boolCol(key, label) {
        return { key, label, type: 'boolean', badge: true };
    }

    function selectFilter(name, label, options, value) {
        return { type: 'select', name, label, options, value: value || '' };
    }

    function textFilter(name, label) {
        return { type: 'text', name, label };
    }

    function initAdmin() {
        state.root = document.querySelector('[data-admin-governance]');
        if (!state.root) return;
        state.active = true;
        state.online = navigator.onLine !== false;
        if (window.AstraApiClient) AstraApiClient.scrubLegacyTokens();
        state.apiBase = resolveApiBase();
        initializePanelState();
        renderShell();
        if (!state.initialized) {
            bindEvents();
            state.initialized = true;
        }
        bindRuntimeEvents();
        if (!state.online) {
            renderAuthError(AstraApiClient.offlineError());
            refreshIcons();
            return;
        }
        refreshAll();
    }

    function destroyAdmin() {
        state.active = false;
        invalidateRequests();
        unbindRuntimeEvents();
        state.user = null;
        state.busy = false;
        state.panelData = {};
        state.summaryData = {};
        const dashboard = getDashboard();
        if (dashboard) dashboard.hidden = true;
        if (state.root) {
            const authContainer = state.root.querySelector('[data-admin-auth-state]');
            if (authContainer && window.AstraAuthUI) AstraAuthUI.unmount(authContainer);
            state.root.innerHTML = `
                <div class="admin-loading">
                    <i data-lucide="loader-circle"></i>
                    <span>管理端已离开</span>
                </div>
            `;
        }
    }

    function bindRuntimeEvents() {
        if (state.runtimeBound) return;
        state.onOnline = () => {
            state.online = true;
            if (state.active) refreshAll();
        };
        state.onOffline = () => {
            state.online = false;
            invalidateRequests();
            setBusy(false);
            state.user = null;
            state.panelData = {};
            state.summaryData = {};
            clearDashboardDom();
            const dashboard = getDashboard();
            if (dashboard) dashboard.hidden = true;
            if (state.active) {
                renderAuthError(AstraApiClient.offlineError());
                refreshIcons();
            }
        };
        state.onAuthRequired = () => {
            invalidateRequests();
            setBusy(false);
            state.user = null;
            state.panelData = {};
            state.summaryData = {};
            clearDashboardDom();
            const dashboard = getDashboard();
            if (dashboard) dashboard.hidden = true;
            if (state.active) {
                renderAuthError(new AstraApiClient.Error('登录状态已失效', { status: 401, code: 'unauthorized' }));
                refreshIcons();
            }
        };
        window.addEventListener('online', state.onOnline);
        window.addEventListener('offline', state.onOffline);
        window.addEventListener('astra:api-auth-required', state.onAuthRequired);
        state.runtimeBound = true;
    }

    function unbindRuntimeEvents() {
        if (!state.runtimeBound) return;
        window.removeEventListener('online', state.onOnline);
        window.removeEventListener('offline', state.onOffline);
        window.removeEventListener('astra:api-auth-required', state.onAuthRequired);
        state.onOnline = null;
        state.onOffline = null;
        state.onAuthRequired = null;
        state.runtimeBound = false;
    }

    function initializePanelState() {
        PANEL_CONFIGS.forEach((config) => {
            if (!state.panels[config.id]) {
                state.panels[config.id] = { limit: 10, offset: 0, filters: {} };
            }
            config.filters.forEach((filter) => {
                if (filter.value && state.panels[config.id].filters[filter.name] === undefined) {
                    state.panels[config.id].filters[filter.name] = filter.value;
                }
            });
        });
    }

    function renderShell() {
        state.root.innerHTML = `
            <header class="admin-governance__header">
                <div class="admin-governance__title">
                    <span class="admin-governance__eyebrow">
                        <i data-lucide="shield-check"></i>
                        管理端治理
                    </span>
                    <h1>治理总览</h1>
                </div>
                <div class="admin-governance__actions">
                    <label class="admin-api-base">
                        <span>API</span>
                        <input type="url" data-admin-api-base value="${escapeAttr(state.apiBase)}" placeholder="同源" autocomplete="off">
                    </label>
                    <button type="button" class="admin-icon-button" data-admin-action="refresh" aria-label="刷新治理总览">
                        <i data-lucide="refresh-cw"></i>
                        <span>刷新</span>
                    </button>
                </div>
            </header>
            <div class="admin-auth-state" data-admin-auth-state></div>
            <div class="admin-notice" data-admin-notice hidden role="status" aria-live="polite"></div>
            <div class="admin-dashboard" data-admin-dashboard hidden>
                <section class="admin-kpi-grid" data-admin-stats></section>
                <section class="admin-database-map" data-admin-database-map></section>
                <section class="admin-summary-grid" data-admin-summary></section>
                <section class="admin-panel-grid" data-admin-panels>
                    ${PANEL_CONFIGS.map(renderPanelShell).join('')}
                </section>
            </div>
        `;
        refreshIcons();
    }

    function renderPanelShell(config) {
        return `
            <article class="admin-panel" data-admin-panel="${config.id}">
                <header class="admin-panel__header">
                    <div>
                        <h2><i data-lucide="${config.icon}"></i>${escapeHtml(config.title)}</h2>
                        <p data-admin-panel-meta="${config.id}">--</p>
                    </div>
                    <button type="button" class="admin-icon-button admin-icon-button--compact" data-admin-panel-refresh="${config.id}" aria-label="刷新${escapeAttr(config.title)}">
                        <i data-lucide="refresh-cw"></i>
                    </button>
                </header>
                <form class="admin-panel__filters" data-admin-panel-form="${config.id}">
                    ${config.filters.map((filter) => renderFilter(config.id, filter)).join('')}
                    <label>
                        <span>条数</span>
                        <select name="limit">
                            ${[5, 10, 25].map((limit) => `<option value="${limit}"${limit === state.panels[config.id].limit ? ' selected' : ''}>${limit}</option>`).join('')}
                        </select>
                    </label>
                    <button type="submit" class="admin-icon-button admin-icon-button--compact" aria-label="应用筛选">
                        <i data-lucide="filter"></i>
                    </button>
                </form>
                <div class="admin-panel__body" data-admin-panel-body="${config.id}">
                    ${renderLoading('加载中')}
                </div>
            </article>
        `;
    }

    function renderFilter(panelId, filter) {
        const current = state.panels[panelId].filters[filter.name] || filter.value || '';
        if (filter.type === 'select') {
            return `
                <label>
                    <span>${escapeHtml(filter.label)}</span>
                    <select name="${escapeAttr(filter.name)}">
                        ${filter.options.map(([value, label]) => `<option value="${escapeAttr(value)}"${value === current ? ' selected' : ''}>${escapeHtml(label)}</option>`).join('')}
                    </select>
                </label>
            `;
        }
        return `
            <label>
                <span>${escapeHtml(filter.label)}</span>
                <input type="search" name="${escapeAttr(filter.name)}" value="${escapeAttr(current)}" autocomplete="off">
            </label>
        `;
    }

    function bindEvents() {
        state.root.addEventListener('click', (event) => {
            const refreshAllButton = event.target.closest('[data-admin-action="refresh"]');
            if (refreshAllButton) {
                state.writeLock = null;
                state.pendingJoinReview = null;
                state.pendingUserUpdate = null;
                setNotice('', '');
                refreshAll();
                return;
            }

            const joinReviewButton = event.target.closest('[data-admin-join-review]');
            if (joinReviewButton) {
                reviewJoinRequest(joinReviewButton);
                return;
            }

            const refreshPanelButton = event.target.closest('[data-admin-panel-refresh]');
            if (refreshPanelButton) {
                refreshPanel(refreshPanelButton.dataset.adminPanelRefresh);
                return;
            }

            const pageButton = event.target.closest('[data-admin-page]');
            if (pageButton) {
                const panelId = pageButton.dataset.adminPanelId;
                const direction = pageButton.dataset.adminPage;
                const panelState = state.panels[panelId];
                if (!panelState) return;
                const data = state.panelData[panelId] || {};
                if (direction === 'next' && data.next_offset !== null && data.next_offset !== undefined) {
                    panelState.offset = data.next_offset;
                } else if (direction === 'prev') {
                    panelState.offset = Math.max(0, panelState.offset - panelState.limit);
                }
                refreshPanel(panelId);
            }
        });

        state.root.addEventListener('submit', (event) => {
            const form = event.target.closest('[data-admin-panel-form]');
            if (!form) return;
            event.preventDefault();
            applyPanelForm(form.dataset.adminPanelForm, form);
        });

        state.root.addEventListener('change', (event) => {
            const apiInput = event.target.closest('[data-admin-api-base]');
            if (apiInput) {
                state.apiBase = normalizeApiBase(apiInput.value);
                localStorage.setItem(API_BASE_STORAGE_KEY, state.apiBase);
                apiInput.value = state.apiBase;
                refreshAll();
                return;
            }

            const form = event.target.closest('[data-admin-panel-form]');
            if (form && event.target.tagName === 'SELECT') {
                applyPanelForm(form.dataset.adminPanelForm, form);
            }
        });
    }

    function applyPanelForm(panelId, form) {
        const panelState = state.panels[panelId];
        if (!panelState) return;
        const data = new FormData(form);
        panelState.limit = Number(data.get('limit')) || 10;
        panelState.offset = 0;
        panelState.filters = {};
        PANEL_CONFIGS.find((config) => config.id === panelId).filters.forEach((filter) => {
            const value = String(data.get(filter.name) || '').trim();
            if (value) panelState.filters[filter.name] = value;
        });
        refreshPanel(panelId);
    }

    async function refreshAll() {
        if (!state.root || !state.active) return;
        const generation = beginRequestGeneration();
        setBusy(true);
        state.user = null;
        state.panelData = {};
        state.summaryData = {};
        clearDashboardDom();
        renderAuthState('checking');
        const dashboard = getDashboard();
        if (dashboard) dashboard.hidden = true;
        if (!state.online) {
            renderAuthError(AstraApiClient.offlineError());
            setBusy(false);
            refreshIcons();
            return;
        }
        try {
            const user = await fetchJson('/api/users/me');
            if (!isCurrentRequest(generation)) return;
            state.user = user;
            if (user.role !== 'admin') {
                renderAuthState('forbidden', user);
                return;
            }
            renderAuthState('ready', user);
            if (dashboard) dashboard.hidden = false;
            await Promise.all([
                refreshStats(generation),
                refreshSummaries(generation),
                ...PANEL_CONFIGS.map((config) => refreshPanel(config.id, generation))
            ]);
        } catch (error) {
            if (AstraApiClient.isCancelled(error) || !isCurrentRequest(generation)) return;
            renderAuthError(error);
        } finally {
            if (isCurrentRequest(generation)) {
                setBusy(false);
                rerenderJoinRequestsPanel();
                rerenderPanel('users');
                refreshIcons();
            }
        }
    }

    async function refreshStats(generation) {
        const requestGeneration = generation || state.requestGeneration;
        const container = state.root.querySelector('[data-admin-stats]');
        if (!container) return;
        container.innerHTML = renderLoading('统计加载中');
        try {
            const [stats, health] = await Promise.all([
                fetchJson('/api/admin/stats'),
                fetchJson('/api/health')
            ]);
            if (!isCurrentRequest(requestGeneration)) return;
            container.innerHTML = renderStats(stats);
            const databaseMap = state.root.querySelector('[data-admin-database-map]');
            if (databaseMap) databaseMap.innerHTML = renderDatabaseMap(stats, health);
            return true;
        } catch (error) {
            if (AstraApiClient.isCancelled(error) || !isCurrentRequest(requestGeneration)) return;
            container.innerHTML = renderError(error, '统计读取失败');
            return false;
        }
    }

    async function refreshSummaries(generation) {
        const requestGeneration = generation || state.requestGeneration;
        const container = state.root.querySelector('[data-admin-summary]');
        if (!container) return;
        container.innerHTML = SUMMARY_CONFIGS.map((config) => renderSummaryCard(config, null, true)).join('');
        const settled = await Promise.allSettled(
            SUMMARY_CONFIGS.map((config) => fetchJson(config.path))
        );
        if (!isCurrentRequest(requestGeneration)) return;
        settled.forEach((result, index) => {
            state.summaryData[SUMMARY_CONFIGS[index].id] = result;
        });
        container.innerHTML = SUMMARY_CONFIGS.map((config) => {
            const result = state.summaryData[config.id];
            if (!result || result.status !== 'fulfilled') {
                return renderSummaryCard(config, result && result.reason, false);
            }
            return renderSummaryCard(config, result.value, false);
        }).join('');
    }

    async function refreshPanel(panelId, generation) {
        const requestGeneration = generation || state.requestGeneration;
        const panelGeneration = (state.panelGenerations[panelId] || 0) + 1;
        state.panelGenerations[panelId] = panelGeneration;
        const config = PANEL_CONFIGS.find((item) => item.id === panelId);
        const body = state.root && state.root.querySelector(`[data-admin-panel-body="${panelId}"]`);
        const meta = state.root && state.root.querySelector(`[data-admin-panel-meta="${panelId}"]`);
        if (!config || !body) return;
        body.innerHTML = renderLoading('加载中');
        if (meta) meta.textContent = '--';
        try {
            const panelState = state.panels[panelId];
            const params = Object.assign({}, panelState.filters, {
                limit: panelState.limit,
                offset: panelState.offset
            });
            const data = await fetchJson(config.path, params);
            if (!isCurrentRequest(requestGeneration) || state.panelGenerations[panelId] !== panelGeneration) return;
            state.panelData[panelId] = data;
            body.innerHTML = renderPanelData(config, data);
            if (meta) meta.textContent = `共 ${formatNumber(data.total || 0)} 条`;
            return true;
        } catch (error) {
            if (AstraApiClient.isCancelled(error)
                || !isCurrentRequest(requestGeneration)
                || state.panelGenerations[panelId] !== panelGeneration) return;
            body.innerHTML = renderError(error, '队列读取失败');
            if (meta) meta.textContent = '读取失败';
            return false;
        } finally {
            refreshIcons();
        }
    }

    function renderAuthState(mode, user) {
        const container = state.root.querySelector('[data-admin-auth-state]');
        if (!container) return;
        if (window.AstraAuthUI) AstraAuthUI.unmount(container);
        if (mode === 'checking') {
            container.innerHTML = `
                <div class="admin-auth-card admin-auth-card--checking">
                    <i data-lucide="loader-circle"></i>
                    <span>正在校验管理员会话</span>
                </div>
            `;
            return;
        }
        if (mode === 'forbidden') {
            if (window.AstraAuthUI) {
                AstraAuthUI.mountAccount(container, {
                    role: 'admin', baseUrl: state.apiBase, user: user || {}, roleMismatch: true,
                    onSignedOut: () => refreshAll()
                });
                return;
            }

            const userUpdateButton = event.target.closest('[data-admin-user-update]');
            if (userUpdateButton) {
                updateUserGovernance(userUpdateButton);
                return;
            }

            const teachingButton = event.target.closest('[data-admin-open-teaching]');
            if (teachingButton && window.Router) {
                Router.navigateTo('teacher', true);
                return;
            }
            container.innerHTML = `
                <div class="admin-auth-card admin-auth-card--blocked">
                    <i data-lucide="shield-x"></i>
                    <div>
                        <strong>当前账号无管理权限</strong>
                        <span>${escapeHtml(user.display_name || user.username || '当前用户')} · ${escapeHtml(user.role || 'unknown')}</span>
                    </div>
                </div>
            `;
            return;
        }
        if (window.AstraAuthUI) {
            AstraAuthUI.mountAccount(container, {
                role: 'admin', baseUrl: state.apiBase, user: user || {},
                onSignedOut: () => refreshAll()
            });
            return;
        }
        container.innerHTML = `
            <div class="admin-auth-card admin-auth-card--ready">
                <i data-lucide="shield-check"></i>
                <div>
                    <strong>${escapeHtml(user.display_name || user.username)}</strong>
                    <span>${escapeHtml(user.username)} · ${escapeHtml(user.role)} · ${escapeHtml(user.status)}</span>
                </div>
                <span class="admin-status-pill admin-status-pill--ready">治理操作已启用</span>
            </div>
        `;
    }

    function renderAuthError(error) {
        const container = state.root.querySelector('[data-admin-auth-state]');
        if (!container) return;
        const isUnauthenticated = error && error.status === 401;
        const isForbidden = error && error.status === 403;
        const isOffline = error && error.code === 'offline';
        if (isUnauthenticated && window.AstraAuthUI) {
            AstraAuthUI.mountGate(container, {
                role: 'admin', baseUrl: state.apiBase,
                onAuthenticated: () => refreshAll()
            });
            return;
        }
        if (window.AstraAuthUI) AstraAuthUI.unmount(container);
        container.innerHTML = `
            <div class="admin-auth-card admin-auth-card--blocked">
                <i data-lucide="${isUnauthenticated ? 'lock' : isForbidden ? 'shield-x' : isOffline ? 'wifi-off' : 'server-off'}"></i>
                <div>
                    <strong>${isUnauthenticated ? '需要管理员会话' : isForbidden ? '当前账号无管理权限' : isOffline ? '当前处于离线状态' : '后端连接失败'}</strong>
                    <span>${escapeHtml(errorMessage(error))}</span>
                </div>
            </div>
        `;
    }

    function renderStats(stats) {
        const items = [
            ['pending_class_join_requests', '待审加入', 'user-plus'],
            ['total_content_drafts', '内容草稿', 'file-pen-line'],
            ['pending_script_reviews', '脚本待审', 'file-code-2'],
            ['open_bug_records', '开放 Bug', 'bug'],
            ['total_audit_logs', '审计日志', 'scroll-text'],
            ['total_users', '用户', 'users'],
            ['total_content_pages', '内容页', 'files'],
            ['total_learning_events', '学习事件', 'activity']
        ];
        const roleText = stats.users_by_role
            ? Object.entries(stats.users_by_role).map(([role, total]) => `${role}:${total}`).join(' / ')
            : '';
        return items.map(([key, label, icon]) => `
            <article class="admin-kpi">
                <span class="admin-kpi__icon"><i data-lucide="${icon}"></i></span>
                <strong>${formatNumber(stats[key] || 0)}</strong>
                <span>${escapeHtml(label)}</span>
                ${key === 'total_users' && roleText ? `<em>${escapeHtml(roleText)}</em>` : ''}
            </article>
        `).join('');
    }

    function renderDatabaseMap(stats, health) {
        const databaseOk = Boolean(health && health.database && health.database.ok);
        const entities = [
            ['users', '用户', stats.total_users, 'users'],
            ['schools', '学校', stats.total_schools, 'landmark'],
            ['classes', '班级', stats.total_classes, 'school'],
            ['courses', '课程', stats.total_courses, 'book-open'],
            ['assignments', '作业', stats.total_assignments, 'clipboard-list'],
            ['submissions', '提交', stats.total_submissions, 'send'],
            ['events', '学习事件', stats.total_learning_events, 'activity'],
            ['audits', '审计记录', stats.total_audit_logs, 'scroll-text']
        ];
        const roleTotal = Math.max(1, Number(stats.total_users || 0));
        return `
            <header class="admin-database-map__header">
                <div>
                    <h2><i data-lucide="database-zap"></i>领域数据地图</h2>
                    <p>展示业务实体与规模；写入只能通过带校验、审计和权限控制的领域操作完成，不开放任意 SQL。</p>
                </div>
                <div class="admin-database-map__actions">
                    <span class="admin-status-pill admin-status-pill--${databaseOk ? 'good' : 'bad'}">数据库 ${databaseOk ? '已连接' : '异常'}</span>
                    <button type="button" class="admin-icon-button" data-admin-open-teaching>
                        <i data-lucide="workflow"></i><span>组织与班级编辑</span>
                    </button>
                </div>
            </header>
            <div class="admin-database-map__entities">
                ${entities.map(([id, label, total, icon], index) => `
                    <article data-entity="${id}">
                        <span><i data-lucide="${icon}"></i>${escapeHtml(label)}</span>
                        <strong>${formatNumber(total || 0)}</strong>
                        ${index < entities.length - 1 ? '<i class="admin-database-map__arrow" data-lucide="arrow-right"></i>' : ''}
                    </article>
                `).join('')}
            </div>
            <div class="admin-database-map__roles" aria-label="用户角色分布">
                ${['student', 'teacher', 'admin'].map((role) => {
                    const total = Number((stats.users_by_role || {})[role] || 0);
                    const width = Math.max(total ? 4 : 0, Math.round(total / roleTotal * 100));
                    return `<div><span>${escapeHtml(role)}</span><b><i style="width:${width}%"></i></b><strong>${formatNumber(total)}</strong></div>`;
                }).join('')}
            </div>
        `;
    }

    function renderSummaryCard(config, data, loading) {
        if (loading) {
            return `
                <article class="admin-summary">
                    <h2><i data-lucide="${config.icon}"></i>${escapeHtml(config.title)}</h2>
                    ${renderLoading('加载中')}
                </article>
            `;
        }
        if (data instanceof Error || (data && data.status && data.message)) {
            return `
                <article class="admin-summary admin-summary--error">
                    <h2><i data-lucide="${config.icon}"></i>${escapeHtml(config.title)}</h2>
                    <p>${escapeHtml(errorMessage(data))}</p>
                </article>
            `;
        }
        return `
            <article class="admin-summary">
                <h2><i data-lucide="${config.icon}"></i>${escapeHtml(config.title)}</h2>
                <dl>
                    ${config.fields.map(([key, label]) => `
                        <div>
                            <dt>${escapeHtml(label)}</dt>
                            <dd>${formatSummaryValue(data && data[key])}</dd>
                        </div>
                    `).join('')}
                </dl>
            </article>
        `;
    }

    function renderPanelData(config, data) {
        const items = Array.isArray(data.items) ? data.items : [];
        if (!items.length) {
            return `
                <div class="admin-empty">
                    <i data-lucide="circle-check"></i>
                    <span>暂无记录</span>
                </div>
                ${renderPager(config.id, data)}
            `;
        }
        return `
            <div class="admin-table-wrap">
                <table class="admin-table">
                    <thead>
                        <tr>${config.columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join('')}<th>详情</th></tr>
                    </thead>
                    <tbody>
                        ${items.map((item) => renderRow(config, item)).join('')}
                    </tbody>
                </table>
            </div>
            ${renderPager(config.id, data)}
        `;
    }

    function renderRow(config, item) {
        return `
            <tr>
                ${config.columns.map((column) => `<td data-label="${escapeAttr(column.label)}">${renderCell(item, column)}</td>`).join('')}
                <td data-label="详情">${renderDetails(config, item)}</td>
            </tr>
        `;
    }

    function renderCell(item, column) {
        const raw = valueAt(item, column.key);
        const text = formatValue(raw, column);
        if (column.badge) {
            return `<span class="admin-status-pill admin-status-pill--${statusClass(raw)}">${escapeHtml(text)}</span>`;
        }
        return escapeHtml(text);
    }

    function renderDetails(config, item) {
        const details = {};
        const approvePending = state.pendingJoinReview === `${item.id}:approved`;
        const rejectPending = state.pendingJoinReview === `${item.id}:rejected`;
        config.details.forEach((key) => {
            details[key] = valueAt(item, key);
        });
        return `
            ${config.actions === 'user-governance' ? renderUserGovernance(item) : ''}
            ${config.actions === 'join-request-review' && item.status === 'pending' ? `
                <div class="admin-row-actions">
                    <button type="button" class="admin-icon-button admin-icon-button--compact${approvePending ? ' admin-icon-button--confirming' : ''}" data-admin-join-review="approved" data-join-request-id="${item.id}" ${state.busy || state.writeLock || !state.online ? 'disabled' : ''} aria-label="${approvePending ? '再次点击确认批准加入请求' : '批准加入请求'}">
                        <i data-lucide="check"></i>
                    </button>
                    <button type="button" class="admin-icon-button admin-icon-button--compact${rejectPending ? ' admin-icon-button--confirming' : ''}" data-admin-join-review="rejected" data-join-request-id="${item.id}" ${state.busy || state.writeLock || !state.online ? 'disabled' : ''} aria-label="${rejectPending ? '再次点击确认拒绝加入请求' : '拒绝加入请求'}">
                        <i data-lucide="x"></i>
                    </button>
                </div>
            ` : ''}
            <details class="admin-row-detail">
                <summary>查看</summary>
                <pre>${escapeHtml(JSON.stringify(details, null, 2))}</pre>
            </details>
        `;
    }

    function renderUserGovernance(item) {
        const pending = state.pendingUserUpdate && state.pendingUserUpdate.userId === Number(item.id)
            ? state.pendingUserUpdate
            : null;
        const confirming = Boolean(pending);
        const selectedRole = pending ? pending.role : item.role;
        const selectedStatus = pending ? pending.status : item.status;
        return `
            <div class="admin-user-governance" data-admin-user-governance="${item.id}">
                <select data-admin-user-role aria-label="用户角色">
                    ${['student', 'teacher', 'admin'].map((role) => `<option value="${role}"${selectedRole === role ? ' selected' : ''}>${role}</option>`).join('')}
                </select>
                <select data-admin-user-status aria-label="用户状态">
                    ${['active', 'disabled'].map((status) => `<option value="${status}"${selectedStatus === status ? ' selected' : ''}>${status}</option>`).join('')}
                </select>
                <button type="button" class="admin-icon-button admin-icon-button--compact${confirming ? ' admin-icon-button--confirming' : ''}" data-admin-user-update data-user-id="${item.id}" ${state.busy || state.writeLock || !state.online ? 'disabled' : ''} aria-label="${confirming ? '再次点击确认用户权限变更' : '预览用户权限变更'}">
                    <i data-lucide="${confirming ? 'shield-alert' : 'save'}"></i>
                </button>
            </div>`;
    }

    function renderPager(panelId, data) {
        const panelState = state.panels[panelId];
        const total = data.total || 0;
        const from = total === 0 ? 0 : panelState.offset + 1;
        const to = Math.min(total, panelState.offset + (data.items ? data.items.length : 0));
        const hasPrev = panelState.offset > 0;
        const hasNext = data.next_offset !== null && data.next_offset !== undefined;
        return `
            <div class="admin-pager">
                <span>${formatNumber(from)}-${formatNumber(to)} / ${formatNumber(total)}</span>
                <div>
                    <button type="button" class="admin-icon-button admin-icon-button--compact" data-admin-panel-id="${panelId}" data-admin-page="prev"${hasPrev ? '' : ' disabled'} aria-label="上一页">
                        <i data-lucide="chevron-left"></i>
                    </button>
                    <button type="button" class="admin-icon-button admin-icon-button--compact" data-admin-panel-id="${panelId}" data-admin-page="next"${hasNext ? '' : ' disabled'} aria-label="下一页">
                        <i data-lucide="chevron-right"></i>
                    </button>
                </div>
            </div>
        `;
    }

    async function updateUserGovernance(button) {
        if (state.busy || state.writeLock) return;
        if (!state.online) {
            setNotice('warning', '当前离线，用户治理写入已停用。');
            return;
        }
        const userId = Number(button.dataset.userId);
        const controls = button.closest('[data-admin-user-governance]');
        const role = controls && controls.querySelector('[data-admin-user-role]')?.value;
        const status = controls && controls.querySelector('[data-admin-user-status]')?.value;
        if (!userId || !['student', 'teacher', 'admin'].includes(role) || !['active', 'disabled'].includes(status)) return;

        const currentUser = ((state.panelData.users && state.panelData.users.items) || [])
            .find((item) => Number(item.id) === userId);
        if (currentUser && currentUser.role === role && currentUser.status === status) {
            state.pendingUserUpdate = null;
            setNotice('warning', `用户 #${userId} 的角色和状态没有变化，未发送写入。`);
            rerenderPanel('users');
            refreshIcons();
            return;
        }

        const confirmationKey = `${userId}:${role}:${status}`;
        if (!state.pendingUserUpdate || state.pendingUserUpdate.key !== confirmationKey) {
            state.pendingUserUpdate = { key: confirmationKey, userId, role, status };
            setNotice('warning', `将用户 #${userId} 调整为 ${role} / ${status}。再次点击同一保存按钮才会写入；权限变化会撤销其活动会话。`);
            rerenderPanel('users');
            refreshIcons();
            return;
        }

        state.pendingUserUpdate = null;
        setBusy(true);
        try {
            await AstraApiClient.request(`/api/admin/users/${userId}`, {
                baseUrl: state.apiBase,
                method: 'PATCH',
                body: { role, status },
                signal: state.lifecycleController && state.lifecycleController.signal
            });
            const results = await Promise.all([
                refreshPanel('users'), refreshPanel('audit-logs'), refreshStats()
            ]);
            if (results.some((result) => !result)) {
                state.writeLock = { action: 'user-governance', resourceId: userId };
                setNotice('warning', '用户变更已由服务端确认，但列表核对未完整完成；写入已锁定，请刷新后核对。');
            } else {
                setNotice('success', `用户 #${userId} 已更新为 ${role} / ${status}，审计日志和统计已同步。`);
            }
        } catch (error) {
            if (error && (error.confirmed || AstraApiClient.isAmbiguousMutation(error))) {
                state.writeLock = {
                    action: 'user-governance', resourceId: userId, requestId: String(error.requestId || '')
                };
                await Promise.all([refreshPanel('users'), refreshPanel('audit-logs'), refreshStats()]);
                setNotice('warning', '用户变更结果尚未确认，系统未自动重试；写入已锁定，请刷新并依据审计日志核对。');
            } else {
                setNotice('error', errorMessage(error));
            }
        } finally {
            setBusy(false);
            rerenderPanel('users');
            refreshIcons();
        }
    }

    async function reviewJoinRequest(button) {
        if (state.busy || state.writeLock) return;
        if (!state.online) {
            setNotice('warning', '当前离线，审批写入已停用');
            return;
        }
        const joinRequestId = Number(button.dataset.joinRequestId);
        const nextStatus = button.dataset.adminJoinReview;
        if (!joinRequestId || !['approved', 'rejected'].includes(nextStatus)) return;
        const actionLabel = nextStatus === 'approved' ? '批准' : '拒绝';
        const confirmationKey = `${joinRequestId}:${nextStatus}`;
        if (state.pendingJoinReview !== confirmationKey) {
            state.pendingJoinReview = confirmationKey;
            setNotice('warning', `再次点击同一按钮以确认${actionLabel}加入请求 #${joinRequestId}；未发送任何写入`);
            rerenderJoinRequestsPanel();
            refreshIcons();
            return;
        }
        state.pendingJoinReview = null;
        setBusy(true);
        try {
            await AstraApiClient.request(`/api/admin/class-join-requests/${joinRequestId}`, {
                baseUrl: state.apiBase,
                method: 'PATCH',
                body: { status: nextStatus, note: 'reviewed from admin governance UI' },
                signal: state.lifecycleController && state.lifecycleController.signal
            });
            const [panelReconciled, statsReconciled] = await Promise.all([
                refreshPanel('join-requests'),
                refreshStats()
            ]);
            if (!panelReconciled || !statsReconciled) {
                state.writeLock = { action: 'join-request-review', resourceId: joinRequestId };
                setNotice('warning', '审批已由服务器确认，但列表或统计刷新失败；系统不会重复发送，请点击顶部刷新完成核对');
            } else {
                setNotice('success', nextStatus === 'approved' ? '加入请求已批准并完成权威列表核对' : '加入请求已拒绝并完成权威列表核对');
            }
        } catch (error) {
            if (error && (error.confirmed || AstraApiClient.isAmbiguousMutation(error))) {
                state.writeLock = {
                    action: 'join-request-review',
                    resourceId: joinRequestId,
                    requestId: String(error.requestId || '')
                };
                await Promise.all([refreshPanel('join-requests'), refreshStats()]);
                setNotice('warning', '审批结果尚未确认，系统未自动重试；写入已锁定，请点击顶部刷新并核对请求状态');
            } else {
                setNotice('error', errorMessage(error));
            }
        } finally {
            setBusy(false);
            rerenderJoinRequestsPanel();
            refreshIcons();
        }
    }

    function rerenderJoinRequestsPanel() {
        const data = state.panelData['join-requests'];
        const config = PANEL_CONFIGS.find((item) => item.id === 'join-requests');
        const body = state.root && state.root.querySelector('[data-admin-panel-body="join-requests"]');
        if (data && config && body) body.innerHTML = renderPanelData(config, data);
    }

    function rerenderPanel(panelId) {
        const data = state.panelData[panelId];
        const config = PANEL_CONFIGS.find((item) => item.id === panelId);
        const body = state.root && state.root.querySelector(`[data-admin-panel-body="${panelId}"]`);
        if (data && config && body) body.innerHTML = renderPanelData(config, data);
    }

    function setNotice(type, message) {
        const notice = state.root && state.root.querySelector('[data-admin-notice]');
        if (!notice) return;
        const text = String(message || '').trim();
        notice.hidden = !text;
        notice.className = `admin-notice${type ? ` admin-notice--${type}` : ''}`;
        notice.textContent = text;
    }

    async function fetchJson(path, params) {
        return AstraApiClient.request(path, {
            baseUrl: state.apiBase,
            params,
            signal: state.lifecycleController && state.lifecycleController.signal
        });
    }

    function beginRequestGeneration() {
        if (state.lifecycleController && !state.lifecycleController.signal.aborted) {
            state.lifecycleController.abort();
        }
        state.lifecycleController = new AbortController();
        state.requestGeneration += 1;
        return state.requestGeneration;
    }

    function invalidateRequests() {
        state.requestGeneration += 1;
        if (state.lifecycleController && !state.lifecycleController.signal.aborted) {
            state.lifecycleController.abort();
        }
        state.lifecycleController = null;
    }

    function isCurrentRequest(generation) {
        return Boolean(
            state.active
            && generation === state.requestGeneration
            && state.lifecycleController
            && !state.lifecycleController.signal.aborted
        );
    }

    function resolveApiBase() {
        let fromUrl = '';
        try {
            fromUrl = new URLSearchParams(window.location.search).get('apiBase') || '';
        } catch (error) {}
        if (fromUrl) {
            const normalized = normalizeApiBase(fromUrl);
            localStorage.setItem(API_BASE_STORAGE_KEY, normalized);
            return normalized;
        }
        const stored = localStorage.getItem(API_BASE_STORAGE_KEY) || '';
        if (stored) return normalizeApiBase(stored);
        const configBase = window.CONFIG && window.CONFIG.backend && window.CONFIG.backend.apiBaseUrl;
        return normalizeApiBase(configBase || '');
    }

    function normalizeApiBase(value) {
        return AstraApiClient.normalizeBaseUrl(value);
    }

    function renderLoading(text) {
        return `
            <div class="admin-loading">
                <i data-lucide="loader-circle"></i>
                <span>${escapeHtml(text)}</span>
            </div>
        `;
    }

    function renderError(error, title) {
        return `
            <div class="admin-error">
                <i data-lucide="triangle-alert"></i>
                <strong>${escapeHtml(title)}</strong>
                <span>${escapeHtml(errorMessage(error))}</span>
            </div>
        `;
    }

    function errorMessage(error) {
        return AstraApiClient.message(error);
    }

    function valueAt(item, key) {
        return String(key).split('.').reduce((value, part) => {
            if (value === null || value === undefined) return undefined;
            return value[part];
        }, item);
    }

    function formatValue(value, column) {
        if (value === null || value === undefined || value === '') return '--';
        if (column.type === 'date') return formatDate(value);
        if (column.type === 'bytes') return formatBytes(value);
        if (column.type === 'boolean') return value ? 'yes' : 'no';
        if (typeof value === 'number') return formatNumber(value);
        if (typeof value === 'boolean') return value ? 'true' : 'false';
        if (typeof value === 'object') return JSON.stringify(value);
        return String(value);
    }

    function formatSummaryValue(value) {
        if (value === null || value === undefined || value === '') return '--';
        if (typeof value === 'number') return escapeHtml(formatNumber(value));
        return `<span class="admin-status-pill admin-status-pill--${statusClass(value)}">${escapeHtml(String(value))}</span>`;
    }

    function formatNumber(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return String(value || 0);
        return number.toLocaleString('zh-CN');
    }

    function formatBytes(value) {
        const number = Number(value);
        if (!Number.isFinite(number)) return '--';
        if (number < 1024) return `${number} B`;
        if (number < 1024 * 1024) return `${(number / 1024).toFixed(1)} KB`;
        return `${(number / 1024 / 1024).toFixed(1)} MB`;
    }

    function formatDate(value) {
        const date = new Date(value);
        if (Number.isNaN(date.getTime())) return String(value);
        return date.toLocaleString('zh-CN', {
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
    }

    function statusClass(value) {
        const normalized = String(value || 'empty').toLowerCase().replace(/[^a-z0-9]+/g, '-');
        if (['success', 'approved', 'active', 'trusted', 'ok', 'yes', 'true', 'queued'].includes(normalized)) return 'good';
        if (['pending', 'pending-review', 'watch', 'warning', 'triaged', 'in-progress', 'planned'].includes(normalized)) return 'warn';
        if (['failed', 'rejected', 'blocked', 'critical', 'cancelled', 'closed', 'no', 'false'].includes(normalized)) return 'bad';
        if (normalized === 'readonly') return 'readonly';
        return 'neutral';
    }

    function getDashboard() {
        return state.root && state.root.querySelector('[data-admin-dashboard]');
    }

    function clearDashboardDom() {
        if (!state.root) return;
        const stats = state.root.querySelector('[data-admin-stats]');
        const databaseMap = state.root.querySelector('[data-admin-database-map]');
        const summary = state.root.querySelector('[data-admin-summary]');
        if (stats) stats.innerHTML = '';
        if (databaseMap) databaseMap.innerHTML = '';
        if (summary) summary.innerHTML = '';
        state.root.querySelectorAll('[data-admin-panel-body]').forEach((body) => {
            body.innerHTML = renderLoading('等待权威刷新');
        });
        state.root.querySelectorAll('[data-admin-panel-meta]').forEach((meta) => {
            meta.textContent = '--';
        });
    }

    function setBusy(value) {
        state.busy = value;
        if (state.root) state.root.classList.toggle('is-busy', value);
    }

    function refreshIcons() {
        if (typeof lucide !== 'undefined' && lucide && typeof lucide.createIcons === 'function') {
            try {
                lucide.createIcons({ attrs: { 'stroke-width': 1.8 }, root: state.root || document });
            } catch (error) {}
        }
    }

    function escapeHtml(value) {
        return String(value === null || value === undefined ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function escapeAttr(value) {
        return escapeHtml(value);
    }

    window.initAdmin = initAdmin;
    window.destroyAdmin = destroyAdmin;
    window.initAdminGovernance = initAdmin;
    window.AdminGovernance = {
        version: ADMIN_ASSET_VERSION,
        refresh: refreshAll
    };
})();

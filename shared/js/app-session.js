(function (global) {
    'use strict';

    const PROTECTED_PAGES = new Set(['student', 'teacher', 'admin']);
    const ROLE_PAGE_ACCESS = Object.freeze({
        student: new Set(['student']),
        teacher: new Set(['teacher']),
        admin: new Set(['teacher', 'admin'])
    });
    const ROLE_LANDING = Object.freeze({ student: 'student', teacher: 'teacher', admin: 'admin' });
    const ROLE_LABEL = Object.freeze({ student: '学生', teacher: '教师', admin: '管理员' });
    const state = {
        user: null,
        apiBase: '',
        bootPromise: null,
        resolveBoot: null,
        overlay: null,
        view: 'login',
        busy: false,
        status: null,
        appStarted: false,
        explicitSignedOut: false
    };

    function escapeHtml(value) {
        return String(value == null ? '' : value)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    function api() {
        if (!global.AstraApiClient || typeof global.AstraApiClient.request !== 'function') {
            throw new Error('API 客户端尚未就绪');
        }
        return global.AstraApiClient;
    }

    function resolveApiBase() {
        let candidate = '';
        try {
            candidate = new URLSearchParams(global.location.search).get('apiBase') || '';
        } catch (_) {}
        if (!candidate && global.CONFIG && global.CONFIG.backend) {
            candidate = global.CONFIG.backend.apiBaseUrl || '';
        }
        return api().normalizeBaseUrl(candidate);
    }

    function request(path, options) {
        return api().request(path, Object.assign({
            baseUrl: state.apiBase,
            dispatchAuthRequired: false
        }, options || {}));
    }

    function roleLanding(role) {
        return ROLE_LANDING[String(role || '')] || 'planets';
    }

    function canAccessPage(page, role) {
        const target = String(page || 'planets');
        if (!PROTECTED_PAGES.has(target)) return true;
        const access = ROLE_PAGE_ACCESS[String(role || (state.user && state.user.role) || '')];
        return Boolean(access && access.has(target));
    }

    function guardPage(page) {
        const target = String(page || 'planets');
        if (canAccessPage(target)) return target;
        const fallback = roleLanding(state.user && state.user.role);
        global.dispatchEvent(new CustomEvent('astra:navigation-denied', {
            detail: { requestedPage: target, fallbackPage: fallback, role: state.user && state.user.role }
        }));
        return fallback;
    }

    function setApplicationLocked(locked) {
        document.body.classList.toggle('app-auth-locked', Boolean(locked));
        ['navbar', 'main-content'].forEach(function (id) {
            const node = document.getElementById(id) || document.querySelector('.' + id);
            if (!node) return;
            node.setAttribute('aria-hidden', locked ? 'true' : 'false');
            if ('inert' in node) node.inert = Boolean(locked);
        });
        document.querySelectorAll('footer').forEach(function (node) {
            node.setAttribute('aria-hidden', locked ? 'true' : 'false');
            if ('inert' in node) node.inert = Boolean(locked);
        });
    }

    function dismissLoadingScreen() {
        if (typeof global.__dismissEnglabLoading === 'function') {
            global.__dismissEnglabLoading();
            return;
        }
        const screen = document.getElementById('loading-screen');
        if (screen) screen.classList.add('hidden');
    }

    function applyRoleUI() {
        const role = state.user && state.user.role;
        document.documentElement.dataset.sessionRole = role || 'anonymous';
        document.querySelectorAll('[data-app-roles]').forEach(function (node) {
            const roles = String(node.dataset.appRoles || '').split(',').map(function (item) {
                return item.trim();
            }).filter(Boolean);
            const visible = Boolean(role && roles.includes(role));
            node.hidden = !visible;
            node.setAttribute('aria-hidden', visible ? 'false' : 'true');
            if ('inert' in node) node.inert = !visible;
        });
        PROTECTED_PAGES.forEach(function (page) {
            const section = document.getElementById('page-' + page);
            if (!section) return;
            const allowed = canAccessPage(page, role);
            section.hidden = !allowed;
            section.setAttribute('aria-hidden', allowed ? 'false' : 'true');
            if ('inert' in section) section.inert = !allowed;
            if (!allowed) section.classList.remove('active');
        });
    }

    function renderSessionControl() {
        const existing = document.querySelector('[data-app-session-control]');
        if (existing) existing.remove();
        if (!state.user) return;
        const host = document.querySelector('#navbar .nav-container');
        if (!host) return;
        const node = document.createElement('div');
        node.className = 'app-session-control';
        node.dataset.appSessionControl = 'true';
        node.innerHTML = `
            <button type="button" class="app-session-control__trigger" data-session-action="toggle" aria-expanded="false">
                <span class="app-session-control__avatar" aria-hidden="true">${escapeHtml(String(ROLE_LABEL[state.user.role] || state.user.display_name || state.user.username || '?').slice(0, 1))}</span>
                <span class="app-session-control__identity">
                    <strong>${escapeHtml(state.user.display_name || state.user.username)}</strong>
                    <small>${escapeHtml(ROLE_LABEL[state.user.role] || state.user.role)}</small>
                </span>
            </button>
            <div class="app-session-control__menu" data-session-menu hidden>
                <button type="button" data-session-action="workspace">进入${escapeHtml(ROLE_LABEL[state.user.role] || '')}工作台</button>
                <button type="button" data-session-action="logout">安全退出</button>
            </div>`;
        node.addEventListener('click', handleSessionControlClick);
        host.appendChild(node);
    }

    function handleSessionControlClick(event) {
        const actionNode = event.target instanceof Element ? event.target.closest('[data-session-action]') : null;
        if (!actionNode) return;
        const action = actionNode.dataset.sessionAction;
        const control = actionNode.closest('[data-app-session-control]');
        const menu = control && control.querySelector('[data-session-menu]');
        if (action === 'toggle' && menu) {
            const willOpen = menu.hidden;
            menu.hidden = !willOpen;
            actionNode.setAttribute('aria-expanded', willOpen ? 'true' : 'false');
            return;
        }
        if (action === 'workspace') {
            if (menu) menu.hidden = true;
            if (global.Router && typeof global.Router.navigateTo === 'function') {
                global.Router.navigateTo(roleLanding(state.user && state.user.role), true);
            } else {
                global.location.hash = roleLanding(state.user && state.user.role);
            }
            return;
        }
        if (action === 'logout') logout();
    }

    function statusMarkup() {
        if (!state.status) return '';
        return `<div class="app-auth-status app-auth-status--${escapeHtml(state.status.type || 'info')}" role="status">${escapeHtml(state.status.message)}</div>`;
    }

    function loginForm() {
        return `
            <form class="app-auth-form" data-app-auth-form="login">
                <label>账号<input name="username" autocomplete="username" minlength="3" maxlength="64" required></label>
                <label>密码<input name="password" type="password" autocomplete="current-password" minlength="8" maxlength="128" required></label>
                <button class="app-auth-primary" type="submit" ${state.busy ? 'disabled' : ''}>${state.busy ? '正在验证…' : '登录并进入星序'}</button>
            </form>`;
    }

    function registerForm() {
        return `
            <form class="app-auth-form" data-app-auth-form="register">
                <label>账号<input name="username" autocomplete="username" minlength="3" maxlength="64" required></label>
                <label>显示名称<input name="display_name" autocomplete="name" minlength="1" maxlength="80" required></label>
                <label>账号性质<select name="role" required><option value="student">学生</option><option value="teacher">教师</option></select></label>
                <label>密码<input name="password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required></label>
                <label>确认密码<input name="password_confirm" type="password" autocomplete="new-password" minlength="8" maxlength="128" required></label>
                <button class="app-auth-primary" type="submit" ${state.busy ? 'disabled' : ''}>${state.busy ? '正在创建…' : '创建账号并进入'}</button>
            </form>`;
    }

    function resetForm() {
        return `
            <form class="app-auth-form" data-app-auth-form="reset-request">
                <label>账号<input name="username" autocomplete="username" minlength="3" maxlength="64" required></label>
                <button class="app-auth-primary" type="submit" ${state.busy ? 'disabled' : ''}>申请重置凭据</button>
            </form>
            <form class="app-auth-form app-auth-form--secondary" data-app-auth-form="reset-confirm">
                <label>重置凭据<input name="token" autocomplete="one-time-code" required></label>
                <label>新密码<input name="password" type="password" autocomplete="new-password" minlength="8" maxlength="128" required></label>
                <button class="app-auth-secondary" type="submit" ${state.busy ? 'disabled' : ''}>确认新密码</button>
            </form>`;
    }

    function renderPortal() {
        if (!state.overlay) return;
        const forms = state.view === 'register' ? registerForm() : (state.view === 'reset' ? resetForm() : loginForm());
        state.overlay.innerHTML = `
            <main class="app-auth-portal" aria-labelledby="app-auth-title">
                <section class="app-auth-context">
                    <div class="app-auth-brand" aria-label="星序认证入口">ASTRA <span>星序</span></div>
                    <div>
                        <p class="app-auth-context__kicker">统一身份入口</p>
                        <h1 id="app-auth-title">先确认身份，再进入你的星序。</h1>
                        <p>学生只进入学习空间，教师获得教学与班级管理，管理员进入全局治理。权限由服务端会话确认，不由页面自行声明。</p>
                    </div>
                    <ul class="app-auth-context__roles" aria-label="角色权限说明">
                        <li><span>学生</span>课程、班级、作业与提交</li>
                        <li><span>教师</span>教学、作业、审批与班级</li>
                        <li><span>管理员</span>用户、组织、审计与全局状态</li>
                    </ul>
                </section>
                <section class="app-auth-panel">
                    <div class="app-auth-tabs" role="tablist" aria-label="账号操作">
                        <button type="button" data-app-auth-view="login" class="${state.view === 'login' ? 'active' : ''}">登录</button>
                        <button type="button" data-app-auth-view="register" class="${state.view === 'register' ? 'active' : ''}">注册</button>
                        <button type="button" data-app-auth-view="reset" class="${state.view === 'reset' ? 'active' : ''}">重置密码</button>
                    </div>
                    ${statusMarkup()}
                    ${forms}
                    <p class="app-auth-panel__note">登录凭据由 HttpOnly Cookie 与服务端 Session 协调保存；本页面不会把访问令牌写入浏览器存储。</p>
                </section>
            </main>`;
    }

    function ensurePortal() {
        if (!state.overlay) {
            state.overlay = document.createElement('div');
            state.overlay.className = 'app-auth-overlay';
            state.overlay.dataset.appAuthOverlay = 'true';
            state.overlay.addEventListener('click', handlePortalClick);
            state.overlay.addEventListener('submit', handlePortalSubmit);
            document.body.appendChild(state.overlay);
        }
        state.overlay.hidden = false;
        renderPortal();
        setApplicationLocked(true);
        dismissLoadingScreen();
    }

    function hidePortal() {
        if (state.overlay) state.overlay.hidden = true;
        setApplicationLocked(false);
    }

    function handlePortalClick(event) {
        const viewNode = event.target instanceof Element ? event.target.closest('[data-app-auth-view]') : null;
        if (!viewNode || state.busy) return;
        state.view = viewNode.dataset.appAuthView || 'login';
        state.status = null;
        renderPortal();
    }

    function formValue(form, name) {
        return String(new FormData(form).get(name) || '').trim();
    }

    async function handlePortalSubmit(event) {
        const form = event.target;
        if (!(form instanceof HTMLFormElement) || !form.dataset.appAuthForm || state.busy) return;
        event.preventDefault();
        if (!form.reportValidity()) return;
        state.busy = true;
        state.status = null;
        renderPortal();
        try {
            if (form.dataset.appAuthForm === 'login') await submitLogin(form);
            if (form.dataset.appAuthForm === 'register') await submitRegister(form);
            if (form.dataset.appAuthForm === 'reset-request') await submitResetRequest(form);
            if (form.dataset.appAuthForm === 'reset-confirm') await submitResetConfirm(form);
        } catch (error) {
            state.status = { type: 'error', message: api().message(error) };
        } finally {
            state.busy = false;
            if (!state.user) renderPortal();
        }
    }

    async function submitLogin(form) {
        await request('/api/auth/login', {
            method: 'POST',
            body: { username: formValue(form, 'username'), password: formValue(form, 'password') }
        });
        await reconcileSession();
    }

    async function submitRegister(form) {
        const password = formValue(form, 'password');
        if (password !== formValue(form, 'password_confirm')) {
            throw Object.assign(new Error('两次输入的密码不一致'), { code: 'invalid_request' });
        }
        const username = formValue(form, 'username');
        await request('/api/auth/register', {
            method: 'POST',
            body: {
                username: username,
                display_name: formValue(form, 'display_name'),
                password: password,
                role: formValue(form, 'role')
            }
        });
        await request('/api/auth/login', { method: 'POST', body: { username: username, password: password } });
        await reconcileSession();
    }

    async function submitResetRequest(form) {
        const result = await request('/api/auth/password-reset/request', {
            method: 'POST', body: { username: formValue(form, 'username') }
        });
        state.status = {
            type: 'success',
            message: result && result.reset_token
                ? '开发环境重置凭据：' + result.reset_token
                : '若账号有效，重置凭据将通过已配置的受控通道送达。'
        };
    }

    async function submitResetConfirm(form) {
        await request('/api/auth/password-reset/confirm', {
            method: 'POST',
            body: { token: formValue(form, 'token'), password: formValue(form, 'password') }
        });
        state.view = 'login';
        state.status = { type: 'success', message: '密码已更新，旧会话已撤销，请重新登录。' };
    }

    async function reconcileSession() {
        const user = await request('/api/users/me', { method: 'GET' });
        completeAuthentication(user);
    }

    function completeAuthentication(user) {
        if (!user || !ROLE_PAGE_ACCESS[user.role]) throw new Error('账号角色无效');
        state.user = Object.freeze(Object.assign({}, user));
        state.explicitSignedOut = false;
        applyRoleUI();
        renderSessionControl();
        hidePortal();
        global.dispatchEvent(new CustomEvent('astra:session-ready', { detail: { user: state.user } }));
        if (state.appStarted) {
            global.location.reload();
            return;
        }
        if (state.resolveBoot) {
            state.resolveBoot(true);
            state.resolveBoot = null;
        }
    }

    function requireAuthentication() {
        state.user = null;
        state.appStarted = Boolean(global.Router && global.Router._initialEnterFired);
        state.view = 'login';
        state.status = state.explicitSignedOut
            ? null
            : { type: 'error', message: '登录状态已失效，请重新登录。' };
        applyRoleUI();
        ensurePortal();
    }

    async function logout() {
        try {
            await request('/api/auth/logout', { method: 'POST' });
        } catch (error) {
            if (!(error && error.status === 401)) {
                global.alert(api().message(error));
                return;
            }
        }
        state.user = null;
        global.location.reload();
    }

    function handleSignedOut() {
        state.explicitSignedOut = true;
        requireAuthentication();
    }

    function bootstrap() {
        if (state.bootPromise) return state.bootPromise;
        state.apiBase = resolveApiBase();
        setApplicationLocked(true);
        global.addEventListener('astra:api-auth-required', requireAuthentication);
        global.addEventListener('astra:session-signed-out', handleSignedOut);
        state.bootPromise = new Promise(function (resolve) {
            state.resolveBoot = resolve;
            request('/api/users/me', { method: 'GET' })
                .then(completeAuthentication)
                .catch(function (error) {
                    state.view = 'login';
                    state.status = error && error.status === 401
                        ? null
                        : { type: 'error', message: api().message(error) };
                    ensurePortal();
                });
        });
        return state.bootPromise;
    }

    global.AstraApplicationSession = Object.freeze({
        bootstrap: bootstrap,
        getUser: function () { return state.user; },
        getRole: function () { return state.user && state.user.role; },
        resolveApiBase: resolveApiBase,
        roleLanding: roleLanding,
        canAccessPage: canAccessPage,
        guardPage: guardPage,
        applyRoleUI: applyRoleUI,
        requireAuthentication: requireAuthentication,
        logout: logout
    });
})(window);

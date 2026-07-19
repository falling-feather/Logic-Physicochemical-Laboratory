/*
 * Student course scope for Code Space.
 *
 * This page owns its own ephemeral class/course context. It deliberately uses
 * the shared cookie-only client and never persists class selection locally.
 */
(function (global) {
    'use strict';

    const state = {
        phase: 'booting',
        role: null,
        classes: [],
        selectedClassId: null,
        courseIds: null,
        generation: 0,
        controller: null,
        started: null,
        redirecting: false
    };

    function positiveInteger(value) {
        return Number.isInteger(value) && value > 0;
    }

    function api() {
        return global.AstraApiClient && typeof global.AstraApiClient.request === 'function'
            ? global.AstraApiClient
            : null;
    }

    function isCurrent(scope) {
        return scope && scope.generation === state.generation && state.controller === scope.controller;
    }

    function beginRequest() {
        if (state.controller) state.controller.abort();
        const controller = new AbortController();
        state.controller = controller;
        return { generation: ++state.generation, controller, signal: controller.signal };
    }

    function clearCourseScope() {
        state.courseIds = null;
        const adapter = global.CvCourseStateAdapter;
        if (adapter && typeof adapter.configureHttp === 'function') adapter.configureHttp({});
    }

    function classLabel(classItem) {
        return [classItem.name || ('班级 ' + classItem.id), classItem.grade, classItem.term]
            .filter(Boolean)
            .join(' · ');
    }

    function validClasses(payload) {
        if (!Array.isArray(payload)) return null;
        const ids = new Set();
        const classes = [];
        for (const item of payload) {
            if (!item || typeof item !== 'object' || !positiveInteger(item.id) || ids.has(item.id)) return null;
            ids.add(item.id);
            classes.push({ id: item.id, name: typeof item.name === 'string' ? item.name : '', grade: typeof item.grade === 'string' ? item.grade : '', term: typeof item.term === 'string' ? item.term : '' });
        }
        return classes;
    }

    function courseMapping(payload) {
        const manifest = global.CvCourseManifest;
        if (!manifest || !Array.isArray(manifest.courses) || !Array.isArray(payload)) return null;
        const expected = new Set(manifest.courses.map(course => course.course_key));
        const mapping = Object.create(null);
        for (const course of payload) {
            if (!course || typeof course !== 'object') return null;
            if (course.galaxy_key !== manifest.galaxy_key || !expected.has(course.course_key)) continue;
            if (!positiveInteger(course.id) || mapping[course.course_key]) return null;
            mapping[course.course_key] = course.id;
        }
        return Object.keys(mapping).length === expected.size ? mapping : null;
    }

    function redirectToLogin() {
        if (state.redirecting) return;
        state.redirecting = true;
        state.phase = 'redirecting';
        renderNavbar();
        try { global.location.assign('../index.html'); }
        catch (_) { global.location.href = '../index.html'; }
    }

    function requestFailure(error) {
        if (Number(error && error.status || 0) === 401) {
            redirectToLogin();
            return true;
        }
        return false;
    }

    function gate() {
        if (state.role !== 'student') return { blocked: false };
        if (state.phase === 'ready') return { blocked: false };
        const copy = {
            booting: ['正在确认学习范围', '正在确认你的课程范围。'],
            selecting_class: ['选择班级后继续', '请选择班级后再打开课程内容。'],
            loading_scope: ['正在切换班级', '正在确认该班级的课程与发布状态。'],
            no_classes: ['当前没有可用班级', '加入班级后才能打开课程内容。'],
            unavailable: ['课程范围暂不可用', '当前班级缺少完整课程范围或服务暂不可用，请稍后重试。'],
            redirecting: ['正在返回登录入口', '请登录后再打开代码空间。']
        }[state.phase] || ['课程范围暂不可用', '暂不能打开课程内容。'];
        return { blocked: true, title: copy[0], message: copy[1] };
    }

    function renderNavbar() {
        if (!global.document) return;
        const controls = document.getElementById('cv-class-context');
        const select = document.getElementById('cv-class-select');
        const status = document.getElementById('cv-class-status');
        const showSelector = state.role === 'student' && state.classes.length > 1 && !state.redirecting;
        if (controls) controls.hidden = !showSelector;
        document.body && document.body.classList.toggle('cv-has-class-selector', showSelector);
        if (!showSelector || !select) return;

        const selected = state.selectedClassId == null ? '' : String(state.selectedClassId);
        select.replaceChildren();
        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = state.phase === 'selecting_class' ? '选择班级…' : '切换班级…';
        select.append(placeholder);
        state.classes.forEach(classItem => {
            const option = document.createElement('option');
            option.value = String(classItem.id);
            option.textContent = classLabel(classItem);
            select.append(option);
        });
        select.value = selected;
        select.disabled = state.phase === 'loading_scope';
        select.onchange = () => {
            const classId = Number(select.value);
            if (positiveInteger(classId)) selectClass(classId);
        };
        if (status) {
            status.textContent = state.phase === 'selecting_class'
                ? '选择后加载课程'
                : state.phase === 'loading_scope'
                    ? '正在加载课程'
                    : '';
        }
    }

    function refreshViews() {
        renderNavbar();
        if (!global.CvRouter || !global.CvRouter.initialized) return;
        const currentPage = global.CvRouter && global.CvRouter.currentPage;
        if (currentPage === 'challenge' && global.CvCourseChallenge) global.CvCourseChallenge.refresh();
        else if (currentPage === 'lesson' && global.CvCourseCatalog) global.CvCourseCatalog.renderLesson();
        else if (global.CvCourseCatalog) global.CvCourseCatalog.refresh();
    }

    function stateFetcher(scope, requestError) {
        return async (url) => {
            const requestUrl = new URL(url, global.location.origin);
            const params = {};
            requestUrl.searchParams.forEach((value, key) => { params[key] = value; });
            try {
                const payload = await api().request(requestUrl.pathname, {
                    method: 'GET',
                    params,
                    signal: scope.signal,
                    dispatchAuthRequired: false
                });
                return { ok: true, json: async () => payload };
            } catch (error) {
                requestError.value = error;
                throw error;
            }
        };
    }

    async function selectClass(classId) {
        const selected = state.classes.find(item => item.id === classId);
        if (!selected || state.role !== 'student') return false;
        const scope = beginRequest();
        state.selectedClassId = selected.id;
        state.phase = 'loading_scope';
        clearCourseScope();
        refreshViews();
        try {
            const courses = await api().request('/api/courses', {
                method: 'GET',
                params: { class_id: selected.id },
                signal: scope.signal,
                dispatchAuthRequired: false
            });
            if (!isCurrent(scope)) return false;
            const courseIds = courseMapping(courses);
            if (!courseIds) throw new Error('code-space course mapping unavailable');

            const adapter = global.CvCourseStateAdapter;
            if (!adapter || typeof adapter.configureHttp !== 'function' || typeof adapter.refresh !== 'function') {
                throw new Error('course release adapter unavailable');
            }
            const unitRequestError = { value: null };
            adapter.configureHttp({
                course_ids: courseIds,
                class_id: selected.id,
                fetcher: stateFetcher(scope, unitRequestError)
            });
            const refreshed = await adapter.refresh();
            if (!isCurrent(scope)) return false;
            if (!refreshed) throw unitRequestError.value || new Error('course release state unavailable');

            state.courseIds = courseIds;
            state.phase = 'ready';
            refreshViews();
            return true;
        } catch (error) {
            if (!isCurrent(scope)) return false;
            if (requestFailure(error)) return false;
            state.phase = 'unavailable';
            clearCourseScope();
            refreshViews();
            return false;
        }
    }

    async function start() {
        if (state.started) return state.started;
        state.started = (async () => {
            const scope = beginRequest();
            const client = api();
            if (!client) {
                state.phase = 'static_preview';
                refreshViews();
                return true;
            }
            let user;
            try {
                user = await client.request('/api/users/me', {
                    method: 'GET',
                    signal: scope.signal,
                    dispatchAuthRequired: false
                });
            } catch (error) {
                if (!isCurrent(scope)) return false;
                if (requestFailure(error)) return false;
                if (Number(error && error.status || 0) === 404 || error && (error.code === 'network' || error.code === 'offline')) {
                    state.phase = 'static_preview';
                    refreshViews();
                    return true;
                }
                state.phase = 'unavailable';
                clearCourseScope();
                refreshViews();
                return false;
            }
            if (!isCurrent(scope) || !user || typeof user !== 'object' || typeof user.role !== 'string') {
                state.phase = 'unavailable';
                clearCourseScope();
                refreshViews();
                return false;
            }
            state.role = user.role;
            if (user.role !== 'student') {
                state.phase = 'nonstudent';
                refreshViews();
                return true;
            }
            try {
                const payload = await client.request('/api/classes', {
                    method: 'GET',
                    params: { mine: true },
                    signal: scope.signal,
                    dispatchAuthRequired: false
                });
                if (!isCurrent(scope)) return false;
                const classes = validClasses(payload);
                if (!classes) throw new Error('invalid class response');
                state.classes = classes;
                if (!classes.length) {
                    state.phase = 'no_classes';
                    clearCourseScope();
                    refreshViews();
                    return false;
                }
                if (classes.length > 1) {
                    state.phase = 'selecting_class';
                    clearCourseScope();
                    refreshViews();
                    return true;
                }
                return selectClass(classes[0].id);
            } catch (error) {
                if (!isCurrent(scope)) return false;
                if (requestFailure(error)) return false;
                state.phase = 'unavailable';
                clearCourseScope();
                refreshViews();
                return false;
            }
        })();
        return state.started;
    }

    function resolve(activity) {
        const manifest = global.CvCourseManifest;
        if (
            state.role !== 'student' || state.phase !== 'ready' || !state.courseIds ||
            !activity || activity.galaxy_key !== (manifest && manifest.galaxy_key) ||
            !positiveInteger(state.selectedClassId) || !positiveInteger(state.courseIds[activity.course_key])
        ) return null;
        return {
            authenticated: true,
            role: 'student',
            class_id: state.selectedClassId,
            course_id: state.courseIds[activity.course_key]
        };
    }

    global.AstraCodeSpaceStudentContext = Object.freeze({ resolve });
    global.CvStudentContext = Object.freeze({
        start,
        selectClass,
        gate,
        getState: () => ({
            phase: state.phase,
            role: state.role,
            class_id: state.selectedClassId,
            classes: state.classes.slice(),
            course_ids: state.courseIds && Object.assign({}, state.courseIds)
        })
    });
})(window);

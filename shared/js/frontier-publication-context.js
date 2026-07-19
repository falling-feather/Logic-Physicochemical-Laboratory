/* Future Galaxy student publication context: Cookie session -> class -> course map -> BE-004 units. */
(function installFutureGalaxyPublicationContext(global) {
    'use strict';

    if (global.FutureGalaxyPublicationContext) return;

    const GALAXY_KEY = 'future-galaxy';
    const MANAGED_PAGES = new Set(['frontier', 'cosmos', 'engineering', 'datascience', 'infotech', 'materials', 'humanities']);
    const state = {
        generation: 0,
        controller: null,
        classId: '',
        courseIds: null,
        userId: ''
    };

    const normalizeList = (payload) => Array.isArray(payload)
        ? payload
        : (payload && Array.isArray(payload.items) ? payload.items : []);
    const entityId = (item) => item && (item.id !== undefined && item.id !== null) ? item.id : '';
    const abortController = (controller) => {
        if (controller && typeof controller.abort === 'function') controller.abort();
    };

    function getManifest() {
        const manifest = global.FrontierCourseManifest;
        return manifest
            && manifest.galaxy_key === GALAXY_KEY
            && Array.isArray(manifest.courses)
            && typeof manifest.configureHttp === 'function'
            && typeof manifest.refresh === 'function'
            ? manifest
            : null;
    }

    function beginContext() {
        abortController(state.controller);
        state.generation += 1;
        state.controller = new AbortController();
        return {
            generation: state.generation,
            controller: state.controller,
            signal: state.controller.signal
        };
    }

    function isCurrent(context) {
        return Boolean(
            context
            && context.generation === state.generation
            && context.controller === state.controller
            && !context.signal.aborted
        );
    }

    function pageFromHash() {
        const page = String((global.location && global.location.hash) || '#frontier').replace(/^#/, '').split('/')[0] || 'frontier';
        return MANAGED_PAGES.has(page) ? page : '';
    }

    function rerenderIfActive() {
        const page = pageFromHash();
        if (!page) return;
        if (global.FrontierLearning && typeof global.FrontierLearning.renderRoute === 'function') {
            global.FrontierLearning.renderRoute(page);
        } else if (typeof global.initFrontierCourse === 'function') {
            global.initFrontierCourse();
        }
    }

    function close(context) {
        if (context && !isCurrent(context)) return false;
        abortController(state.controller);
        state.generation += 1;
        state.controller = null;
        const manifest = getManifest();
        if (manifest) manifest.configureHttp({});
        state.classId = '';
        state.courseIds = null;
        state.userId = '';
        rerenderIfActive();
        return true;
    }

    function validCourseId(value) {
        return (typeof value === 'number' && Number.isFinite(value) && value > 0)
            || (typeof value === 'string' && value.trim().length > 0);
    }

    function buildCourseIdMap(payload, manifest) {
        const target = manifest || getManifest();
        if (!target) return null;
        const expected = new Set(target.courses.map((course) => course.course_key));
        const map = {};
        for (const item of normalizeList(payload)) {
            if (!item || item.galaxy_key !== GALAXY_KEY) continue;
            const courseKey = String(item.course_key || '');
            if (!expected.has(courseKey) || Object.prototype.hasOwnProperty.call(map, courseKey) || !validCourseId(item.id)) return null;
            map[courseKey] = item.id;
        }
        return Object.keys(map).length === expected.size ? Object.freeze(map) : null;
    }

    async function requestSameOriginJson(path, options) {
        if (typeof global.fetch !== 'function') throw new Error('Future course authority fetch is unavailable');
        const request = options || {};
        const origin = (global.location && global.location.origin) || 'http://localhost';
        const url = new URL(path, origin);
        Object.entries(request.params || {}).forEach(([key, value]) => {
            if (value !== undefined && value !== null && String(value).trim() !== '') url.searchParams.set(key, String(value));
        });
        const response = await global.fetch(`${url.pathname}${url.search}`, {
            method: 'GET',
            credentials: 'same-origin',
            headers: { Accept: 'application/json' },
            signal: request.signal
        });
        if (!response || response.ok !== true || typeof response.json !== 'function') throw new Error('Future course authority request failed');
        return response.json();
    }

    async function configureForContext(context, classId, coursePayload) {
        const manifest = getManifest();
        if (!manifest || !isCurrent(context)) return { availability: 'unavailable', source: 'manifest-unavailable' };
        const courseIds = buildCourseIdMap(coursePayload, manifest);
        if (!courseIds) {
            close(context);
            return { availability: 'unavailable', source: 'course-map-unavailable' };
        }
        const configured = manifest.configureHttp({
            course_ids: courseIds,
            class_id: classId,
            fetcher: (path, request) => {
                if (!isCurrent(context)) return Promise.reject(new Error('Future course context superseded'));
                return global.fetch(path, {
                    ...(request || {}),
                    credentials: 'same-origin',
                    signal: context.signal
                });
            }
        });
        if (!configured) {
            close(context);
            return { availability: 'unavailable', source: 'http-config-unavailable' };
        }
        state.classId = String(classId);
        state.courseIds = courseIds;
        const snapshot = await manifest.refresh();
        if (!isCurrent(context)) return { availability: 'unavailable', source: 'superseded' };
        rerenderIfActive();
        return snapshot;
    }

    async function configure(classId, coursePayload) {
        if (!classId) {
            close();
            return { availability: 'unavailable', source: 'class-context-unavailable' };
        }
        const context = beginContext();
        try {
            return await configureForContext(context, classId, coursePayload);
        } catch (error) {
            if (isCurrent(context)) close(context);
            return { availability: 'unavailable', source: 'course-context-unavailable' };
        }
    }

    async function bootstrap(user) {
        if (!user || user.role !== 'student') return { availability: 'legacy-boundary' };
        const userId = String(user.id || '');
        const context = beginContext();
        state.userId = userId;
        try {
            const classes = normalizeList(await requestSameOriginJson('/api/classes', {
                params: { mine: true }, signal: context.signal
            }));
            if (!isCurrent(context)) return { availability: 'unavailable', source: 'superseded' };
            if (classes.length !== 1) {
                close(context);
                return { availability: 'unavailable', source: 'class-selection-required' };
            }
            const classId = entityId(classes[0]);
            if (!classId) {
                close(context);
                return { availability: 'unavailable', source: 'class-context-unavailable' };
            }
            const courses = await requestSameOriginJson('/api/courses', {
                params: { class_id: classId }, signal: context.signal
            });
            return configureForContext(context, classId, courses);
        } catch (error) {
            if (isCurrent(context)) close(context);
            return { availability: 'unavailable', source: 'course-context-unavailable' };
        }
    }

    const api = Object.freeze({
        bootstrap,
        configure,
        close,
        buildCourseIdMap,
        snapshot: () => Object.freeze({ classId: state.classId, courseIds: state.courseIds, userId: state.userId })
    });
    global.FutureGalaxyPublicationContext = api;

    if (typeof global.addEventListener === 'function') {
        global.addEventListener('astra:session-ready', (event) => {
            const user = event && event.detail && event.detail.user;
            if (user && user.role === 'student') void bootstrap(user);
        });
        const closeOnAuthorityLoss = () => close();
        global.addEventListener('astra:api-auth-required', closeOnAuthorityLoss);
        global.addEventListener('astra:session-signed-out', closeOnAuthorityLoss);
    }

    const session = global.AstraApplicationSession;
    const currentUser = session && typeof session.getUser === 'function' ? session.getUser() : null;
    if (currentUser && currentUser.role === 'student') void bootstrap(currentUser);

    if (typeof module !== 'undefined' && module.exports) module.exports = api;
})(window);

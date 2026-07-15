// ===== Astra Page Registry =====
(function attachAstraPageRegistry(global) {
    'use strict';

    if (global.AstraPageRegistry) return;

    const definePage = (config) => Object.freeze({
        galaxy: config.galaxy || 'englab',
        tags: Object.freeze([...(config.tags || [])]),
        script: config.script || null,
        ready: config.ready || null,
        enter: config.enter || null,
        leave: config.leave || null
    });

    const definitions = Object.freeze({
        planets: definePage({
            galaxy: 'astra',
            script: 'pages/planets/planets.js?v=20260704qianduanV72',
            ready: 'initPlanets',
            enter: 'initPlanets',
            leave: 'destroyPlanets'
        }),
        home: definePage({
            galaxy: 'englab',
            script: 'pages/home/home.js?v=20260704qianduanV70',
            ready: 'initHome',
            enter: 'initHome'
        }),
        mathematics: definePage({ galaxy: 'englab', tags: ['course'] }),
        physics: definePage({ galaxy: 'englab', tags: ['course'] }),
        chemistry: definePage({ galaxy: 'englab', tags: ['course'] }),
        algorithms: definePage({ galaxy: 'englab', tags: ['course'] }),
        biology: definePage({ galaxy: 'englab', tags: ['course'] }),
        student: definePage({
            galaxy: 'englab',
            script: 'pages/student/student.js?v=20260711v740RoleShellP0',
            ready: 'initStudent',
            enter: 'initStudent',
            leave: 'destroyStudent'
        }),
        teacher: definePage({
            galaxy: 'englab',
            script: 'pages/teacher/teacher.js?v=20260711v740RoleShellP0',
            ready: 'initTeacher',
            enter: 'initTeacher',
            leave: 'destroyTeacher'
        }),
        admin: definePage({
            galaxy: 'englab',
            script: 'pages/admin/admin.js?v=20260711v740RoleShellP0',
            ready: 'initAdmin',
            enter: 'initAdmin',
            leave: 'destroyAdmin'
        }),
        frontier: definePage({ galaxy: 'frontier', tags: ['frontier'] }),
        cosmos: definePage({
            galaxy: 'frontier',
            tags: ['frontier'],
            script: 'pages/cosmos/earth-sun.js?v=20260630mainV64',
            ready: 'initCosmosSeasons',
            enter: 'initCosmosSeasons',
            leave: 'destroyCosmosSeasons'
        }),
        engineering: definePage({
            galaxy: 'frontier',
            tags: ['frontier'],
            script: 'pages/engineering/bridge-truss.js?v=20260630mainV64',
            ready: 'initBridgeTruss',
            enter: 'initBridgeTruss',
            leave: 'destroyBridgeTruss'
        }),
        datascience: definePage({
            galaxy: 'frontier',
            tags: ['frontier'],
            script: 'pages/datascience/linear-regression.js?v=20260630mainV64',
            ready: 'initLinearRegressionLab',
            enter: 'initLinearRegressionLab',
            leave: 'destroyLinearRegressionLab'
        }),
        infotech: definePage({
            galaxy: 'frontier',
            tags: ['frontier'],
            script: 'pages/infotech/network-layers.js?v=20260630mainV64',
            ready: 'initNetworkLayersLab',
            enter: 'initNetworkLayersLab',
            leave: 'destroyNetworkLayersLab'
        }),
        materials: definePage({
            galaxy: 'frontier',
            tags: ['frontier'],
            script: 'pages/materials/materials-lab.js?v=20260630mainV64',
            ready: 'initMaterialsLab',
            enter: 'initMaterialsLab',
            leave: 'destroyMaterialsLab'
        }),
        humanities: definePage({
            galaxy: 'frontier',
            tags: ['frontier'],
            script: 'pages/humanities/text-lab.js?v=20260630mainV64',
            ready: 'initHumanitiesLab',
            enter: 'initHumanitiesLab',
            leave: 'destroyHumanitiesLab'
        }),
        license: definePage({
            galaxy: 'englab',
            script: 'pages/about/about.js?v=20260630mainV64',
            ready: 'initLicense',
            enter: 'initLicense'
        }),
        changelog: definePage({
            galaxy: 'englab',
            script: 'pages/about/about.js?v=20260630mainV64',
            ready: 'initChangelog',
            enter: 'initChangelog'
        })
    });
    const pageNames = Object.freeze(Object.keys(definitions));

    const get = (page) => definitions[page] || null;
    const hasTag = (page, tag) => {
        const definition = get(page);
        return !!definition && definition.tags.includes(tag);
    };
    const invokeHook = (page, hook) => {
        const definition = get(page);
        const hookName = definition && definition[hook];
        if (!hookName) return false;
        const handler = global[hookName];
        if (typeof handler === 'function') handler();
        return true;
    };

    const registry = Object.freeze({
        get,
        has: (page) => !!get(page),
        pages: () => pageNames.slice(),
        pagesByTag: (tag) => pageNames.filter((page) => hasTag(page, tag)),
        hasTag,
        galaxyFor: (page) => {
            const definition = get(page);
            return definition ? definition.galaxy : 'englab';
        },
        scriptFor: (page) => {
            const definition = get(page);
            return definition ? definition.script : null;
        },
        isReady: (page) => {
            const definition = get(page);
            const hookName = definition && definition.ready;
            return !hookName || typeof global[hookName] === 'function';
        },
        enter: (page) => invokeHook(page, 'enter'),
        leave: (page) => invokeHook(page, 'leave')
    });

    Object.defineProperty(global, 'AstraPageRegistry', {
        value: registry,
        configurable: false,
        enumerable: true,
        writable: false
    });
})(window);

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const read = (file) => fs.readFileSync(path.join(root, file), 'utf8');

const configSource = read('shared/js/config.js');
const registrySource = read('shared/js/experiment-registry.js');
const moduleSelector = read('shared/js/module-selector.js');
const router = read('shared/js/router.js');
const html = read('index.html');
const main = read('shared/js/main.js');
const serviceWorker = read('sw.js');
const context = { window: {} };

vm.createContext(context);
vm.runInContext(configSource, context, { filename: 'shared/js/config.js' });
vm.runInContext(registrySource, context, { filename: 'shared/js/experiment-registry.js' });

const registry = context.window.AstraExperimentRegistry;
assert.ok(registry, 'experiment registry must be attached before ModuleSelector starts');
assert.ok(Object.isFrozen(registry), 'public experiment registry API must be immutable');
const registryDescriptor = Object.getOwnPropertyDescriptor(context.window, 'AstraExperimentRegistry');
assert.equal(registryDescriptor.configurable, false, 'experiment registry binding must not be reconfigured');
assert.equal(registryDescriptor.writable, false, 'experiment registry binding must not be replaced');

const configIds = vm.runInContext(
    'Object.fromEntries(Object.entries(CONFIG.experiments).map(([subject, entries]) => [subject, entries.map(entry => entry.id)]))',
    context
);
const subjects = ['mathematics', 'physics', 'chemistry', 'algorithms', 'biology'];
const expectedCounts = {
    mathematics: 20,
    physics: 20,
    chemistry: 17,
    algorithms: 12,
    biology: 19
};
const definitions = Array.from(registry.entries());

assert.equal(definitions.length, 88);
assert.equal(new Set(definitions.map(entry => `${entry.subject}:${entry.id}`)).size, 88);
for (const subject of subjects) {
    const entries = Array.from(registry.entries(subject));
    assert.equal(entries.length, expectedCounts[subject], `${subject} count must remain stable`);
    assert.deepEqual(
        entries.map(entry => entry.id),
        Array.from(configIds[subject]),
        `${subject} runtime order must follow CONFIG.experiments`
    );
}

const domModules = Array.from(html.matchAll(/data-module="([a-z0-9-]+)"/g), match => match[1]);
assert.equal(domModules.length, 90, 'DOM keeps three searching sections and one section for every other experiment');
assert.equal(new Set(domModules).size, 88);
assert.equal(domModules.filter(id => id === 'searching').length, 3);
assert.deepEqual(
    [...new Set(definitions.map(entry => entry.id))].sort(),
    [...new Set(domModules)].sort(),
    'registry and DOM experiment identities must be a bijection'
);

for (const definition of definitions) {
    assert.ok(Object.isFrozen(definition));
    assert.ok(Object.isFrozen(definition.init));
    assert.ok(Object.isFrozen(definition.cleanup));
    assert.ok(Object.isFrozen(definition.cleanup.owners));
    const scriptPath = definition.script.split('?')[0];
    assert.ok(fs.existsSync(path.join(root, scriptPath)), `${definition.id} script must exist: ${scriptPath}`);
    assert.equal(definition.cleanup.verified, false, `${definition.id} cleanup must not be overstated as verified`);
}

const initModeCounts = definitions.reduce((counts, entry) => {
    counts[entry.init.mode] = (counts[entry.init.mode] || 0) + 1;
    return counts;
}, {});
assert.deepEqual(initModeCounts, { 'global-hook': 87, 'legacy-bypass': 1 });
const sorting = registry.get('algorithms', 'sorting');
assert.equal(sorting.init.hook, 'initAlgorithms');
assert.equal(sorting.init.invoke, false);
assert.equal(registry.init('algorithms', 'sorting'), true);

context.window.initFunctionGraph = () => { context.initCalls = (context.initCalls || 0) + 1; };
assert.equal(registry.init('mathematics', 'function-graph'), true);
assert.equal(context.initCalls, 1);
assert.equal(registry.init('mathematics', 'unknown'), false);

const cleanupStateCounts = definitions.reduce((counts, entry) => {
    counts[entry.cleanup.state] = (counts[entry.cleanup.state] || 0) + 1;
    return counts;
}, {});
assert.deepEqual(cleanupStateCounts, {
    'legacy-callback': 65,
    'candidate-unwired': 21,
    missing: 2
});

const expectedCandidates = [
    'algorithms:bst-avl',
    'algorithms:greedy-scheduling',
    'algorithms:hash-tables',
    'algorithms:mst-compare',
    'biology:dna',
    'biology:enzyme-properties',
    'biology:gene-engineering',
    'biology:genetics',
    'biology:homeostasis',
    'biology:humoral-regulation',
    'biology:material-cycles',
    'biology:photosynthesis',
    'biology:population-community',
    'chemistry:crystal-structures',
    'chemistry:experiments',
    'chemistry:hybrid-orbitals',
    'mathematics:modeling-numerical',
    'physics:atomic-physics',
    'physics:gas-laws',
    'physics:mechanics',
    'physics:thermodynamics'
];
assert.deepEqual(
    definitions
        .filter(entry => entry.cleanup.state === 'candidate-unwired')
        .map(entry => `${entry.subject}:${entry.id}`)
        .sort(),
    expectedCandidates
);
assert.deepEqual(
    definitions
        .filter(entry => entry.cleanup.state === 'missing')
        .map(entry => `${entry.subject}:${entry.id}`)
        .sort(),
    ['algorithms:sorting', 'biology:cell-structure']
);
definitions
    .filter(entry => entry.cleanup.state !== 'legacy-callback')
    .forEach(entry => assert.equal(entry.cleanup.run, null, `${entry.id} must not carry a fake cleanup`));

const searching = registry.get('algorithms', 'searching');
assert.equal(searching.cleanup.kind, 'composite');
assert.deepEqual(Array.from(searching.cleanup.owners), ['SearchComparison', 'TreeTraversal', 'HashSearch']);
assert.equal(typeof searching.cleanup.run, 'function');
assert.equal(registry.get('mathematics', 'function-graph').cleanup.kind, 'function');

context.destroyFunctionGraph = () => { context.destroyCalls = (context.destroyCalls || 0) + 1; };
vm.runInContext(
    'const Calculus = { destroy() { globalThis.calculusDestroyCalls = (globalThis.calculusDestroyCalls || 0) + 1; } };',
    context
);
const cleanupReport = registry.cleanupPage('mathematics');
assert.equal(cleanupReport.attempted, 19);
assert.equal(cleanupReport.executed, 2);
assert.equal(cleanupReport.failed, 0);
assert.equal(context.destroyCalls, 1);
assert.equal(context.calculusDestroyCalls, 1, 'cleanup closure must resolve a later global lexical binding');

assert.doesNotMatch(registrySource, /destroyPhysics|Biology\.destroy/);
assert.doesNotMatch(moduleSelector, /\b_moduleScripts\s*:|\bconst initMap\s*=/);
assert.match(moduleSelector, /AstraExperimentRegistry\?\.scriptFor\(page, moduleId\)/);
assert.match(moduleSelector, /AstraExperimentRegistry\?\.init\(page, moduleId\)/);
assert.match(moduleSelector, /leavePage\(page, options = \{\}\)/);
assert.match(moduleSelector, /AstraExperimentRegistry\?\.cleanupPage\(page\)/);
const leavePageStart = moduleSelector.indexOf('leavePage(page, options = {})');
const leavePageSource = moduleSelector.slice(
    leavePageStart,
    moduleSelector.indexOf('toggleSidebar(page)', leavePageStart)
);
assert.match(leavePageSource, /try \{[\s\S]*this\.closeModule\(page, options\)/);
assert.match(leavePageSource, /try \{[\s\S]*AstraExperimentRegistry\?\.cleanupPage\(page\)/);
assert.match(leavePageSource, /try \{ this\.resetPage\(page\); \} catch/);
const openModuleSource = moduleSelector.slice(
    moduleSelector.indexOf('openModule(page, moduleId)'),
    moduleSelector.indexOf('_hideModuleTools()')
);
const closeModuleSource = moduleSelector.slice(
    moduleSelector.indexOf('closeModule(page, options = {})'),
    moduleSelector.indexOf('leavePage(page, options = {})')
);
assert.doesNotMatch(openModuleSource, /cleanupPage|\.cleanup\.run/);
assert.doesNotMatch(closeModuleSource, /cleanupPage|\.cleanup\.run/);

const isolationContext = {
    window: {
        AstraExperimentRegistry: {
            cleanupPage: () => {
                isolationContext.cleanupCalls = (isolationContext.cleanupCalls || 0) + 1;
                return Object.freeze({ attempted: 1, executed: 1, failed: 0 });
            }
        }
    }
};
vm.createContext(isolationContext);
vm.runInContext(moduleSelector, isolationContext, { filename: 'shared/js/module-selector.js' });
const selector = vm.runInContext('ModuleSelector', isolationContext);
selector.activeModule.physics = 'energy-conservation';
selector.closeModule = () => { throw new Error('close failure probe'); };
selector._hideModuleTools = () => { isolationContext.hideCalls = (isolationContext.hideCalls || 0) + 1; };
selector.resetPage = () => { isolationContext.resetCalls = (isolationContext.resetCalls || 0) + 1; };
const isolatedLeaveReport = selector.leavePage('physics', { preserveHash: true });
assert.equal(isolationContext.hideCalls, 1, 'tool hiding must continue after closeModule fails');
assert.equal(isolationContext.cleanupCalls, 1, 'cleanup must continue after closeModule fails');
assert.equal(isolationContext.resetCalls, 1, 'state reset must continue after closeModule fails');
assert.equal(isolatedLeaveReport.executed, 1);

assert.doesNotMatch(router, /\bconst destroyMap\s*=/);
assert.match(router, /ModuleSelector\.leavePage\(page, \{ preserveHash: true \}\)/);
assert.match(html, /config\.js[\s\S]*experiment-registry\.js[\s\S]*page-registry\.js[\s\S]*router\.js[\s\S]*main\.js/);
assert.match(main, /experiment-registry\.js\?v=20260715v7416ExperimentRegistryP1/);
assert.match(main, /module-selector\.js\?v=20260715v7416ExperimentRegistryP1/);
assert.match(serviceWorker, /experiment-registry\.js\?v=20260715v7416ExperimentRegistryP1/);
assert.match(serviceWorker, /astra-static-v20260715v7416ExperimentRegistryP1/);

console.log('experiment-registry-contract: ok');

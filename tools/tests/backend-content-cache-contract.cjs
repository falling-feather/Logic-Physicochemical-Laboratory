const assert = require('node:assert/strict');
const path = require('node:path');

const scriptPath = path.resolve(__dirname, '../../shared/js/backend-content.js');
const apiClientPath = path.resolve(__dirname, '../../shared/js/api-client.js');

async function main() {
    global.window = global;
    global.location = {
        origin: 'https://astra.test',
        search: '?backendSchema=1'
    };
    global.CONFIG = { backend: { apiBaseUrl: 'https://astra.test' } };
    global.localStorage = {
        values: new Map(),
        getItem(key) { return this.values.has(key) ? this.values.get(key) : null; },
        setItem(key, value) { this.values.set(key, String(value)); }
    };
    global.addEventListener = () => {};
    global.removeEventListener = () => {};

    let callCount = 0;
    let mode = 'success';
    delete require.cache[apiClientPath];
    const apiClient = require(apiClientPath);
    global.AstraApiClient = Object.assign({}, apiClient, {
        request(pathname) {
            callCount += 1;
            if (mode === 'failure') return Promise.reject(new Error('offline'));
            return new Promise((resolve) => setTimeout(() => resolve({ layout: 'experiment-page', pathname, callCount }), 5));
        }
    });

    delete require.cache[scriptPath];
    require(scriptPath);
    const content = global.BackendContent;
    assert.ok(content);

    const first = content.fetchPageSchema('physics/energy-conservation');
    const concurrent = content.fetchPageSchema('physics/energy-conservation');
    assert.equal(first, concurrent, 'concurrent reads must share only the in-flight promise');
    const firstValue = await first;
    assert.equal(firstValue.callCount, 1);
    assert.equal(content._schemaRequests.size, 0, 'settled success must not remain cached');

    const secondValue = await content.fetchPageSchema('physics/energy-conservation');
    assert.equal(secondValue.callCount, 2, 'reopening must perform a fresh authoritative read');

    mode = 'failure';
    await assert.rejects(() => content.fetchPageSchema('physics/energy-conservation'), /offline/);
    assert.equal(content._schemaRequests.size, 0, 'failed reads must not poison future reads');

    mode = 'success';
    const recovered = await content.fetchPageSchema('physics/energy-conservation');
    assert.equal(recovered.callCount, 4, 'online recovery must issue a new request');

    assert.equal(
        content._absoluteApiUrl('/api/render/script-sandboxes/sm_test/page/physics/energy-conservation'),
        'https://astra.test/api/render/script-sandboxes/sm_test/page/physics/energy-conservation'
    );
    assert.equal(content._absoluteApiUrl('javascript:alert(1)'), '');
    assert.equal(content._absoluteApiUrl('https://evil.example/api/render/script-sandboxes/sm_test/page/demo'), '');
    assert.equal(content._absoluteApiUrl('/api/users/me'), '');

    const classes = new Set();
    const sourceWindow = {};
    const status = { textContent: '' };
    const message = { textContent: '' };
    let removedSrc = 0;
    let parentDestroyCount = 0;
    let parentInitCount = 0;
    global.EnergyConservation = { destroy() { parentDestroyCount += 1; } };
    global.initEnergyConservation = () => { parentInitCount += 1; };
    const controller = {
        target: {
            classList: {
                add(value) { classes.add(value); },
                remove(value) { classes.delete(value); },
                contains(value) { return classes.has(value); }
            }
        },
        shell: {
            dataset: {},
            querySelector(selector) {
                return selector === '[data-backend-sandbox-status]' ? status : message;
            }
        },
        iframe: {
            contentWindow: sourceWindow,
            style: {},
            removeAttribute(name) { if (name === 'src') removedSrc += 1; }
        },
        sandboxId: 'sm_test',
        moduleId: 'energy-conservation',
        expectedSource: 'astra-content-script-sandbox',
        expectedProtocolVersion: 'astra-script-sandbox-bootstrap-v1',
        expectedDocumentContractVersion: 'astra-script-sandbox-document-v1',
        expectedTemplateId: 'physics-energy-conservation-v1',
        state: 'assets',
        destroyed: false,
        terminal: false,
        staticRuntimeSuspended: false,
        timeoutId: null
    };
    const metadata = {
        sandboxId: 'sm_test',
        protocolVersion: 'astra-script-sandbox-bootstrap-v1',
        documentContractVersion: 'astra-script-sandbox-document-v1',
        templateId: 'physics-energy-conservation-v1'
    };
    content._handleSandboxMessage(controller, {
        source: sourceWindow,
        origin: 'null',
        data: { source: 'astra-content-script-sandbox', type: 'ready', metadata, payload: {} }
    });
    assert.equal(controller.state, 'ready');
    assert.equal(parentDestroyCount, 1);
    assert.equal(classes.has('backend-sandbox-runtime-active'), true);

    content._handleSandboxMessage(controller, {
        source: sourceWindow,
        origin: 'null',
        data: {
            source: 'astra-content-script-sandbox',
            type: 'error',
            metadata,
            payload: { code: 'content_script_sandbox_bootstrap_failed' }
        }
    });
    assert.equal(controller.terminal, true);
    assert.equal(controller.state, 'error');
    assert.equal(parentInitCount, 1, 'terminal failure must restore the static runtime once');
    assert.equal(classes.has('backend-sandbox-runtime-active'), false);
    assert.equal(removedSrc, 1, 'terminal failure must unload the iframe');

    content._handleSandboxMessage(controller, {
        source: sourceWindow,
        origin: 'null',
        data: { source: 'astra-content-script-sandbox', type: 'ready', metadata, payload: {} }
    });
    assert.equal(parentDestroyCount, 1, 'late ready must not reactivate a terminal sandbox');

    const closeTarget = {
        classList: {
            add(value) { classes.add(value); },
            remove(value) { classes.delete(value); },
            contains(value) { return classes.has(value); }
        }
    };
    const closeController = {
        target: closeTarget,
        shell: { remove() {} },
        iframe: {
            removeAttribute() {},
            removeEventListener() {}
        },
        moduleId: 'energy-conservation',
        destroyed: false,
        staticRuntimeSuspended: true,
        timeoutId: null,
        onMessage: null,
        onLoad: null,
        onError: null
    };
    classes.add('backend-sandbox-runtime-active');
    content._sandboxControllers.set(closeTarget, closeController);
    content._activeSandboxControllers.add(closeController);
    content._destroyScriptSandbox(closeTarget, { restoreStatic: false });
    assert.equal(parentInitCount, 1, 'ordinary route destroy must not restart the static runtime');
    assert.equal(classes.has('backend-sandbox-runtime-active'), false, 'ordinary destroy must reveal the static DOM without starting it');
    assert.equal(content._activeSandboxControllers.has(closeController), false, 'ordinary destroy must release the sandbox controller');

    process.stdout.write('backend-content-cache-contract: ok\n');
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});

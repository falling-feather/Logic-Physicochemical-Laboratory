const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const source = fs.readFileSync(path.resolve(__dirname, '../../sw.js'), 'utf8');

async function main() {
    const handlers = {};
    const cachedPuts = [];
    let fetchCalls = 0;
    const cache = {
        async addAll() {},
        async put(request) { cachedPuts.push(request.url || String(request)); },
        async match() { return null; }
    };
    const context = {
        URL,
        Request,
        Response,
        Promise,
        console,
        setTimeout,
        clearTimeout,
        caches: {
            async open() { return cache; },
            async keys() { return []; },
            async delete() { return true; },
            async match() { return null; }
        },
        fetch: async () => {
            fetchCalls += 1;
            return new Response('ok', { status: 200 });
        },
        self: {
            location: { origin: 'https://astra.test' },
            clients: { async claim() {} },
            async skipWaiting() {},
            addEventListener(type, handler) { handlers[type] = handler; }
        }
    };
    vm.runInNewContext(source, context, { filename: 'sw.js' });
    assert.equal(typeof handlers.fetch, 'function');

    for (const request of [
        { method: 'GET', mode: 'cors', url: 'https://astra.test/api/health' },
        { method: 'GET', mode: 'navigate', url: 'https://astra.test/api/render/page/demo' },
        { method: 'GET', mode: 'cors', url: 'https://astra.test/api/render/script.js' }
    ]) {
        let responded = false;
        handlers.fetch({
            request,
            respondWith() { responded = true; }
        });
        assert.equal(responded, false, `${request.url} must bypass service-worker cache handling`);
    }
    assert.equal(fetchCalls, 0);
    assert.deepEqual(cachedPuts, []);

    let staticPromise = null;
    handlers.fetch({
        request: { method: 'GET', mode: 'cors', url: 'https://astra.test/pages/apiary/app.js' },
        respondWith(value) { staticPromise = value; }
    });
    assert.ok(staticPromise, '/pages/apiary must not be mistaken for /api');
    await staticPromise;
    assert.equal(fetchCalls, 1);
    assert.deepEqual(cachedPuts, ['https://astra.test/pages/apiary/app.js']);

    let navigationPromise = null;
    handlers.fetch({
        request: { method: 'GET', mode: 'navigate', url: 'https://astra.test/' },
        respondWith(value) { navigationPromise = value; }
    });
    assert.ok(navigationPromise, 'normal SPA navigation should keep network-first shell behavior');
    await navigationPromise;
    assert.equal(fetchCalls, 2);
    assert.deepEqual(cachedPuts, [
        'https://astra.test/pages/apiary/app.js',
        'https://astra.test/'
    ]);

    process.stdout.write('service-worker-cache-boundary: ok\n');
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});

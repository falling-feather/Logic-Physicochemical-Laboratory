const assert = require('node:assert/strict');
const path = require('node:path');

const clientPath = path.resolve(__dirname, '../../shared/js/api-client.js');

function memoryStorage(initial = {}) {
    const values = new Map(Object.entries(initial));
    return {
        getItem(key) { return values.has(key) ? values.get(key) : null; },
        setItem(key, value) { values.set(key, String(value)); },
        removeItem(key) { values.delete(key); },
        snapshot() { return Object.fromEntries(values); }
    };
}

function response(status, payload, headers = {}) {
    return new Response(payload === null ? null : JSON.stringify(payload), {
        status,
        headers: { 'Content-Type': 'application/json', ...headers }
    });
}

async function main() {
    global.window = global;
    global.location = { origin: 'https://astra.test' };
    global.CONFIG = { backend: { apiBaseUrl: 'https://api.astra.test' } };
    global.navigator = { onLine: true };
    global.localStorage = memoryStorage({
        'astra-access-token': 'legacy-local-token',
        'safe-setting': 'keep'
    });
    global.sessionStorage = memoryStorage({
        'auth_token': 'legacy-session-token',
        'safe-session': 'keep'
    });

    delete require.cache[clientPath];
    const client = require(clientPath);

    assert.equal(client.normalizeBaseUrl('https://evil.example'), '');
    assert.equal(client.normalizeBaseUrl('https://api.astra.test/'), 'https://api.astra.test');
    assert.equal(client.normalizeBaseUrl('http://api.astra.test/'), '', 'HTTPS pages must reject API downgrade');
    assert.equal(client.normalizeBaseUrl('https://api.astra.test/api'), '', 'API base must be an origin, not a path prefix');
    assert.equal(client.normalizeBaseUrl('https://user@api.astra.test'), '', 'API base must reject userinfo');
    assert.equal(client.normalizeBaseUrl('https://api.astra.test?tenant=1'), '', 'API base must reject query strings');
    assert.throws(
        () => client.buildUrl('/api/users/me', 'https://evil.example'),
        (error) => error.code === 'invalid_api_origin'
    );
    assert.throws(
        () => client.buildUrl('https://evil.example/api/demo'),
        (error) => error.code === 'invalid_api_origin'
    );

    assert.deepEqual(global.localStorage.snapshot(), { 'safe-setting': 'keep' }, 'module load must scrub legacy local tokens globally');
    assert.deepEqual(global.sessionStorage.snapshot(), { 'safe-session': 'keep' }, 'module load must scrub legacy session tokens globally');

    global.localStorage.setItem('access_token', 'late-local-token');
    global.sessionStorage.setItem('astra-access-token', 'late-session-token');
    const removed = client.scrubLegacyTokens();
    assert.deepEqual(removed.sort(), [
        'localStorage:access_token',
        'sessionStorage:astra-access-token'
    ]);
    assert.deepEqual(global.localStorage.snapshot(), { 'safe-setting': 'keep' });
    assert.deepEqual(global.sessionStorage.snapshot(), { 'safe-session': 'keep' });
    assert.deepEqual(client.scrubLegacyTokens(), [], 'global startup and page init scrubs must remain idempotent');

    const calls = [];
    global.fetch = async (url, options) => {
        calls.push({ url: String(url), options });
        return response(200, { ok: true }, { 'X-Request-ID': 'request-from-server' });
    };
    const value = await client.request('/api/demo', {
        baseUrl: 'https://api.astra.test/',
        params: { class_id: 7, empty: '' },
        headers: { Authorization: 'Bearer must-be-removed' }
    });
    assert.deepEqual(value, { ok: true });
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, 'https://api.astra.test/api/demo?class_id=7');
    assert.equal(calls[0].options.cache, 'no-store');
    assert.equal(calls[0].options.credentials, 'include');
    assert.equal(calls[0].options.redirect, 'follow');
    assert.equal(calls[0].options.headers.has('Authorization'), false);
    assert.equal(client.extractDetail({ detail: { code: 'template_missing', message: '模板缺失' } }), '模板缺失');

    let localFailureFetches = 0;
    global.fetch = async () => {
        localFailureFetches += 1;
        return response(200, { ok: true });
    };
    const circular = {};
    circular.self = circular;
    await assert.rejects(
        () => client.request('/api/demo', { method: 'POST', body: circular }),
        (error) => error.code === 'invalid_request' && error.ambiguous === false
    );
    const preAborted = new AbortController();
    preAborted.abort();
    await assert.rejects(
        () => client.request('/api/demo', { method: 'POST', body: {}, signal: preAborted.signal }),
        (error) => error.code === 'cancelled' && error.ambiguous === false
    );
    assert.equal(localFailureFetches, 0, 'local failures and pre-abort must not call fetch');

    let mutationCalls = 0;
    global.fetch = async () => {
        mutationCalls += 1;
        throw new TypeError('network down');
    };
    await assert.rejects(
        () => client.request('/api/demo', { method: 'POST', body: { value: 1 } }),
        (error) => error.code === 'network' && error.ambiguous === true && error.mutation === true
    );
    assert.equal(mutationCalls, 1, 'mutations must never be retried automatically');

    global.fetch = async (url, options) => {
        mutationCalls += 1;
        assert.equal(options.redirect, 'error');
        throw new TypeError('redirect or network failure');
    };
    await assert.rejects(
        () => client.request('/api/demo', { method: 'PATCH', body: { value: 2 } }),
        (error) => error.ambiguous === true && Boolean(error.requestId)
    );
    assert.equal(mutationCalls, 2, 'PATCH must be attempted exactly once');

    let timeoutCalls = 0;
    global.fetch = async (url, options) => {
        timeoutCalls += 1;
        return new Promise((resolve, reject) => {
            options.signal.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError')), { once: true });
        });
    };
    await assert.rejects(
        () => client.request('/api/demo', { method: 'POST', body: { value: 5 }, timeoutMs: 10 }),
        (error) => error.code === 'timeout' && error.ambiguous === true && Boolean(error.requestId)
    );
    assert.equal(timeoutCalls, 1, 'timed-out mutations must not be replayed');

    global.fetch = async () => ({
        ok: true,
        status: 200,
        statusText: 'OK',
        headers: new Headers({ 'X-Request-ID': 'confirmed-write' }),
        async text() { throw new TypeError('body stream interrupted'); }
    });
    await assert.rejects(
        () => client.request('/api/demo', { method: 'POST', body: { value: 3 } }),
        (error) => error.code === 'invalid_response' && error.confirmed === true && error.ambiguous === false
    );

    global.fetch = async () => ({
        ok: false,
        status: 409,
        statusText: 'Conflict',
        headers: new Headers(),
        async text() { throw new TypeError('body stream interrupted'); }
    });
    await assert.rejects(
        () => client.request('/api/demo', { method: 'POST', body: { value: 4 } }),
        (error) => error.status === 409 && error.ambiguous === false
    );

    global.fetch = async () => response(200, null);
    await assert.rejects(
        () => client.request('/api/demo'),
        (error) => error.code === 'invalid_response' && error.ambiguous === false
    );
    global.fetch = async () => response(204, null);
    assert.equal(await client.request('/api/demo'), null);

    global.fetch = async () => { throw new TypeError('network down'); };
    await assert.rejects(
        () => client.request('/api/demo'),
        (error) => error.code === 'network' && error.ambiguous === false
    );

    global.fetch = async () => response(401, { detail: 'raw auth detail' });
    await assert.rejects(
        () => client.request('/api/users/me'),
        (error) => error.status === 401 && client.message(error) === '登录状态已失效，请重新登录'
    );

    global.fetch = async () => response(503, { detail: 'database secret must not become product copy' });
    await assert.rejects(
        () => client.request('/api/health'),
        (error) => error.status === 503 && client.message(error) === '后端服务暂时不可用，请稍后重试'
    );

    let offlineFetchCalled = false;
    global.navigator.onLine = false;
    global.fetch = async () => {
        offlineFetchCalled = true;
        return response(200, {});
    };
    await assert.rejects(
        () => client.request('/api/demo'),
        (error) => error.code === 'offline' && error.ambiguous === false
    );
    assert.equal(offlineFetchCalled, false, 'offline requests must not read a cache or call fetch');

    process.stdout.write('api-client-contract: ok\n');
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});

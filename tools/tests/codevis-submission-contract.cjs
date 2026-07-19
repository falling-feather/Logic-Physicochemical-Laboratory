const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const adapterPath = path.join(root, 'codevis/shared/js/submission-adapter.js');
const challengePath = path.join(root, 'codevis/pages/course-challenge/course-challenge.js');
const indexPath = path.join(root, 'codevis/index.html');
const activity = {
    galaxy_key: 'code-space',
    course_key: 'control-flow',
    activity_key: 'control-flow.loop-boundary',
    language: 'javascript'
};

function createHarness() {
    const calls = [];
    const context = {
        console,
        AbortController,
        window: null,
        CvCourseStateAdapter: { resolve: () => ({ status: 'available' }) },
        AstraCodeSpaceStudentContext: {
            resolve: () => ({ authenticated: true, role: 'student', class_id: 7, course_id: 19 })
        },
        AstraApiClient: {
            request: async (url, options) => {
                calls.push({ url, options });
                if (options.method === 'GET') {
                    return {
                        id: 23,
                        course_id: 19,
                        activity_key: activity.activity_key,
                        effective_release_state: 'open',
                        active_version: { id: 31, language_allowlist: ['javascript'] }
                    };
                }
                return {
                    id: 47,
                    problem_id: 23,
                    course_id: 19,
                    class_id: 7,
                    activity_key: activity.activity_key,
                    language: 'javascript',
                    status: 'runner_unavailable',
                    result_summary: { runner_state: 'runner_disabled' },
                    idempotent_replay: false
                };
            },
            isAmbiguousMutation: (error) => Boolean(error && error.ambiguous && error.mutation !== false),
            isCancelled: (error) => Boolean(error && error.code === 'cancelled')
        }
    };
    context.window = context;
    vm.createContext(context);
    vm.runInContext(fs.readFileSync(adapterPath, 'utf8'), context, { filename: adapterPath });
    return { context, calls, adapter: context.CvSubmissionAdapter };
}

async function main() {
    const source = fs.readFileSync(adapterPath, 'utf8');
    const challengeSource = fs.readFileSync(challengePath, 'utf8');
    const index = fs.readFileSync(indexPath, 'utf8');
    assert.match(source, /AstraCodeSpaceStudentContext\.resolve/, 'host student scope must be explicit and injectable');
    assert.match(source, /\/api\/code-problems\/by-activity/, 'formal submission must discover problems by stable activity key');
    assert.match(source, /\/api\/code-problems\/['"] \+ encodeURIComponent/, 'submission URL must use the authoritative problem id');
    assert.match(source, /dispatchAuthRequired: false/, 'Code Space must not recreate the app-shell authentication flow');
    assert.match(challengeSource, /id="challenge-submit"/, 'challenge UI must expose a real formal submission control');
    assert.match(challengeSource, /state\.available\).*正式提交服务已连接/, 'available service must not be described as unavailable');
    assert.match(challengeSource, /仅用于学习反馈，不是正式判题/, 'browser preview must remain visibly non-authoritative');
    assert.doesNotMatch(challengeSource, /AstraSubmissionAdapter/, 'obsolete placeholder adapter must not control submission UI');
    assert.ok(index.indexOf('../shared/js/api-client.js') < index.indexOf('shared/js/submission-adapter.js'), 'reuse the shared cookie-only API client before the adapter');

    const { context, calls, adapter } = createHarness();
    const result = await adapter.submit(activity, 'print(1)');
    assert.deepEqual(JSON.parse(JSON.stringify(result)), {
        ok: true,
        status: 'runner_unavailable',
        reason: '权威状态：判题器暂不可用，尚未判定通过。',
        submission_id: 47,
        idempotent_replay: false
    });
    assert.equal(calls.length, 2);
    assert.deepEqual(JSON.parse(JSON.stringify(calls[0])), {
        url: '/api/code-problems/by-activity',
        options: {
            method: 'GET',
            params: { course_id: 19, activity_key: activity.activity_key, class_id: 7 },
            dispatchAuthRequired: false
        }
    });
    assert.deepEqual(JSON.parse(JSON.stringify(calls[1])), {
        url: '/api/code-problems/23/submissions',
        options: {
            method: 'POST',
            body: { class_id: 7, language: 'javascript', source_code: 'print(1)', stdin: '' },
            dispatchAuthRequired: false
        }
    });

    context.AstraApiClient.request = async (url, options) => {
        calls.push({ url, options });
        if (options.method === 'GET') {
            return {
                id: 23, course_id: 19, activity_key: activity.activity_key,
                effective_release_state: 'open', active_version: { id: 31, language_allowlist: ['javascript'] }
            };
        }
        return {
            id: 48, problem_id: 23, course_id: 19, class_id: 7, activity_key: activity.activity_key,
            language: 'javascript', status: 'accepted', result_summary: {}, idempotent_replay: true
        };
    };
    const accepted = await adapter.submit(activity, 'print(2)');
    assert.equal(accepted.status, 'accepted');
    assert.equal(accepted.reason, '权威状态：通过。');
    assert.equal(accepted.idempotent_replay, true);

    const unavailable = createHarness();
    delete unavailable.context.AstraCodeSpaceStudentContext;
    const noContext = await unavailable.adapter.submit(activity, 'print(1)');
    assert.equal(noContext.ok, false);
    assert.equal(noContext.code, 'context_unavailable');
    assert.equal(unavailable.calls.length, 0, 'absent student context must fail closed before discovery');

    const missingScope = createHarness();
    missingScope.context.AstraCodeSpaceStudentContext.resolve = () => ({ authenticated: true, role: 'student', class_id: 7 });
    const scopeResult = await missingScope.adapter.submit(activity, 'print(1)');
    assert.equal(scopeResult.code, 'scope_unavailable');
    assert.equal(missingScope.calls.length, 0, 'missing course mapping must fail closed before discovery');

    const locked = createHarness();
    locked.context.CvCourseStateAdapter.resolve = () => ({ status: 'locked' });
    const lockedResult = await locked.adapter.submit(activity, 'print(1)');
    assert.equal(lockedResult.code, 'course_state_closed');
    assert.equal(locked.calls.length, 0, 'locked activities must never submit');

    const hidden = createHarness();
    hidden.context.CvCourseStateAdapter.resolve = () => ({ status: 'hidden' });
    const hiddenStateResult = await hidden.adapter.submit(activity, 'print(1)');
    assert.equal(hiddenStateResult.code, 'course_state_closed');
    assert.equal(hidden.calls.length, 0, 'hidden activities must never submit');

    const hiddenLookup = createHarness();
    hiddenLookup.context.AstraApiClient.request = async (url, options) => {
        hiddenLookup.calls.push({ url, options });
        return {
            id: 23, course_id: 19, activity_key: activity.activity_key,
            effective_release_state: 'locked', active_version: { id: 31, language_allowlist: ['javascript'] }
        };
    };
    const hiddenResult = await hiddenLookup.adapter.submit(activity, 'print(1)');
    assert.equal(hiddenResult.code, 'problem_unavailable');
    assert.equal(hiddenLookup.calls.length, 1, 'closed discovery payload must not proceed to POST');

    for (const [status, code] of [[401, 'unauthorized'], [403, 'forbidden'], [404, 'problem_unavailable'], [409, 'conflict'], [422, 'validation']]) {
        const failed = createHarness();
        failed.context.AstraApiClient.request = async (url, options) => {
            if (options.method === 'GET') {
                return {
                    id: 23, course_id: 19, activity_key: activity.activity_key,
                    effective_release_state: 'open', active_version: { id: 31, language_allowlist: ['javascript'] }
                };
            }
            throw { status };
        };
        const response = await failed.adapter.submit(activity, 'print(1)');
        assert.equal(response.ok, false);
        assert.equal(response.code, code, 'HTTP ' + status + ' must fail closed');
    }
    const network = createHarness();
    network.context.AstraApiClient.request = async () => { throw { code: 'network', ambiguous: true, mutation: true }; };
    const networkResult = await network.adapter.submit(activity, 'print(1)');
    assert.equal(networkResult.code, 'submission_unconfirmed');
    assert.equal(networkResult.ok, false);

    const empty = createHarness();
    const emptyResult = await empty.adapter.submit(activity, '   ');
    assert.equal(emptyResult.code, 'source_empty');
    assert.equal(empty.calls.length, 0, 'empty code must not create a submission');
    assert.equal(adapter.resultMessage('queued'), '权威状态：已进入判题队列。');
    assert.equal(adapter.resultMessage('accepted'), '权威状态：通过。');
    assert.equal(adapter.resultMessage('compile_error'), '权威状态：编译未通过。');

    process.stdout.write('codevis-submission-contract: ok\n');
}

main().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});

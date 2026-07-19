(function (global) {
    'use strict';

    const challenge = global.CvChallengeSession = global.CvChallengeSession || {
        drafts: Object.create(null), predictions: Object.create(null), submissions: Object.create(null),
        result: null, repairingKey: null, runGeneration: 0, submissionGeneration: 0, submissionAbort: null
    };
    challenge.drafts = challenge.drafts || Object.create(null);
    challenge.predictions = challenge.predictions || Object.create(null);
    challenge.submissions = challenge.submissions || Object.create(null);
    challenge.runGeneration = Number(challenge.runGeneration) || 0;
    challenge.submissionGeneration = Number(challenge.submissionGeneration) || 0;

    function esc(value) {
        return String(value == null ? '' : value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[char]);
    }

    function outputOf(result) {
        const steps = result && result.steps || [];
        const last = steps[steps.length - 1];
        return last && Array.isArray(last.stdout) ? last.stdout.join('\n').trim() : '';
    }

    function courseTitle(manifest, activity) {
        const course = manifest.courses.find(item => item.course_key === activity.course_key);
        return course ? course.title : '代码空间';
    }

    function traceView(result) {
        if (!result) return '<p class="challenge-empty">运行后会在这里显示变量、数组与输出的可观察轨迹。</p>';
        if (result.error) return '<p class="challenge-error">' + esc(result.error) + '</p>';
        const frames = result.steps.slice(0, 5);
        if (!frames.length) return '<p class="challenge-empty">运行完成，但这段代码没有产生可显示的轨迹。</p>';
        return '<ol class="trace-frames">' + frames.map((frame, index) => '<li><span>步骤 ' + (index + 1) + '</span><code>' + esc(JSON.stringify(frame.vars || {})) + '</code><small>' + esc((frame.stdout || []).join(' · ') || '继续观察') + '</small></li>').join('') + '</ol>';
    }

    function submissionState(activity) {
        const adapter = global.CvSubmissionAdapter;
        if (adapter && typeof adapter.availability === 'function') {
            try { return adapter.availability(activity); } catch (_) { /* fail closed below */ }
        }
        return { available: false, reason: '正式提交服务暂不可用。', code: 'adapter_unavailable' };
    }

    function learningGate() {
        const context = global.CvStudentContext;
        return context && typeof context.gate === 'function' ? context.gate() : { blocked: false };
    }

    function formalStatusClass(record) {
        if (!record) return '';
        if (record.pending) return 'is-warn';
        return record.ok && record.status === 'accepted' ? 'is-pass' : 'is-warn';
    }

    function formalStatusCopy(record, state) {
        if (record) return record.reason || '提交结果尚未确认。';
        if (state.available) return '正式提交服务已连接，提交后将在这里显示权威判题状态。';
        return state.reason || '正式提交暂不可用。';
    }

    function formalButtonCopy(record, state) {
        if (record && record.pending) return '正在提交…';
        return state.available ? '正式提交代码' : '暂不能正式提交';
    }

    function render() {
        const root = document.getElementById('course-challenge-root');
        const manifest = global.CvCourseManifest;
        if (!root) return;
        const gate = learningGate();
        if (gate.blocked) {
            root.innerHTML = '<div class="challenge-shell course-context-gate" role="status" aria-live="polite"><p class="course-eyebrow">代码空间</p><h1>' + esc(gate.title || '课程暂不可用') + '</h1><p class="course-lede">' + esc(gate.message || '请稍后重试。') + '</p></div>';
            return;
        }
        const routeKey = global.CvRouter && global.CvRouter.currentParams && global.CvRouter.currentParams.get('activity');
        const activity = manifest && manifest.getActivity(routeKey || (global.CvCourseSession || {}).activityKey || manifest.defaultActivityKey);
        if (!activity) {
            root.replaceChildren();
            global.CvRouter.navigateTo('catalog');
            return;
        }
        global.CvCourseSession.activityKey = activity.activity_key;
        global.CvCourseSession.courseKey = activity.course_key;
        const state = global.CvCourseStateAdapter.resolve(activity);
        if (state.status === 'hidden' || state.status === 'locked' || state.status === 'unavailable') {
            if (state.status === 'hidden') root.replaceChildren();
            global.CvRouter.navigateTo('lesson', { activity: activity.activity_key });
            return;
        }
        const template = manifest.getTemplate(activity);
        const draft = challenge.drafts[activity.activity_key] || template.starter_code;
        const prediction = challenge.predictions[activity.activity_key] || '';
        const result = challenge.result && challenge.result.activity_key === activity.activity_key ? challenge.result.value : null;
        const precheck = result && !result.error && outputOf(result) === template.expected_output;
        const submitState = submissionState(activity);
        const submission = challenge.submissions[activity.activity_key] || null;
        const repairing = challenge.repairingKey === activity.activity_key;
        const observation = !result ? '' : '<section class="challenge-compare"><div><span>你的预测</span><p>' + esc(prediction || '尚未写下预测') + '</p></div><div><span>观察结果</span><p>' + esc(result.error ? result.error : (outputOf(result) || '已完成运行，继续查看轨迹。')) + '</p></div><div><span>修正线索</span><p>' + esc(template.repair_hint) + '</p></div></section>';
        const formalDisabled = !submitState.available || (submission && submission.pending);
        root.innerHTML = '<div class="challenge-shell">' +
            '<a class="lesson-back" href="#lesson?activity=' + encodeURIComponent(activity.activity_key) + '">← 返回子课程</a>' +
            '<header class="challenge-heading"><p class="course-eyebrow">' + esc(courseTitle(manifest, activity)) + ' / 可执行挑战</p><h1>挑战：' + esc(activity.title) + '</h1><p>' + esc(activity.goal) + '</p></header>' +
            '<ol class="challenge-steps" aria-label="学习步骤"><li class="' + (prediction ? 'is-done' : 'is-current') + '"><b>1</b>预测</li><li class="' + (result ? 'is-done' : (!prediction ? '' : 'is-current')) + '"><b>2</b>运行</li><li class="' + (result && !repairing ? 'is-current' : (repairing ? 'is-done' : '')) + '"><b>3</b>追踪</li><li class="' + (repairing ? 'is-current' : '') + '"><b>4</b>修正</li></ol>' +
            '<div class="challenge-layout"><section class="challenge-editor"><label for="challenge-prediction">你的预测</label><input id="challenge-prediction" maxlength="180" value="' + esc(prediction) + '" placeholder="先写下你的判断，不会作为正式记录保存。" /><label for="challenge-code">可编辑代码</label><textarea id="challenge-code" spellcheck="false" aria-label="可编辑代码">' + esc(draft) + '</textarea><p class="challenge-public">' + esc(template.public_check) + '</p><p class="challenge-repair-hint">修正线索：' + esc(template.repair_hint) + '</p><button class="cv-btn cv-btn--primary" type="button" id="challenge-run">运行并追踪</button></section>' +
            '<section class="challenge-trace" aria-live="polite"><div class="challenge-panel-title">运行 / 追踪</div>' + traceView(result) + '<button class="cv-btn" type="button" id="challenge-repair">修改后再次运行</button></section></div>' +
            observation +
            '<section class="challenge-checks"><div><p>浏览器预检</p><strong class="' + (result ? (precheck ? 'is-pass' : 'is-warn') : '') + '">' + (result ? (precheck ? '样例通过 · 仅用于学习反馈，不是正式判题' : '样例尚未通过 · 仅用于学习反馈，不是正式判题') : '请先运行公开样例 · 仅用于学习反馈，不是正式判题') + '</strong></div><div><p>正式提交</p><strong id="challenge-submission-status" class="' + formalStatusClass(submission) + '" aria-live="polite">' + esc(formalStatusCopy(submission, submitState)) + '</strong><button class="cv-btn" type="button" id="challenge-submit"' + (formalDisabled ? ' disabled aria-disabled="true"' : '') + '>' + formalButtonCopy(submission, submitState) + '</button></div></section>' +
            '</div>';

        const code = root.querySelector('#challenge-code');
        const predictionInput = root.querySelector('#challenge-prediction');
        const run = async () => {
            challenge.drafts[activity.activity_key] = code.value;
            challenge.predictions[activity.activity_key] = predictionInput.value;
            const runGeneration = ++challenge.runGeneration;
            const button = root.querySelector('#challenge-run');
            button.disabled = true;
            button.textContent = '正在运行…';
            const value = await global.CvRuntime.trace({ language: template.language, code: code.value, maxSteps: 500 });
            if (runGeneration !== challenge.runGeneration) return;
            challenge.result = { activity_key: activity.activity_key, value };
            challenge.repairingKey = null;
            render();
        };
        const formalSubmit = async () => {
            const adapter = global.CvSubmissionAdapter;
            if (!adapter || typeof adapter.submit !== 'function') return;
            const sourceCode = code.value;
            challenge.drafts[activity.activity_key] = sourceCode;
            challenge.predictions[activity.activity_key] = predictionInput.value;
            if (challenge.submissionAbort) challenge.submissionAbort.abort();
            const controller = new AbortController();
            challenge.submissionAbort = controller;
            const generation = ++challenge.submissionGeneration;
            challenge.submissions[activity.activity_key] = { pending: true, reason: '正在发送正式提交…' };
            render();
            let response;
            try {
                response = await adapter.submit(activity, sourceCode, { signal: controller.signal });
            } catch (_) {
                response = { ok: false, reason: '提交结果尚未确认，未显示为成功。请刷新后核对。', code: 'submission_unconfirmed' };
            }
            if (generation !== challenge.submissionGeneration) return;
            challenge.submissionAbort = null;
            challenge.submissions[activity.activity_key] = response;
            render();
        };
        root.querySelector('#challenge-run').addEventListener('click', run);
        const submitButton = root.querySelector('#challenge-submit');
        if (!submitButton.disabled) submitButton.addEventListener('click', formalSubmit);
        code.addEventListener('input', () => { challenge.drafts[activity.activity_key] = code.value; });
        predictionInput.addEventListener('input', () => { challenge.predictions[activity.activity_key] = predictionInput.value; });
        root.querySelector('#challenge-repair').addEventListener('click', () => {
            challenge.drafts[activity.activity_key] = code.value;
            challenge.predictions[activity.activity_key] = predictionInput.value;
            challenge.repairingKey = activity.activity_key;
            render();
            requestAnimationFrame(() => root.querySelector('#challenge-code').focus());
        });
        code.addEventListener('keydown', event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); run(); } });
    }

    global.CvCourseChallenge = {
        init: render,
        refresh: render,
        cancel() {
            challenge.runGeneration++;
            challenge.submissionGeneration++;
            if (challenge.submissionAbort) challenge.submissionAbort.abort();
            challenge.submissionAbort = null;
            global.CvRuntime && global.CvRuntime.cancel('cpp');
        }
    };
})(window);

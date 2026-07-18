/* Future Galaxy course manifest: the single client-side bridge for BE-004. */
(function attachFutureGalaxyManifest(global) {
    'use strict';

    const GALAXY_KEY = 'future-galaxy';
    const course = (course_key, page, title, eyebrow, question, objective, visual, activities) => Object.freeze({
        galaxy_key: GALAXY_KEY,
        course_key,
        page,
        title,
        eyebrow,
        question,
        objective,
        visual,
        activities: Object.freeze(activities.map((activity) => Object.freeze({
            galaxy_key: GALAXY_KEY,
            course_key,
            ...activity,
            route_slug: activity.route_slug || String(activity.activity_key || '').split('.').slice(1).join('.')
        })))
    });

    const courses = Object.freeze([
        course('earth-space', 'cosmos', '地球与宇宙', 'ORBITAL FIELD', '太阳高度变化为什么会改变白昼与温度？', '用可调的日照角与轨道尺度，把预测、观察和判断连成一次可复查的推理。', 'orbit', [
            { activity_key: 'cosmos.day-season', title: '昼夜与季节', kind: 'canvas', input: '日照角', prompt: '先预测：北半球的受光面积会怎样变化？', observation: '观察昼夜分界线与受光带。', decision: '选择最能解释季节差异的结论。' },
            { activity_key: 'cosmos.orbital-scale', title: '轨道与尺度', kind: 'webgl', input: '轨道位置', prompt: '先预测：改变位置后，昼夜分界线与观察角会怎样移动？', observation: '观察可旋转的地球、轨道和日照方向。', decision: '判断位置变化与昼夜现象的关系。' },
            { activity_key: 'cosmos.evidence-log', title: '证据记录', kind: 'canvas', input: '观测时刻', prompt: '先预测：同一地点的阴影会向哪里移动？', observation: '观察光束与地表标记。', decision: '用一句因果解释提交判断。' }
        ]),
        course('engineering-systems', 'engineering', '工程应用', 'SYSTEMS STUDIO', '结构受力如何沿着构件传递？', '调节载荷位置，观察受力路径，判断哪个设计更能稳定传力。', 'bridge', [
            { activity_key: 'engineering.load-path', title: '受力路径', kind: 'canvas', input: '载荷位置', prompt: '先预测：把载荷移到跨中，哪几根杆会先变红？', observation: '观察桁架节点与受力强度。', decision: '选择更合理的加固位置。' },
            { activity_key: 'engineering.member-choice', title: '构件选择', kind: 'canvas', input: '杆件数量', prompt: '先预测：删去一根斜杆会影响哪条路径？', observation: '观察力的改道与支点反应。', decision: '解释三角单元为何常用于稳定结构。' },
            { activity_key: 'engineering.safety-check', title: '安全校核', kind: 'canvas', input: '安全系数', prompt: '先预测：提高安全系数后，允许载荷会怎样变化？', observation: '观察阈值线与载荷读数。', decision: '判断方案是否满足约束。' }
        ]),
        course('data-ai', 'datascience', '数据科学', 'MODEL BENCH', '一条拟合线何时能帮助解释数据？', '改变模型参数并查看误差，区分“贴近样本”和“可解释”的判断。', 'data', [
            { activity_key: 'datascience.model-fit', title: '模型拟合', kind: 'canvas', input: '斜率', prompt: '先预测：斜率变大时哪些点的误差会增加？', observation: '观察样本、拟合线与残差。', decision: '选择误差更小且方向合理的模型。' },
            { activity_key: 'datascience.outlier-test', title: '离群点检验', kind: 'canvas', input: '离群点权重', prompt: '先预测：一个远离样本的点会如何拉动拟合线？', observation: '观察模型随权重的偏移。', decision: '解释为什么需要标记异常值。' },
            { activity_key: 'datascience.evidence-claim', title: '证据与主张', kind: 'canvas', input: '观察窗口', prompt: '先预测：扩大观察窗口会带来什么不确定性？', observation: '观察数据范围与趋势。', decision: '选择最谨慎的结论表述。' }
        ]),
        course('information-technology', 'infotech', '信息技术', 'NETWORK TRACE', '一个请求如何穿过分层网络到达目的地？', '调节跳数和请求体，沿路径观察分层处理，再判断瓶颈所在。', 'network', [
            { activity_key: 'infotech.packet-route', title: '分组路由', kind: 'canvas', input: '跳数', prompt: '先预测：增加中继后，请求的到达时间会怎样变化？', observation: '观察数据包穿过节点与层。', decision: '判断哪一段最可能是瓶颈。' },
            { activity_key: 'infotech.layer-contract', title: '分层约定', kind: 'canvas', input: '消息长度', prompt: '先预测：更长的消息会影响哪一层的工作？', observation: '观察封装与传输标记。', decision: '解释分层为何能降低复杂度。' },
            { activity_key: 'infotech.fault-trace', title: '故障追踪', kind: 'canvas', input: '故障节点', prompt: '先预测：一个节点失效后，包会在哪里停下？', observation: '观察路径高亮与重试。', decision: '选择最先检查的网络层。' }
        ]),
        course('materials-science', 'materials', '材料微观', 'MATTER ATLAS', '微观晶粒与缺陷为什么会改变材料表现？', '调节晶粒尺度，观察边界密度与受力方向，再判断微结构方案。', 'materials', [
            { activity_key: 'materials.grain-boundary', title: '晶粒边界', kind: 'canvas', input: '晶粒尺度', prompt: '先预测：晶粒更细时，边界数量会怎样变化？', observation: '观察晶粒、边界与受力箭头。', decision: '判断哪种结构更可能阻碍位错。' },
            { activity_key: 'materials.defect-path', title: '缺陷路径', kind: 'canvas', input: '缺陷密度', prompt: '先预测：增加缺陷会让裂纹更容易向哪里延伸？', observation: '观察缺陷点与传播路径。', decision: '解释缺陷并非总是“看得见的洞”。' },
            { activity_key: 'materials.process-window', title: '工艺窗口', input: '冷却速率', kind: 'canvas', prompt: '先预测：冷却更快会如何影响组织尺度？', observation: '观察组织由粗到细的变化。', decision: '选择与目标性能匹配的工艺方向。' }
        ]),
        course('humanities-futures', 'humanities', '人文可视化', 'CONTEXT LAB', '一个文本或图像在什么语境中才有意义？', '调整叙事视角与连接强度，观察关系网络，并用证据解释一个判断。', 'humanities', [
            { activity_key: 'humanities.context-map', title: '语境地图', kind: 'canvas', input: '连接强度', prompt: '先预测：改变连接强度后，哪个主题会成为中心？', observation: '观察人物、事件与概念之间的连线。', decision: '选择最能由关系支持的解释。' },
            { activity_key: 'humanities.voice-shift', title: '视角切换', kind: 'canvas', input: '叙事视角', prompt: '先预测：切换叙事者后，哪些关系会被强调？', observation: '观察节点权重与色彩变化。', decision: '解释“观点”与“事实”如何共存。' },
            { activity_key: 'humanities.claim-review', title: '主张审阅', kind: 'canvas', input: '证据阈值', prompt: '先预测：提高证据阈值会留下哪些连接？', observation: '观察弱关联逐步淡出。', decision: '提交可追溯的解释。' }
        ])
    ]);

    const getCourse = (course_key) => courses.find((item) => item.course_key === course_key) || null;
    const getCourseByPage = (page) => courses.find((item) => item.page === page) || null;
    const getActivity = (course_key, activity_key) => {
        const item = getCourse(course_key);
        return item && item.activities.find((activity) => activity.activity_key === activity_key) || null;
    };

    const ACCESS_STATES = new Set(['open', 'locked', 'hidden']);
    const unavailableAccess = () => Object.freeze({ state: 'unavailable' });
    const allActivities = courses.flatMap((item) => item.activities);
    const sanitizeActivityAccess = (raw) => {
        const input = raw && typeof raw === 'object' ? raw : {};
        const output = {};
        allActivities.forEach((item) => {
            const candidate = input[item.activity_key];
            if (typeof candidate === 'string' && ACCESS_STATES.has(candidate)) {
                output[item.activity_key] = Object.freeze({ state: candidate });
                return;
            }
            if (candidate && typeof candidate === 'object' && ACCESS_STATES.has(candidate.state)) {
                const normalized = { state: candidate.state };
                // Progress is intentionally accepted only as explicit numeric state, never inferred.
                if (Number.isFinite(candidate.progress)) normalized.progress = Math.max(0, Math.min(1, Number(candidate.progress)));
                output[item.activity_key] = Object.freeze(normalized);
                return;
            }
            output[item.activity_key] = unavailableAccess();
        });
        return Object.freeze(output);
    };
    const deriveCourseAccess = (activity_access) => Object.freeze(courses.reduce((output, item) => {
        const states = item.activities.map((activity) => activity_access[activity.activity_key] || unavailableAccess()).map((access) => access.state);
        output[item.course_key] = Object.freeze({
            state: states.every((state) => state === 'hidden') ? 'hidden'
                : states.includes('open') ? 'open'
                    : states.every((state) => state === 'locked' || state === 'hidden') ? 'locked'
                        : 'unavailable'
        });
        return output;
    }, {}));

    // BE-004 returns only open/locked units. The adapter calls this once per course
    // after GET /api/courses/{course_id}/units?class_id={class_id}; a known manifest
    // activity absent from a valid response is hidden, and malformed/unknown rows fail closed.
    const adaptBe004Units = (course_key, units) => {
        const currentCourse = getCourse(course_key);
        if (!currentCourse || !Array.isArray(units)) return null;
        const expected = new Map(currentCourse.activities.map((activity) => [activity.activity_key, activity]));
        const output = Object.fromEntries(currentCourse.activities.map((activity) => [activity.activity_key, { state: 'hidden' }]));
        for (const unit of units) {
            if (!unit || typeof unit !== 'object' || !expected.has(unit.activity_key)
                || !('id' in unit) || typeof unit.title !== 'string' || !Number.isFinite(unit.position)
                || !Array.isArray(unit.lock_reasons) || !['open', 'locked'].includes(unit.effective_release_state)) return null;
            if (output[unit.activity_key].state !== 'hidden') return null;
            output[unit.activity_key] = { state: unit.effective_release_state };
        }
        return Object.freeze(output);
    };

    let httpConfig = null;
    let httpSnapshot = null;
    let httpRefresh = null;
    const unavailableSnapshot = (source) => Object.freeze({
        galaxy_key: GALAXY_KEY,
        source,
        availability: 'unavailable',
        teacher_plan: 'unavailable',
        course_access: deriveCourseAccess(sanitizeActivityAccess(null)),
        activity_access: sanitizeActivityAccess(null)
    });
    const isCourseIdMap = (value) => value && typeof value === 'object' && courses.every((item) => {
        const id = value[item.course_key];
        return typeof id === 'string' || Number.isFinite(id);
    });

    // This configures the BE-004 student-unit adapter but never performs a request in
    // resolveAvailability(). Consumers call refresh() during preload/refresh, then render
    // reads only the finished cached snapshot.
    const configureHttp = ({ course_ids, class_id, fetcher } = {}) => {
        if (!isCourseIdMap(course_ids) || !(typeof class_id === 'string' || Number.isFinite(class_id))
            || (fetcher !== undefined && typeof fetcher !== 'function')
            || (fetcher === undefined && typeof global.fetch !== 'function')) {
            httpConfig = null;
            httpSnapshot = unavailableSnapshot('http-config-unavailable');
            return false;
        }
        httpConfig = Object.freeze({
            course_ids: Object.freeze({ ...course_ids }),
            class_id: String(class_id),
            fetcher: fetcher || global.fetch.bind(global)
        });
        httpSnapshot = unavailableSnapshot('http-pending');
        return true;
    };
    const refresh = async () => {
        if (!httpConfig) return httpSnapshot || unavailableSnapshot('http-unconfigured');
        if (httpRefresh) return httpRefresh;
        httpRefresh = Promise.all(courses.map(async (item) => {
            const courseId = encodeURIComponent(String(httpConfig.course_ids[item.course_key]));
            const classId = encodeURIComponent(httpConfig.class_id);
            const response = await httpConfig.fetcher(`/api/courses/${courseId}/units?class_id=${classId}`, { credentials: 'same-origin' });
            if (!response || response.ok !== true || typeof response.json !== 'function') throw new Error('Invalid BE-004 units response');
            const access = adaptBe004Units(item.course_key, await response.json());
            if (!access) throw new Error('Invalid BE-004 unit fields');
            return access;
        })).then((perCourse) => {
            const activity_access = Object.freeze(Object.assign({}, ...perCourse));
            httpSnapshot = Object.freeze({
                galaxy_key: GALAXY_KEY,
                source: 'http-cache',
                availability: 'available',
                teacher_plan: 'unavailable',
                course_access: deriveCourseAccess(activity_access),
                activity_access
            });
            return httpSnapshot;
        }).catch(() => {
            httpSnapshot = unavailableSnapshot('http-unavailable');
            return httpSnapshot;
        }).finally(() => { httpRefresh = null; });
        return httpRefresh;
    };

    // BE-004 can provide a state adapter later. Only a wholly absent adapter means the
    // legacy local catalogue may default-open; every malformed adapter response fails closed.
    const resolveAvailability = () => {
        if (httpConfig || httpSnapshot) return httpSnapshot || unavailableSnapshot('http-pending');
        const adapter = global.AstraCourseStateAdapter;
        if (!adapter) {
            return Object.freeze({
                galaxy_key: GALAXY_KEY,
                source: 'legacy-default-open',
                availability: 'default-open',
                teacher_plan: 'unavailable',
                course_access: Object.freeze({}),
                activity_access: Object.freeze({})
            });
        }
        if (typeof adapter.getFutureGalaxyState !== 'function') {
            return Object.freeze({
                galaxy_key: GALAXY_KEY,
                source: 'adapter-unavailable',
                availability: 'unavailable',
                teacher_plan: 'unavailable',
                course_access: deriveCourseAccess(sanitizeActivityAccess(null)),
                activity_access: sanitizeActivityAccess(null)
            });
        }
        try {
            const incoming = adapter.getFutureGalaxyState({ galaxy_key: GALAXY_KEY, courses });
            if (!incoming || typeof incoming !== 'object') throw new Error('Invalid course state adapter response');
            if (typeof incoming.then === 'function') throw new Error('Future galaxy state must be a cached snapshot, not a pending fetch');
            if (incoming.availability !== 'available' || !incoming.activity_access || typeof incoming.activity_access !== 'object') throw new Error('Unknown future galaxy availability');
            const activity_access = sanitizeActivityAccess(incoming.activity_access);
            return Object.freeze({
                galaxy_key: GALAXY_KEY,
                source: 'adapter',
                availability: 'available',
                teacher_plan: incoming.teacher_plan || 'unavailable',
                course_access: deriveCourseAccess(activity_access),
                activity_access
            });
        } catch (error) {
            return Object.freeze({
                galaxy_key: GALAXY_KEY,
                source: 'adapter-unavailable',
                availability: 'unavailable',
                teacher_plan: 'unavailable',
                course_access: deriveCourseAccess(sanitizeActivityAccess(null)),
                activity_access: sanitizeActivityAccess(null)
            });
        }
    };

    global.FrontierCourseManifest = Object.freeze({
        galaxy_key: GALAXY_KEY,
        courses,
        getCourse,
        getCourseByPage,
        getActivity,
        adaptBe004Units,
        configureHttp,
        hasHttpConfig: () => !!httpConfig,
        refresh,
        resolveAvailability
    });
})(window);

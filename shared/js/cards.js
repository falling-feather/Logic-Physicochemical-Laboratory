// ===== Card Renderer (Bento Grid) =====

function initExperimentCards() {
    Object.keys(CONFIG.experiments).forEach(category => {
        const container = document.getElementById(`${category}-experiments`);
        if (!container) return;

        const accent = CONFIG.accentColors[category];

        container.innerHTML = CONFIG.experiments[category].map(exp => {
            const meta = getCardLearningMeta(category, exp);
            const variantClass = exp.variant === 'featured' ? 'card--featured'
                : exp.variant === 'upcoming' ? 'card--upcoming'
                : '';
            const subjectLabel = CONFIG.pages?.[category]?.label || category;

            const statusLabel = exp.variant === 'featured' ? '推荐体验'
                : exp.variant === 'upcoming' ? '即将推出'
                : '可探索';

            return `
                <div class="card card--${accent} ${variantClass}" onclick="openExperiment('${exp.id}', event)" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openExperiment('${exp.id}', event)}" tabindex="0" role="button" aria-label="${exp.title}">
                    <div class="card-icon">
                        <i data-lucide="${exp.icon}"></i>
                    </div>
                    <div class="card-meta">
                        <span>${escapeCardHtml(subjectLabel)}</span>
                        <span>${escapeCardHtml(statusLabel)}</span>
                    </div>
                    <h3 class="card-title">${escapeCardHtml(exp.title)}</h3>
                    <p class="card-desc">${escapeCardHtml(exp.description)}</p>
                    <div class="card-learning">
                        <span>学习目标</span>
                        <p>${escapeCardHtml(meta.task)}</p>
                    </div>
                    <span class="card-status card-status--${exp.variant}">${statusLabel}</span>
                </div>
            `;
        }).join('');

        if (typeof lucide !== 'undefined') lucide.createIcons();
    });
}

function getCardLearningMeta(category, exp) {
    const learning = CONFIG.learningDesign || {};
    const subject = learning.subjects ? learning.subjects[category] : null;
    const focus = learning.focus ? learning.focus[exp.id] : null;
    return {
        task: focus?.task || `观察 ${exp.title} 中参数变化与结论的对应关系。`
    };
}

function escapeCardHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

let _openExpBusy = false;
function openExperiment(id, evt) {
    if (_openExpBusy) return;
    _openExpBusy = true;

    // Find which page this experiment belongs to
    let page = null;
    for (const [category, experiments] of Object.entries(CONFIG.experiments)) {
        if (experiments.some(exp => exp.id === id)) {
            page = category;
            break;
        }
    }

    const btn = evt && evt.currentTarget;
    if (btn) {
        btn.style.transition = 'transform 0.15s ease';
        btn.style.transform = 'scale(0.97)';
        setTimeout(() => {
            btn.style.transform = '';
            if (page && typeof ModuleSelector !== 'undefined') {
                ModuleSelector.openModule(page, id);
            }
            _openExpBusy = false;
        }, 150);
    } else if (page && typeof ModuleSelector !== 'undefined') {
        ModuleSelector.openModule(page, id);
        _openExpBusy = false;
    } else {
        _openExpBusy = false;
    }
}

window.initExperimentCards = initExperimentCards;
window.openExperiment = openExperiment;

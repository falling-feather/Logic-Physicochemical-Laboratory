// ===== Card Renderer (Bento Grid) =====

function initExperimentCards() {
    Object.keys(CONFIG.experiments).forEach(category => {
        const container = document.getElementById(`${category}-experiments`);
        if (!container) return;

        const accent = CONFIG.accentColors[category];

        container.innerHTML = CONFIG.experiments[category].map(exp => {
            const variantClass = exp.variant === 'featured' ? 'card--featured'
                : exp.variant === 'upcoming' ? 'card--upcoming'
                : '';

            const statusLabel = exp.variant === 'featured' ? '推荐体验'
                : exp.variant === 'upcoming' ? '即将推出'
                : '可探索';

            return `
                <div class="card card--${accent} ${variantClass}" onclick="openExperiment('${exp.id}', event)" onkeydown="if(event.key==='Enter'||event.key===' '){event.preventDefault();openExperiment('${exp.id}', event)}" tabindex="0" role="button" aria-label="${exp.title}">
                    <div class="card-icon">
                        <i data-lucide="${exp.icon}"></i>
                    </div>
                    <h3 class="card-title">${exp.title}</h3>
                    <p class="card-desc">${exp.description}</p>
                    <span class="card-status card-status--${exp.variant}">${statusLabel}</span>
                </div>
            `;
        }).join('');

        if (typeof lucide !== 'undefined') lucide.createIcons();
    });
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

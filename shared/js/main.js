// ===== Main Application Bootstrap =====

function initApp() {
    // 1. Initialize card system
    initExperimentCards();

    // 1b. Initialize module selector (gallery-based navigation per subject page)
    if (typeof ModuleSelector !== 'undefined') ModuleSelector.init();

    // 2. Initialize homepage (stars, parallax, eyes, satellites, shooting stars)
    initHome();

    // 3. Initialize abacus
    if (typeof updateAbacus === 'function') updateAbacus();

    // 3a. Initialize function graph
    if (typeof initFunctionGraph === 'function') initFunctionGraph();

    // 3a2. Initialize calculus visualization
    if (typeof initCalculus === 'function') initCalculus();

    // 3a3. Initialize geometry transformations
    if (typeof initGeoTransform === 'function') initGeoTransform();

    // 3a4. Initialize complex numbers visualization
    if (typeof initComplexVis === 'function') initComplexVis();

    // 3b. Initialize physics simulation
    if (typeof initPhysics === 'function') initPhysics();

    // 3c. Initialize electromagnetic field visualization
    if (typeof initElectromagnetic === 'function') initElectromagnetic();

    // 3d. Initialize wave demo
    if (typeof initWaves === 'function') initWaves();

    // 3d2. Initialize relativity
    if (typeof initRelativity === 'function') initRelativity();

    // 3e. Initialize periodic table
    if (typeof initPeriodicTable === 'function') initPeriodicTable();

    // 3e2. Initialize molecular structure
    if (typeof initMoleculeVis === 'function') initMoleculeVis();

    // 3e3. Initialize chemical reactions
    if (typeof initChemReaction === 'function') initChemReaction();

    // 3f. Initialize search algorithms (binary search + graph traversal)
    if (typeof initSearchAlgorithms === 'function') initSearchAlgorithms();

    // 3g. Initialize graph algorithms (Dijkstra + Prim)
    if (typeof initGraphAlgo === 'function') initGraphAlgo();

    // 3h. Initialize data structures
    if (typeof initDataStructVis === 'function') initDataStructVis();

    // 3i. Initialize biology modules
    if (typeof initBiology === 'function') initBiology();

    // 4. Initialize scroll animation system
    if (typeof initScrollAnimations === 'function') initScrollAnimations();

    // 5. Initialize router (page transitions)
    Router.init();

    // 6. Speed slider for bucket sort
    const speedInput = document.getElementById('sort-speed');
    if (speedInput) {
        speedInput.addEventListener('input', (e) => {
            const newSpeed = parseInt(e.target.value);
            window.sortSpeed = newSpeed;
            if (typeof sortSpeed !== 'undefined') {
                sortSpeed = newSpeed;
            }
            const speedValueEl = document.getElementById('speed-value');
            if (speedValueEl) {
                speedValueEl.textContent = newSpeed + 'ms';
            }
        });
    }

    // 7. Render Lucide icons
    if (typeof lucide !== 'undefined') lucide.createIcons();

    // 8. Nav indicator initial position
    requestAnimationFrame(() => {
        const activeNav = document.querySelector('.nav-item.active');
        if (activeNav && Router.moveIndicator) {
            Router.moveIndicator(activeNav);
        }
    });

    // 9. Window resize: update nav indicator
    window.addEventListener('resize', () => {
        const activeNav = document.querySelector('.nav-item.active');
        if (activeNav && Router.moveIndicator) {
            Router.moveIndicator(activeNav);
        }
    });

    // 10. Back to top button
    initBackToTop();

    // 11. Footer visibility based on current page
    updateFooterVisibility();
}

// ===== Back to Top =====
function initBackToTop() {
    const btn = document.getElementById('back-to-top');
    if (!btn) return;

    window.addEventListener('scroll', () => {
        if (window.scrollY > 400) {
            btn.classList.add('visible');
        } else {
            btn.classList.remove('visible');
        }
    }, { passive: true });

    btn.addEventListener('click', () => {
        window.scrollTo({ top: 0, behavior: 'smooth' });
    });
}

// ===== Footer Visibility =====
function updateFooterVisibility() {
    const footer = document.getElementById('site-footer');
    if (!footer) return;

    // Hide footer on home page, show on content pages
    const observer = new MutationObserver(() => {
        const homePage = document.getElementById('page-home');
        footer.style.display = homePage && homePage.classList.contains('active') ? 'none' : '';
    });

    observer.observe(document.querySelector('.main-content'), {
        childList: false,
        subtree: true,
        attributes: true,
        attributeFilter: ['class']
    });

    // Initial check
    const homePage = document.getElementById('page-home');
    footer.style.display = homePage && homePage.classList.contains('active') ? 'none' : '';
}

window.updateFooterVisibility = updateFooterVisibility;

// Launch
document.addEventListener('DOMContentLoaded', initApp);

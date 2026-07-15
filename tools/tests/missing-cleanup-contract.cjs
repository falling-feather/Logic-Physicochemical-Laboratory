const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');

class FakeClassList {
    constructor() { this.values = new Set(); }
    add(...names) { names.forEach(name => this.values.add(name)); }
    remove(...names) { names.forEach(name => this.values.delete(name)); }
    contains(name) { return this.values.has(name); }
    toggle(name, force) {
        const enabled = force === undefined ? !this.contains(name) : Boolean(force);
        if (enabled) this.add(name); else this.remove(name);
        return enabled;
    }
}

class FakeTarget {
    constructor() {
        this._listeners = [];
        this.classList = new FakeClassList();
        this.children = [];
        this.style = {};
        this.dataset = {};
        this.disabled = false;
        this.value = '';
        this.parentElement = null;
        this._textContent = '';
        this._innerHTML = '';
        this.writeCount = 0;
    }
    addEventListener(event, handler, options) {
        this._listeners.push({ event, handler, options });
    }
    removeEventListener(event, handler) {
        const index = this._listeners.findIndex(item => item.event === event && item.handler === handler);
        if (index >= 0) this._listeners.splice(index, 1);
    }
    liveListeners() { return this._listeners.length; }
    fire(event, payload = {}) {
        this._listeners.filter(item => item.event === event).forEach(item => item.handler(payload));
    }
    appendChild(child) {
        child.parentElement = this;
        this.children.push(child);
        return child;
    }
    append(...children) { children.forEach(child => this.appendChild(child)); }
    querySelectorAll(selector) {
        if (selector === '.array-bar') return this.children.filter(child => child.className === 'array-bar');
        return [];
    }
    setAttribute(name, value) { this[name] = value; }
    get textContent() { return this._textContent; }
    set textContent(value) { this._textContent = String(value); this.writeCount += 1; }
    get innerHTML() { return this._innerHTML; }
    set innerHTML(value) {
        this._innerHTML = String(value);
        this.children = [];
        this.writeCount += 1;
    }
}

function createTimerHarness() {
    let nextId = 1;
    const timers = new Map();
    return {
        timers,
        setTimeout(callback) {
            const id = nextId++;
            timers.set(id, callback);
            return id;
        },
        clearTimeout(id) { timers.delete(id); },
        runAll() {
            const pending = [...timers.entries()];
            timers.clear();
            pending.forEach(([, callback]) => callback());
        }
    };
}

const sortingSource = read('pages/algorithms/algorithms.js');
assert.match(sortingSource, /function initAlgorithms\(\) \{\s*destroyAlgorithms\(\);/);
assert.match(sortingSource, /function destroyAlgorithms\(\)/);
assert.match(sortingSource, /window\.SortingLab = SortingLab/);
assert.equal(
    (sortingSource.match(/setTimeout\(/g) || []).length,
    2,
    'sorting timers must only be created by the cancellable sleep/schedule helpers'
);
assert.equal(
    (sortingSource.match(/\.addEventListener\(/g) || []).length,
    0,
    'sorting lifecycle must not duplicate the application-owned speed listener'
);

const sortingTimers = createTimerHarness();
const sortingIds = Object.fromEntries([
    'sort-speed', 'speed-value', 'original-array', 'sorted-array',
    'buckets-container', 'sort-info'
].map(id => [id, new FakeTarget()]));
sortingIds['sort-speed'].value = '100';
const sortInfoParent = new FakeTarget();
sortInfoParent.appendChild(sortingIds['sort-info']);
const sortingButtons = [new FakeTarget(), new FakeTarget(), new FakeTarget()];
const sortingDocument = new FakeTarget();
sortingDocument.getElementById = id => sortingIds[id] || null;
sortingDocument.createElement = () => new FakeTarget();
sortingDocument.querySelectorAll = selector => {
    if (selector === '.sort-toolbar .btn') return sortingButtons;
    if (selector === '#original-array .array-bar') return sortingIds['original-array'].children;
    if (selector === '#sorted-array .array-bar') return sortingIds['sorted-array'].children;
    if (selector === '#original-array .array-bar.active') {
        return sortingIds['original-array'].children.filter(child => child.classList.contains('active'));
    }
    return [];
};
const sortingContext = {
    window: {},
    document: sortingDocument,
    setTimeout: callback => sortingTimers.setTimeout(callback),
    clearTimeout: id => sortingTimers.clearTimeout(id),
    console
};
vm.createContext(sortingContext);
vm.runInContext(sortingSource, sortingContext, { filename: 'pages/algorithms/algorithms.js' });

(async () => {
const sorting = sortingContext.window.SortingLab;
assert.ok(sorting && typeof sorting.init === 'function' && typeof sorting.destroy === 'function');
const applicationSpeedListener = () => {};
sortingIds['sort-speed'].addEventListener('input', applicationSpeedListener);
sorting.init();
sorting.init();
assert.equal(sortingIds['sort-speed'].liveListeners(), 1, 'sorting reinit must not duplicate the application speed listener');
const sortRun = sortingContext.window.startBucketSort();
const duplicateSortRun = sortingContext.window.startBucketSort();
await duplicateSortRun;
assert.equal(sortingIds['original-array'].children.length, 15);
assert.equal(sortingTimers.timers.size, 1, 'sorting double start must expose only one cancellable pending sleep');
sorting.destroy();
await sortRun;
assert.equal(sortingTimers.timers.size, 0, 'sorting destroy must cancel every pending timeout');
assert.equal(sortingIds['sort-speed'].liveListeners(), 1, 'sorting destroy must preserve the application speed listener');
assert.ok(sortingButtons.every(button => button.disabled === false));
const sortingWritesAfterDestroy = Object.values(sortingIds).reduce((sum, el) => sum + el.writeCount, 0);
sortingTimers.runAll();
await Promise.resolve();
assert.equal(
    Object.values(sortingIds).reduce((sum, el) => sum + el.writeCount, 0),
    sortingWritesAfterDestroy,
    'cancelled sorting work must not write DOM after destroy'
);
sorting.destroy();

const cellSource = read('pages/biology/cell-structure.js');
assert.match(cellSource, /init\(\) \{\s*this\.destroy\(\);/);
assert.match(cellSource, /destroy\(\) \{/);
assert.match(cellSource, /cancelAnimationFrame\(this\.animId\)/);
assert.match(cellSource, /this\._ro\.disconnect\(\)/);
assert.equal(
    (cellSource.match(/\.addEventListener\(/g) || []).length,
    1,
    'cell structure listeners must use the tracker helper'
);

const cellTimers = createTimerHarness();
let nextRaf = 1;
const cellRafs = new Map();
const cellWindow = new FakeTarget();
cellWindow.devicePixelRatio = 1;
const cellDocument = new FakeTarget();
const cellCanvas = new FakeTarget();
const cellCanvasParent = new FakeTarget();
cellCanvasParent.clientWidth = 640;
cellCanvas.parentElement = cellCanvasParent;
cellCanvas.getBoundingClientRect = () => ({ left: 0, top: 0, width: 640, height: 307 });
cellCanvas.getContext = () => ({ setTransform() {} });
const cellIds = {
    'cell-canvas': cellCanvas,
    'cell-info': new FakeTarget(),
    'cellstr-info': new FakeTarget(),
    'bio-cell-toggle': new FakeTarget(),
    'bio-cell-label-toggle': new FakeTarget()
};
cellDocument.getElementById = id => cellIds[id] || null;
const resizeObservers = [];
class FakeResizeObserver {
    constructor(callback) { this.callback = callback; this.disconnected = false; resizeObservers.push(this); }
    observe(target) { this.target = target; }
    disconnect() { this.disconnected = true; }
}
const cellContext = {
    window: cellWindow,
    document: cellDocument,
    ResizeObserver: FakeResizeObserver,
    requestAnimationFrame(callback) {
        const id = nextRaf++;
        cellRafs.set(id, callback);
        return id;
    },
    cancelAnimationFrame(id) { cellRafs.delete(id); },
    setTimeout: callback => cellTimers.setTimeout(callback),
    clearTimeout: id => cellTimers.clearTimeout(id),
    navigator: { vibrate() {} },
    console
};
vm.createContext(cellContext);
vm.runInContext(cellSource, cellContext, { filename: 'pages/biology/cell-structure.js' });

const cell = cellWindow.CellStructure;
assert.ok(cell && typeof cell.destroy === 'function');
cell.init();
cell.init();
assert.equal(cellRafs.size, 1, 'cell structure reinit must keep one RAF');
assert.equal(cellCanvas.liveListeners(), 7, 'cell structure must keep one listener per Canvas interaction, including touchcancel');
assert.equal(cellIds['bio-cell-toggle'].liveListeners(), 1);
assert.equal(cellIds['bio-cell-label-toggle'].liveListeners(), 1);
assert.equal(cellDocument.liveListeners(), 1, 'cell structure must keep one Escape listener');
assert.equal(resizeObservers.length, 2);
assert.equal(resizeObservers[0].disconnected, true, 'reinit must disconnect the previous ResizeObserver');
cellCanvas.fire('touchstart', {
    preventDefault() {},
    touches: [{ clientX: 320, clientY: 129 }]
});
assert.equal(cellTimers.timers.size, 1, 'cell long press must own one cancellable timeout');
cellCanvas.fire('touchcancel');
assert.equal(cellTimers.timers.size, 0, 'cell touchcancel must cancel the long-press timeout');
assert.equal(cell._lpStartXY, null);
assert.equal(cell._lpOrg, null);
cellCanvas.fire('touchstart', {
    preventDefault() {},
    touches: [{ clientX: 320, clientY: 129 }]
});
assert.equal(cellTimers.timers.size, 1, 'cell long press must remain usable after touchcancel');
cell.destroy();
assert.equal(cellRafs.size, 0, 'cell destroy must cancel RAF');
assert.equal(cellTimers.timers.size, 0, 'cell destroy must cancel long-press timeout');
assert.equal(cellCanvas.liveListeners(), 0);
assert.equal(cellIds['bio-cell-toggle'].liveListeners(), 0);
assert.equal(cellIds['bio-cell-label-toggle'].liveListeners(), 0);
assert.equal(cellDocument.liveListeners(), 0);
assert.equal(resizeObservers[1].disconnected, true);
assert.equal(cell.canvas, null);
assert.equal(cell.ctx, null);
cell.destroy();

console.log('missing-cleanup-contract: ok');
})().catch((error) => {
    console.error(error);
    process.exitCode = 1;
});

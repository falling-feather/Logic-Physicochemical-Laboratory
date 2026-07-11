const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const repoRoot = path.resolve(__dirname, '..', '..');
const source = fs.readFileSync(path.join(repoRoot, 'pages/home/home.js'), 'utf8');

const parent = { clientWidth: 1024, clientHeight: 720 };
let activeCanvas;
let canvasSequence = 0;
const workers = [];

function createCanvas() {
  const canvas = {
    id: `canvas-${++canvasSequence}`,
    dataset: {},
    style: {},
    parentElement: parent,
    transferred: false,
    transferControlToOffscreen() {
      assert.equal(this.transferred, false, 'the same canvas must not be transferred twice');
      this.transferred = true;
      return { id: `${this.id}-offscreen` };
    },
    cloneNode() {
      const replacement = createCanvas();
      replacement.dataset = { ...this.dataset };
      replacement.style = { ...this.style };
      return replacement;
    },
    replaceWith(replacement) {
      activeCanvas = replacement;
    },
    getContext() {
      assert.equal(this.transferred, false, 'a transferred canvas cannot provide a 2D context');
      return null;
    },
  };
  return canvas;
}

class FakeWorker {
  constructor() {
    this.messages = [];
    this.terminated = false;
    workers.push(this);
  }

  postMessage(message) {
    this.messages.push(message);
  }

  terminate() {
    this.terminated = true;
  }
}

class FakeResizeObserver {
  observe() {}
  disconnect() {}
}

activeCanvas = createCanvas();
const homePage = { classList: { contains: (name) => name === 'active' } };
const context = {
  console,
  document: {
    addEventListener() {},
    getElementById(id) {
      if (id === 'particle-network') return activeCanvas;
      if (id === 'page-home') return homePage;
      return null;
    },
  },
  navigator: { hardwareConcurrency: 8, deviceMemory: 8 },
  performance: { now: () => 0 },
  requestAnimationFrame: () => 1,
  ResizeObserver: FakeResizeObserver,
  setTimeout: () => 1,
  clearTimeout() {},
  Worker: FakeWorker,
  window: {
    __englabCache: null,
    devicePixelRatio: 1,
    innerHeight: 720,
    innerWidth: 1024,
  },
};

vm.runInNewContext(source, context, { filename: 'pages/home/home.js' });
const particles = context.window.ParticleNetwork;

particles.init();
const firstCanvas = activeCanvas;
assert.equal(workers.length, 1);
assert.equal(firstCanvas.transferred, true);
assert.equal(particles.running, true);

particles.destroy();
assert.equal(workers[0].terminated, true);
assert.notEqual(activeCanvas, firstCanvas, 'destroy must replace a transferred canvas');
assert.equal(activeCanvas.transferred, false);

assert.doesNotThrow(() => particles.init());
assert.equal(workers.length, 2, 're-entering home should start a fresh worker');
assert.equal(activeCanvas.transferred, true);
assert.equal(particles.running, true);

particles.destroy();
console.log('home particle lifecycle contract passed');

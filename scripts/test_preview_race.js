const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const html = fs.readFileSync(path.join(__dirname, '..', 'assets', 'preview.html'), 'utf8');
const script = html.match(/<script>([\s\S]*)<\/script>/)[1];

function element(properties = {}) {
  return Object.assign({
    dataset: {},
    disabled: false,
    hidden: false,
    listeners: {},
    style: {},
    addEventListener(type, listener) { this.listeners[type] = listener; },
    dispatch(type) { return this.listeners[type](); },
    remove() {},
    select() {},
    setAttribute(name, value) { this[name] = value; },
  }, properties);
}

function loadPreview() {
  const layout1 = element({ value: 'L1' });
  const layout2 = element({ value: 'L2' });
  const style1 = element({ value: 'S1' });
  const confirm = element();
  const copy = element({ disabled: true, hidden: true });
  const code = element({ value: 'Not confirmed' });
  const status = element({ textContent: 'Final rendering waits for this code.' });
  const platformNote = element();
  const main = element();
  const badge = element({ hidden: true });
  const label = element();
  const tab = element({
    dataset: { adapted: 'false', device: 'iphone', frame: 'iPhone portrait', platform: 'iPhone' },
  });
  const tablet = element({
    dataset: { adapted: 'true', device: 'ipad', frame: 'iPad portrait', platform: 'iPad' },
  });
  const pendingWrites = [];
  let selectedLayout = layout1;

  const document = {
    body: { append() {} },
    createElement: () => element(),
    execCommand: () => false,
    querySelector(selector) {
      return {
        '#adapted-badge': badge,
        '#code': code,
        '#confirm': confirm,
        '#copy': copy,
        '#platform-note': platformNote,
        '#status': status,
        '[data-platform][aria-pressed="true"]': tab,
        '[name=layout]:checked': selectedLayout,
        '[name=style]:checked': style1,
        main,
      }[selector];
    },
    querySelectorAll(selector) {
      return {
        '.device-label': [label],
        '[data-platform]': [tab, tablet],
        '[name=layout], [name=style]': [layout1, layout2, style1],
      }[selector];
    },
  };
  const navigator = {
    clipboard: {
      writeText: () => new Promise((resolve) => pendingWrites.push(resolve)),
    },
  };

  vm.runInNewContext(script, { document, navigator });
  return {
    code,
    confirm,
    copy,
    layout2,
    pendingWrites,
    selectLayout: (layout) => { selectedLayout = layout; },
    status,
    tab, tablet, main, label, badge,
  };
}

async function assertResetSurvives(pendingCopy, preview) {
  preview.selectLayout(preview.layout2);
  preview.layout2.dispatch('change');
  preview.pendingWrites.shift()();
  await pendingCopy;
  assert.equal(preview.code.value, 'Not confirmed');
  assert.equal(preview.status.textContent, 'Selection changed. Confirm again before rendering.');
  assert.equal(preview.copy.hidden, true);
  assert.equal(preview.copy.disabled, true);
}

async function main() {
  const platform = loadPreview();
  platform.tablet.dispatch('click');
  assert.equal(platform.tablet['aria-pressed'], 'true');
  assert.equal(platform.tab['aria-pressed'], 'false');
  assert.equal(platform.main.dataset.device, 'ipad');
  assert.equal(platform.label.textContent, 'iPad portrait');
  assert.equal(platform.badge.hidden, false);
  platform.tab.dispatch('click');
  assert.equal(platform.tablet['aria-pressed'], 'false');
  assert.equal(platform.tab['aria-pressed'], 'true');
  assert.equal(platform.main.dataset.device, 'iphone');
  assert.equal(platform.badge.hidden, true);

  const initial = loadPreview();
  await assertResetSurvives(initial.confirm.dispatch('click'), initial);

  const repeat = loadPreview();
  const firstCopy = repeat.confirm.dispatch('click');
  repeat.pendingWrites.shift()();
  await firstCopy;
  await assertResetSurvives(repeat.copy.dispatch('click'), repeat);

  console.log('preview: pressed-state and device updates pass; stale confirm and repeat-copy completions ignored');
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

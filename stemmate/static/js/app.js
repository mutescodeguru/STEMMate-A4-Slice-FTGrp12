// App shell: routing, login, plan list, outbox, connection banner, sync polling.
import { api, newPlanId, usingMock } from './api.js';
import { SYNC_POLL_MS } from './config.js';
import { initEditor, openPlan, flush, hasUnsaved, refreshSyncStatus, currentPlanId } from './editor.js';
import { statusChip, formatTime } from './status.js';

const $ = (sel) => document.querySelector(sel);
const views = ['login', 'plans', 'editor', 'outbox'];

let user = null;
let pollTimer = null;
let lastPlans = [];
let loginNotice = '';
let resumeHash = null;   // editor to return to after a 401, with its unsaved edits kept

// ---------- routing ----------

function show(view) {
  views.forEach((v) => { $(`#view-${v}`).hidden = v !== view; });
  $('#bottom-nav').hidden = view === 'login';
  document.querySelectorAll('.bottom-nav a').forEach((a) => {
    const active = a.dataset.nav === view || (view === 'editor' && a.dataset.nav === 'plans');
    if (active) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current');
  });
}

function focusHeading(view) {
  const h = $(`#view-${view} h1`);
  if (h) { h.setAttribute('tabindex', '-1'); h.focus(); }
}

async function route() {
  const hash = location.hash || '#/plans';
  if (!user && hash !== '#/login') { location.hash = '#/login'; return; }
  if (user && hash === '#/login') { location.hash = '#/plans'; return; }

  if (hash === '#/login') {
    show('login');
    const err = $('#login-error');
    err.hidden = !loginNotice;
    err.textContent = loginNotice;
    $('#login-username').focus();
    return;
  }
  if (currentPlanId() && hasUnsaved()) await flush();

  if (hash === '#/outbox') { await renderOutbox(); show('outbox'); focusHeading('outbox'); return; }

  if (hash === '#/new') {
    const id = newPlanId();
    await openPlan({ plan_id: id, version: 0 }, { isNew: true });
    history.replaceState(null, '', `#/plan/${id}`); // no hashchange event
    show('editor');                                   // only once the form is filled
    $('#f-title').focus();
    return;
  }
  const m = /^#\/plan\/(.+)$/.exec(hash);
  if (m) {
    try {
      const plan = await api.getPlan(decodeURIComponent(m[1]));
      await openPlan(plan);
      show('editor');
      focusHeading('editor');
    } catch (e) {
      if (!handleAuth(e)) { location.hash = '#/plans'; }
    }
    return;
  }

  await renderPlans();
  show('plans');
  focusHeading('plans');
}

// ---------- auth (SR-01) ----------

function handleAuth(err) {
  if (err && err.status === 401) { authLost(); return true; }
  return false;
}

function authLost() {
  user = null;
  stopPolling();
  resumeHash = !$('#view-editor').hidden ? location.hash : null;
  loginNotice = resumeHash
    ? 'Your session ended. Sign in again and you will go back to your plan. Unsaved changes are kept.'
    : 'Your session ended. Your draft is saved. Sign in to continue.';
  location.hash = '#/login';
}

$('#login-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const err = $('#login-error');
  const username = $('#login-username').value.trim();
  const password = $('#login-password').value;
  if (!username || !password) {
    err.textContent = 'Enter your username and password.';
    err.hidden = false;
    err.focus();
    return;
  }
  try {
    user = await api.login(username, password);
    $('#login-password').value = '';
    loginNotice = '';
    startPolling();
    if (resumeHash) {
      // Go back to the form exactly as it was on screen, then save what was pending.
      history.replaceState(null, '', resumeHash);
      resumeHash = null;
      show('editor');
      focusHeading('editor');
      await flush();
      return;
    }
    await restoreLatestDraft();
  } catch (ex) {
    err.textContent = ex.status === 0
      ? 'The app on this device is not responding. Make sure STEMMate is running, then try again.'
      : ex.message;
    err.hidden = false;
    err.focus();
  }
});

// After login, reopen the latest draft (QR-02, C2).
async function restoreLatestDraft() {
  try {
    const draft = await api.latestDraft();
    if (draft) {
      history.replaceState(null, '', `#/plan/${encodeURIComponent(draft.plan_id)}`);
      await openPlan(draft, { restoredAt: draft.last_modified });
      show('editor');
      focusHeading('editor');
      return;
    }
  } catch (e) { if (handleAuth(e)) return; }
  goTo('#/plans');
}

/** Navigate, and still re-render if we are already on that route. */
function goTo(hash) {
  if (location.hash === hash) route();
  else location.hash = hash;
}

$('#logout').addEventListener('click', async () => {
  await flush();
  try { await api.logout(); } catch { /* signing out locally anyway */ }
  user = null;
  stopPolling();
  loginNotice = '';
  resumeHash = null;
  location.hash = '#/login';
});

// ---------- lists ----------

function planItem(p, { withRetry = false } = {}) {
  const li = document.createElement('li');
  li.className = 'plan-item' + (p.sync_status === 'interrupted' ? ' plan-item--attention' : '');
  const main = document.createElement('div');
  main.className = 'plan-item__main';
  const title = document.createElement('p');
  title.className = 'plan-item__title';
  title.textContent = p.title || 'Untitled plan';
  const meta = document.createElement('p');
  meta.className = 'plan-item__meta';
  meta.textContent = `${p.is_complete ? 'Complete' : 'Draft'} · Last saved ${formatTime(p.last_modified)}`;
  main.append(title, meta);

  const open = document.createElement('a');
  open.href = `#/plan/${encodeURIComponent(p.plan_id)}`;
  open.textContent = p.sync_status === 'syncing' ? 'View' : 'Open';
  open.setAttribute('aria-label', `${open.textContent} ${p.title || 'untitled plan'}`);

  li.append(main, statusChip(p.sync_status), open);
  if (withRetry && p.sync_status === 'interrupted') {
    const retry = document.createElement('button');
    retry.type = 'button';
    retry.className = 'btn btn--secondary';
    retry.textContent = 'Retry';
    retry.setAttribute('aria-label', `Retry syncing ${p.title || 'untitled plan'}`);
    retry.addEventListener('click', runSync);
    li.appendChild(retry);
  }
  return li;
}

async function loadPlans() {
  try { lastPlans = await api.listPlans(); } catch (e) { handleAuth(e); }
  return lastPlans;
}

async function renderPlans() {
  const plans = await loadPlans();
  const list = $('#plan-list');
  list.innerHTML = '';
  plans.forEach((p) => list.appendChild(planItem(p)));
  $('#plan-list-empty').hidden = plans.length > 0;
}

async function renderOutbox() {
  const plans = (await loadPlans()).filter((p) => p.is_complete || p.sync_status !== 'local');
  const order = { interrupted: 0, syncing: 1, pending: 2, synced: 3, local: 4 };
  plans.sort((a, b) => order[a.sync_status] - order[b.sync_status]);
  const list = $('#outbox-list');
  list.innerHTML = '';
  plans.forEach((p) => list.appendChild(planItem(p, { withRetry: true })));
  $('#outbox-empty').hidden = plans.length > 0;
  const waiting = plans.filter((p) => p.sync_status !== 'synced').length;
  $('#outbox-summary').textContent =
    `${waiting} ${waiting === 1 ? 'plan' : 'plans'} waiting · All copies are saved on this device.`;
}

$('#new-plan').addEventListener('click', () => { location.hash = '#/new'; });
$('#editor-back').addEventListener('click', () => { location.hash = '#/plans'; });

// ---------- sync (FR-04, FR-05) ----------

async function runSync() {
  const btn = $('#sync-now');
  btn.disabled = true;
  try {
    await api.syncRun();
    announce('Sync started.');
    await poll();
  } catch (e) {
    if (!handleAuth(e)) setBanner('error', 'Could not start syncing. Your plans are safe on this device.');
  } finally {
    btn.disabled = false;
  }
}
$('#sync-now').addEventListener('click', runSync);

async function poll() {
  if (!user) return;
  let s;
  try {
    s = await api.syncStatus();
  } catch (e) {
    if (handleAuth(e)) return;
    setBanner('error', 'The app on this device is not responding. Anything already saved is safe.');
    return;
  }

  const waiting = s.pending + s.syncing + s.interrupted;
  const badge = $('#outbox-badge');
  badge.hidden = waiting === 0;
  badge.textContent = waiting;
  badge.setAttribute('aria-label', `${waiting} waiting`);

  if (s.interrupted > 0) {
    setBanner('warn', `${s.interrupted} ${s.interrupted === 1 ? 'plan' : 'plans'} stopped syncing part way. They are safe on this device and will retry.`,
      { label: 'Open outbox', onClick: () => { location.hash = '#/outbox'; } });
  } else if (s.last_outcome && s.last_outcome !== 'success' && s.pending > 0) {
    setBanner('info', 'Working offline. Everything is saved on this device.');
  } else {
    setBanner(null);
  }

  // Keep open views in step with background sync.
  if (!$('#view-outbox').hidden) await renderOutbox();
  else if (!$('#view-plans').hidden) await renderPlans();
  else if (!$('#view-editor').hidden && currentPlanId()) {
    const plans = await loadPlans();
    const mine = plans.find((p) => p.plan_id === currentPlanId());
    if (mine) refreshSyncStatus(mine.sync_status);
  }
}

function startPolling() { stopPolling(); poll(); pollTimer = setInterval(poll, SYNC_POLL_MS); }
function stopPolling() { clearInterval(pollTimer); pollTimer = null; }

// ---------- banner & announcements ----------

let bannerKey = '';
function setBanner(kind, text, action) {
  const b = $('#banner');
  const key = `${kind}|${text}`;
  if (key === bannerKey) return;      // don't re-announce the same message every 5 s
  bannerKey = key;
  if (!kind) { b.hidden = true; return; }
  const icons = { info: 'ⓘ', warn: '⚠', error: '⚠' };
  b.className = `banner banner--${kind}`;
  b.querySelector('.banner__icon').textContent = icons[kind];
  b.querySelector('.banner__text').textContent = text;
  const btn = b.querySelector('.banner__action');
  btn.hidden = !action;
  if (action) { btn.textContent = action.label; btn.onclick = action.onClick; }
  b.hidden = false;
}

function announce(msg) {
  const a = $('#announcer');
  a.textContent = '';
  setTimeout(() => { a.textContent = msg; }, 50);
}

// ---------- start ----------

initEditor({ onAuthLost: authLost, onChanged: () => { poll(); } });
window.addEventListener('hashchange', route);

(async function start() {
  if (usingMock) {
    console.info('[STEMMate] Mock API in use. Sign in as demo_facilitator / demo123. Failure switches: window.stemmateMock');
    document.title = 'STEMMate Namibia (mock data)';
  }
  try {
    user = await api.me();
    startPolling();
  } catch (e) {
    user = null;
    if (e.status === 0) loginNotice = 'The app on this device is not responding. Make sure STEMMate is running.';
  }
  route();
})();

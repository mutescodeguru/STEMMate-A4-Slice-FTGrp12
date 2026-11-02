// Mock of P3's local API, for building and demoing the UI before the backend is ready.
// Follows the API contract: same routes' behaviour, status codes and error format.
// Data lives in localStorage under "stemmate_mock_db". All data is fictional (PR-01).
//
// Failure switches for testing (type in the browser console):
//   stemmateMock.offline = true      -> every call fails like the local app is not running
//   stemmateMock.failSync = true     -> sync stops part way (status "interrupted")
//   stemmateMock.storageLimit = 2000 -> tiny storage budget, saves return 507
//   stemmateMock.reset()             -> wipe mock data
import { completeErrors, draftErrors, totalDuration } from './validation.js';

let ApiError = Error;
export function setErrorClass(cls) { ApiError = cls; }

const KEY = 'stemmate_mock_db';
const SESSION_KEY = 'stemmate_mock_session';
const IDLE_MS = 30 * 60 * 1000; // AC-6
const ALLOWED = ['version', 'title', 'level', 'safety_notes', 'inclusion_prompt', 'steps', 'materials'];

const controls = { offline: false, failSync: false, storageLimit: 52428800, reset };
window.stemmateMock = controls;

function seed() {
  return {
    users: [
      { user_id: 1, username: 'demo_facilitator', password: 'demo123' },
      { user_id: 2, username: 'facilitator2', password: 'demo123' },
    ],
    materials: [
      { material_id: 1, name: 'AA battery', safety_notes: 'Do not short-circuit.' },
      { material_id: 2, name: 'Insulated wire (20 cm)', safety_notes: 'Strip ends with adult help.' },
      { material_id: 3, name: 'Torch bulb', safety_notes: 'Glass can break; handle gently.' },
      { material_id: 4, name: 'Plastic cups', safety_notes: 'None.' },
      { material_id: 5, name: 'Red cabbage', safety_notes: 'Adult handles boiling water.' },
      { material_id: 6, name: 'A4 paper', safety_notes: 'None.' },
      { material_id: 7, name: 'Masking tape', safety_notes: 'None.' },
      { material_id: 8, name: 'Thermometer', safety_notes: 'Glass thermometers: handle with care.' },
    ],
    plans: {},
  };
}

function load() {
  try {
    const db = JSON.parse(localStorage.getItem(KEY));
    if (db && db.users) return db;
  } catch { /* ignore */ }
  const db = seed();
  persist(db);
  return db;
}
function persist(db) { try { localStorage.setItem(KEY, JSON.stringify(db)); } catch { /* ignore */ } }
function reset() { localStorage.removeItem(KEY); sessionStorage.removeItem(SESSION_KEY); location.reload(); }

// Start-up recovery rule proposed to P3: a plan left "syncing" by a crash becomes "interrupted".
(function recoverOnStart() {
  const db = load();
  let changed = false;
  Object.values(db.plans).forEach((p) => { if (p.sync_status === 'syncing') { p.sync_status = 'interrupted'; changed = true; } });
  if (changed) persist(db);
})();

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
const fail = (status, code, message, extra = {}) => { throw new ApiError({ status, code, message, ...extra }); };
const now = () => new Date().toISOString();
const clone = (x) => JSON.parse(JSON.stringify(x));

async function call(fn, { auth = true } = {}) {
  await wait(120); // feel like a real request
  if (controls.offline) fail(0, 'NETWORK', 'Could not reach the app on this device.');
  let user = null;
  if (auth) {
    const s = JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
    if (!s || Date.now() - s.last > IDLE_MS) {
      sessionStorage.removeItem(SESSION_KEY);
      fail(401, 'UNAUTHENTICATED', 'Please sign in again.');
    }
    s.last = Date.now();
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(s));
    user = s.user;
  }
  const db = load();
  const result = fn(db, user);
  persist(db);
  return result;
}

function ownPlan(db, user, planId) {
  const p = db.plans[planId];
  if (!p || p.owner_id !== user.user_id) fail(404, 'NOT_FOUND', 'That plan could not be found.');
  return p;
}

const summary = (p) => ({
  plan_id: p.plan_id, title: p.title, level: p.level, is_complete: p.is_complete,
  sync_status: p.sync_status, version: p.version, last_modified: p.last_modified,
});
const full = (p) => clone({ ...p });

function syncStatusCounts(db, user) {
  const counts = { local: 0, pending: 0, syncing: 0, interrupted: 0, synced: 0 };
  Object.values(db.plans).filter((p) => p.owner_id === user.user_id)
    .forEach((p) => { counts[p.sync_status] += 1; });
  return { ...counts, last_attempt_at: db.last_attempt_at || null, last_outcome: db.last_outcome || null };
}

export const api = {
  login: (username, password) => call((db) => {
    const u = db.users.find((x) => x.username === username && x.password === password);
    if (!u) fail(401, 'INVALID_CREDENTIALS', 'That username or password is not right.');
    sessionStorage.setItem(SESSION_KEY, JSON.stringify({ user: { user_id: u.user_id, username: u.username }, last: Date.now() }));
    return { user_id: u.user_id, username: u.username };
  }, { auth: false }),

  logout: () => call(() => { sessionStorage.removeItem(SESSION_KEY); return null; }, { auth: false }),

  me: () => call((db, user) => clone(user)),

  savePlan: (planId, body) => call((db, user) => {
    const unknown = Object.keys(body).filter((k) => !ALLOWED.includes(k));
    if (unknown.length) fail(422, 'UNKNOWN_FIELD', 'This form sent a field the app does not accept.',
      { fields: unknown.map((f) => ({ field: f, message: 'Unknown field.' })) });

    let plan = db.plans[planId];
    if (!plan) {
      if (body.version !== 0) fail(404, 'NOT_FOUND', 'That plan could not be found.');
    } else {
      if (plan.owner_id !== user.user_id) fail(404, 'NOT_FOUND', 'That plan could not be found.');
      if (plan.sync_status === 'syncing') fail(409, 'PLAN_SYNCING', 'This plan is syncing. Try again in a moment.');
      if (body.version !== plan.version)
        fail(409, 'VERSION_CONFLICT', 'This plan was changed since you opened it.', { currentVersion: plan.version });
    }

    const errs = draftErrors(body);
    if (errs.length) fail(422, 'VALIDATION_FAILED', 'Please fix the highlighted fields.', { fields: errs });

    const next = {
      plan_id: planId, owner_id: user.user_id,
      title: body.title ?? '', level: body.level ?? '', safety_notes: body.safety_notes ?? '',
      inclusion_prompt: body.inclusion_prompt ?? '', steps: body.steps ?? [], materials: body.materials ?? [],
      estimated_duration: plan ? plan.estimated_duration : null,
      is_complete: plan ? plan.is_complete : false,
      version: (plan ? plan.version : 0) + 1,
      last_modified: now(),
    };
    if (next.is_complete && completeErrors(next).length === 0) {
      next.sync_status = 'pending';
      next.estimated_duration = totalDuration(next.steps);
    } else {
      next.is_complete = false;
      next.sync_status = 'local';
    }

    const others = JSON.stringify(Object.values(db.plans).filter((p) => p.plan_id !== planId)).length;
    if (others + JSON.stringify(next).length > controls.storageLimit)
      fail(507, 'STORAGE_LIMIT', 'Storage on this device is full. Delete old plans to make room.');

    db.plans[planId] = next;
    return { plan_id: planId, version: next.version, is_complete: next.is_complete,
      sync_status: next.sync_status, last_modified: next.last_modified };
  }),

  completePlan: (planId, version) => call((db, user) => {
    const plan = ownPlan(db, user, planId);
    if (plan.sync_status === 'syncing') fail(409, 'PLAN_SYNCING', 'This plan is syncing. Try again in a moment.');
    if (version !== plan.version)
      fail(409, 'VERSION_CONFLICT', 'This plan was changed since you opened it.', { currentVersion: plan.version });
    const errs = completeErrors(plan);
    if (errs.length) fail(422, 'VALIDATION_FAILED', 'Please fix the highlighted fields.', { fields: errs });
    plan.estimated_duration = totalDuration(plan.steps);
    plan.is_complete = true;
    plan.sync_status = 'pending';
    plan.version += 1;
    plan.last_modified = now();
    return { plan_id: planId, version: plan.version, is_complete: true, sync_status: 'pending' };
  }),

  listPlans: () => call((db, user) => Object.values(db.plans)
    .filter((p) => p.owner_id === user.user_id)
    .sort((a, b) => b.last_modified.localeCompare(a.last_modified))
    .map(summary)),

  getPlan: (planId) => call((db, user) => full(ownPlan(db, user, planId))),

  latestDraft: () => call((db, user) => {
    const drafts = Object.values(db.plans)
      .filter((p) => p.owner_id === user.user_id && !p.is_complete)
      .sort((a, b) => b.last_modified.localeCompare(a.last_modified));
    return drafts.length ? full(drafts[0]) : null; // null = 204
  }),

  materials: () => call((db) => clone(db.materials)),

  storage: () => call((db) => {
    const used = JSON.stringify(db.plans).length;
    return { used_bytes: used, limit_bytes: controls.storageLimit,
      percent: Math.round((used / controls.storageLimit) * 1000) / 10 };
  }),

  syncRun: () => call((db, user) => {
    const toSend = Object.values(db.plans).filter((p) => p.owner_id === user.user_id
      && (p.sync_status === 'pending' || p.sync_status === 'interrupted'));
    toSend.forEach((p) => { p.sync_status = 'syncing'; });
    db.last_attempt_at = now();
    // Finish "in the background", like C5.
    setTimeout(() => {
      const d = load();
      toSend.forEach(({ plan_id }) => {
        const p = d.plans[plan_id];
        if (p && p.sync_status === 'syncing') p.sync_status = controls.failSync ? 'interrupted' : 'synced';
      });
      d.last_outcome = controls.failSync ? 'interrupted' : 'success';
      persist(d);
    }, 2500);
    return { started: true };
  }),

  syncStatus: () => call((db, user) => syncStatusCounts(db, user)),
};

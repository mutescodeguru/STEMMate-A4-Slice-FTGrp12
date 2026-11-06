// Session plan editor: form (C1), autosave controller (C2), status indicator (FR-05).
import { api } from './api.js';
import { AUTOSAVE_DELAY_MS, SAVE_RETRY_DELAYS_MS } from './config.js';
import { completeErrors, totalDuration } from './validation.js';
import { statusChip, formatTime } from './status.js';

const $ = (sel, root = document) => root.querySelector(sel);

const els = {
  title: $('#editor-title'),
  form: $('#plan-form'),
  fieldset: $('#plan-fieldset'),
  fTitle: $('#f-title'),
  fLevel: $('#f-level'),
  fSafety: $('#f-safety'),
  fInclusion: $('#f-inclusion'),
  stepList: $('#step-list'),
  stepsCount: $('#steps-count'),
  addStep: $('#add-step'),
  total: $('#total-duration'),
  materialList: $('#material-list'),
  saveStatus: $('#save-status'),
  syncBadge: $('#sync-badge'),
  complete: $('#mark-complete'),
  summary: $('#error-summary'),
  readonly: $('#readonly-note'),
  dialog: $('#conflict-dialog'),
  stepTemplate: $('#step-template'),
  announcer: $('#announcer'),
};

let hooks = { onAuthLost: () => {}, onChanged: () => {} };

const state = {
  planId: null,
  version: 0,
  isComplete: false,
  syncStatus: 'local',
  materialsCatalogue: [],
  timer: null,
  saving: null,          // promise of the save in flight
  dirty: false,          // edits not yet confirmed by the API
  retryIndex: 0,
  retryTimer: null,
};

export function initEditor(h) {
  hooks = { ...hooks, ...h };
  els.form.addEventListener('input', onEdit);
  els.form.addEventListener('change', onEdit);
  els.form.addEventListener('submit', (e) => e.preventDefault());
  els.addStep.addEventListener('click', () => {
    const li = addStepRow({});
    renumber();
    li.querySelector('.step__desc').focus();
    announce(`Step ${stepRows().length} added.`);
    onEdit();
  });
  els.stepList.addEventListener('click', onStepTool);
  els.complete.addEventListener('click', markComplete);

  // Save straight away if the page is hidden or closed (signal loss / power cut, QR-02).
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'hidden' && state.dirty) saveNow();
  });
  window.addEventListener('beforeunload', (e) => {
    if (state.dirty) { saveNow(); e.preventDefault(); e.returnValue = ''; }
  });
}

export async function openPlan(plan, { isNew = false, restoredAt = null } = {}) {
  // Load the catalogue first, so nothing below can overwrite edits made while waiting.
  if (!state.materialsCatalogue.length) {
    try { state.materialsCatalogue = await api.materials(); } catch (e) { if (e.status === 401) return hooks.onAuthLost(); }
  }
  clearTimeout(state.timer);
  clearTimeout(state.retryTimer);
  state.retryTimer = null;
  state.planId = plan.plan_id;
  state.version = plan.version ?? 0;
  state.isComplete = !!plan.is_complete;
  state.syncStatus = plan.sync_status || 'local';
  state.dirty = false;
  state.retryIndex = 0;

  els.fTitle.value = plan.title || '';
  els.fLevel.value = plan.level || '';
  els.fSafety.value = plan.safety_notes || '';
  els.fInclusion.value = plan.inclusion_prompt || '';
  els.stepList.innerHTML = '';
  (plan.steps || []).slice().sort((a, b) => a.step_number - b.step_number).forEach((s) => addStepRow(s));
  if (isNew) addStepRow({});
  renumber();
  renderMaterials(plan.materials || []);
  clearErrors();
  updateHeading();

  if (isNew) setSaveStatus('idle', 'Not saved yet. Saving starts when you type.');
  else if (restoredAt) setSaveStatus('saved', `Draft restored. Last saved ${formatTime(restoredAt)}`);
  else setSaveStatus('saved', `Last saved ${formatTime(plan.last_modified)}`);
  renderSyncState();
}

/** True if there are edits that have not been saved yet. */
export function hasUnsaved() { return state.dirty; }

/** Save any pending edits now (used before leaving the editor). */
export async function flush() {
  clearTimeout(state.timer);
  if (state.dirty) await saveNow();
  if (state.saving) await state.saving.catch(() => {});
}

/** Called when the sync poller sees a new status for the open plan. */
export function refreshSyncStatus(status) {
  if (!state.planId || status === state.syncStatus) return;
  state.syncStatus = status;
  renderSyncState();
}
export function currentPlanId() { return state.planId; }

// ---------- form <-> data ----------

function collect() {
  const steps = stepRows().map((li, i) => {
    const raw = li.querySelector('.step__dur').value.trim();
    return {
      step_number: i + 1,
      description: li.querySelector('.step__desc').value,
      duration: raw === '' ? null : Number(raw), // non-whole numbers are rejected by validation (422)
    };
  });
  const materials = [...els.materialList.querySelectorAll('.material')]
    .filter((li) => li.querySelector('input[type="checkbox"]').checked)
    .map((li) => ({
      material_id: Number(li.dataset.id),
      quantity_required: Math.max(1, parseInt(li.querySelector('.material__qty input').value, 10) || 1),
    }));
  return {
    version: state.version,
    title: els.fTitle.value,
    level: els.fLevel.value,
    safety_notes: els.fSafety.value,
    inclusion_prompt: els.fInclusion.value,
    steps,
    materials,
  };
}

function stepRows() { return [...els.stepList.querySelectorAll('.step')]; }

let stepUid = 0;
function addStepRow(step) {
  const li = els.stepTemplate.content.firstElementChild.cloneNode(true);
  const uid = ++stepUid;
  const desc = li.querySelector('.step__desc');
  const dur = li.querySelector('.step__dur');
  const err = li.querySelector('.step__error');
  desc.id = `step-desc-${uid}`;
  dur.id = `step-dur-${uid}`;
  err.id = `step-err-${uid}`;
  li.querySelector('.step__desc-label').htmlFor = desc.id;
  li.querySelector('.step__dur-label').htmlFor = dur.id;
  desc.setAttribute('aria-describedby', err.id);
  dur.setAttribute('aria-describedby', err.id);
  desc.value = step.description || '';
  dur.value = step.duration ?? '';
  els.stepList.appendChild(li);
  return li;
}

function renumber() {
  const rows = stepRows();
  rows.forEach((li, i) => {
    const n = i + 1;
    li.querySelector('.step__num').textContent = n;
    li.querySelector('.step__desc-label').textContent = `Step ${n} description`;
    li.querySelector('.step__dur-label').textContent = `Step ${n} minutes`;
    const up = li.querySelector('.step__up');
    const down = li.querySelector('.step__down');
    up.setAttribute('aria-label', `Move step ${n} up`);
    down.setAttribute('aria-label', `Move step ${n} down`);
    li.querySelector('.step__remove').setAttribute('aria-label', `Remove step ${n}`);
    up.disabled = i === 0;
    down.disabled = i === rows.length - 1;
  });
  els.stepsCount.textContent = `${rows.length} ${rows.length === 1 ? 'step' : 'steps'}`;
  els.total.textContent = totalDuration(collect().steps);
}

function onStepTool(e) {
  const btn = e.target.closest('button');
  if (!btn) return;
  const li = btn.closest('.step');
  const rows = stepRows();
  const i = rows.indexOf(li);
  if (btn.classList.contains('step__remove')) {
    const next = rows[i + 1] || rows[i - 1];
    li.remove();
    renumber();
    (next ? next.querySelector('.step__desc') : els.addStep).focus();
    announce(`Step ${i + 1} removed.`);
  } else if (btn.classList.contains('step__up') && i > 0) {
    els.stepList.insertBefore(li, rows[i - 1]);
    renumber();
    (li.querySelector('.step__up:not(:disabled)') || li.querySelector('.step__down')).focus();
    announce(`Step moved to position ${i}.`);
  } else if (btn.classList.contains('step__down') && i < rows.length - 1) {
    els.stepList.insertBefore(rows[i + 1], li);
    renumber();
    (li.querySelector('.step__down:not(:disabled)') || li.querySelector('.step__up')).focus();
    announce(`Step moved to position ${i + 2}.`);
  } else return;
  onEdit();
}

function renderMaterials(selected) {
  const chosen = new Map(selected.map((m) => [m.material_id, m.quantity_required]));
  els.materialList.innerHTML = '';
  state.materialsCatalogue.forEach((m) => {
    const li = document.createElement('li');
    li.className = 'material';
    li.dataset.id = m.material_id;
    const cbId = `mat-${m.material_id}`;
    const qtyId = `mat-qty-${m.material_id}`;
    const isOn = chosen.has(m.material_id);
    li.innerHTML = `
      <input type="checkbox" id="${cbId}" ${isOn ? 'checked' : ''}>
      <label for="${cbId}"></label>
      <span class="material__qty" ${isOn ? '' : 'hidden'}>
        <label for="${qtyId}">Qty</label>
        <input id="${qtyId}" type="number" inputmode="numeric" min="1" max="999" value="${isOn ? chosen.get(m.material_id) : 1}" ${isOn ? '' : 'disabled'}>
      </span>`;
    const label = li.querySelector(`label[for="${cbId}"]`);
    label.textContent = m.name;
    if (m.safety_notes && m.safety_notes !== 'None.') {
      const s = document.createElement('span');
      s.className = 'material__safety';
      s.textContent = m.safety_notes;
      label.appendChild(s);
    }
    li.querySelector(`#${qtyId}`).setAttribute('aria-label', `Quantity of ${m.name}`);
    li.querySelector('input[type="checkbox"]').addEventListener('change', (e) => {
      li.querySelector('.material__qty input').disabled = !e.target.checked;
      li.querySelector('.material__qty').hidden = !e.target.checked;
    });
    els.materialList.appendChild(li);
  });
}

function updateHeading() {
  const t = els.fTitle.value.trim();
  els.title.textContent = t ? `Session plan: ${t}` : 'New session plan';
}

// ---------- autosave (C2) ----------

function onEdit() {
  if (els.fieldset.disabled) return;
  state.dirty = true;
  updateHeading();
  els.total.textContent = totalDuration(collect().steps);
  setSaveStatus('pending', 'Editing… will save automatically');
  clearTimeout(state.timer);
  state.timer = setTimeout(saveNow, AUTOSAVE_DELAY_MS);
}

async function saveNow() {
  clearTimeout(state.timer);
  if (state.saving) {               // a save is running: save again once it finishes
    await state.saving.catch(() => {});
    if (!state.dirty) return;
  }
  const body = collect();
  state.dirty = false;
  setSaveStatus('saving', 'Saving…');
  state.saving = api.savePlan(state.planId, body);
  try {
    const res = await state.saving;
    state.version = res.version;
    state.isComplete = res.is_complete;
    state.syncStatus = res.sync_status;
    state.retryIndex = 0;
    clearFieldErrorsQuiet();
    if (!state.dirty) setSaveStatus('saved', `Last saved ${formatTime(res.last_modified)}`);  // status chip already says where it is saved
    renderSyncState();
    hooks.onChanged();
  } catch (err) {
    state.dirty = true;             // edits are still only on screen
    handleSaveError(err);
  } finally {
    state.saving = null;
  }
}

function handleSaveError(err) {
  if (err.status === 401) {
    setSaveStatus('error', 'Signed out. Your last saved draft is safe.');
    hooks.onAuthLost();
    return;
  }
  if (err.status === 409 && err.code === 'VERSION_CONFLICT') { openConflict(err.currentVersion); return; }
  if (err.status === 409 && err.code === 'PLAN_SYNCING') {
    state.syncStatus = 'syncing';
    renderSyncState();
    setSaveStatus('error', 'Not saved: this plan is syncing. Your change will be kept after syncing.');
    scheduleRetry();
    return;
  }
  if (err.status === 422) {
    showFieldErrors(err.fields, { summary: false });
    setSaveStatus('error', 'Not saved: fix the highlighted fields.');
    return;
  }
  if (err.status === 507) {
    setSaveStatus('error', 'Not saved: storage on this device is full. Delete old plans to make room.');
    return;
  }
  // Network failure or server error: keep edits in memory and retry with back-off.
  scheduleRetry();
}

function scheduleRetry() {
  clearTimeout(state.retryTimer);
  const delay = SAVE_RETRY_DELAYS_MS[state.retryIndex];
  if (delay === undefined) {
    state.retryTimer = null;
    setSaveStatus('error', 'Not saved. The app on this device is not responding. Your changes are kept on this screen.', retryButton());
    return;
  }
  state.retryIndex += 1;
  setSaveStatus('error', `Not saved yet. Trying again in ${delay / 1000} seconds…`);
  state.retryTimer = setTimeout(() => { state.retryTimer = null; saveNow(); }, delay);
}

function retryButton() {
  const b = document.createElement('button');
  b.type = 'button';
  b.className = 'link-button';
  b.textContent = 'Try again';
  b.addEventListener('click', () => { state.retryIndex = 0; saveNow(); });
  return b;
}

// ---------- version conflict (Figma 6.5) ----------

function openConflict(currentVersion) {
  setSaveStatus('error', 'Not saved: a newer version of this plan exists.');
  const d = els.dialog;
  const choose = async (e) => {
    const choice = e.target.closest('[data-choice]')?.dataset.choice;
    if (!choice) return;
    d.removeEventListener('click', choose);
    d.close();
    if (choice === 'mine') {
      state.version = currentVersion;
      state.dirty = true;
      await saveNow();
    } else {
      try { await openPlan(await api.getPlan(state.planId)); announce('Saved version loaded.'); }
      catch (err) { if (err.status === 401) hooks.onAuthLost(); }
    }
    els.complete.focus();
  };
  d.addEventListener('click', choose);
  d.showModal();
}

// ---------- mark complete (FR-03 strict rules) ----------

async function markComplete() {
  await flush();
  const plan = collect();
  const errors = completeErrors(plan);
  if (errors.length) { showFieldErrors(errors, { summary: true }); return; }
  if (state.dirty) return; // last save failed; status already explains why
  els.complete.disabled = true;
  try {
    const res = await api.completePlan(state.planId, state.version);
    state.version = res.version;
    state.isComplete = true;
    state.syncStatus = res.sync_status;
    clearErrors();
    renderSyncState();
    setSaveStatus('saved', 'Plan complete.');
    hooks.onChanged();
  } catch (err) {
    if (err.status === 422) showFieldErrors(err.fields, { summary: true });
    else handleSaveError(err);
  } finally {
    renderSyncState();
  }
}

// ---------- errors ----------

function fieldTarget(field) {
  const m = /^steps\[(\d+)\]\.(description|duration|step_number)$/.exec(field);
  if (m) {
    const li = stepRows()[Number(m[1])];
    if (!li) return { input: els.addStep, error: $('#err-steps') };
    return {
      input: li.querySelector(m[2] === 'duration' ? '.step__dur' : '.step__desc'),
      error: li.querySelector('.step__error'),
    };
  }
  if (/^materials\[\d+\]/.test(field)) {   // e.g. materials[0].quantity_required from the server
    return { input: els.materialList.querySelector('input'), error: $('#err-materials') };
  }
  const map = {
    title: [els.fTitle, '#err-title'],
    level: [els.fLevel, '#err-level'],
    safety_notes: [els.fSafety, '#err-safety_notes'],
    inclusion_prompt: [els.fInclusion, '#err-inclusion_prompt'],
    steps: [els.addStep, '#err-steps'],
    materials: [els.materialList.querySelector('input'), '#err-materials'],
  };
  const hit = map[field];
  return hit ? { input: hit[0], error: $(hit[1]) } : null;
}

function showFieldErrors(errors, { summary }) {
  clearErrors();
  const list = els.summary.querySelector('ul');
  errors.forEach((e) => {
    const t = fieldTarget(e.field);
    if (t && t.error) {
      t.error.textContent = t.error.hidden ? e.message : `${t.error.textContent} ${e.message}`;
      t.error.hidden = false;
    }
    if (t && t.input && t.input.matches('input, select, textarea')) t.input.setAttribute('aria-invalid', 'true');
    if (summary) {
      const li = document.createElement('li');
      const a = document.createElement('a');
      a.href = '#';
      a.textContent = e.message;
      a.addEventListener('click', (ev) => { ev.preventDefault(); t?.input?.focus(); });
      li.appendChild(a);
      list.appendChild(li);
    }
  });
  if (summary) {
    els.summary.hidden = false;
    els.summary.focus();
  }
}

function clearErrors() {
  els.summary.hidden = true;
  els.summary.querySelector('ul').innerHTML = '';
  clearFieldErrorsQuiet();
}
function clearFieldErrorsQuiet() {
  document.querySelectorAll('#view-editor .field-error').forEach((p) => { p.hidden = true; p.textContent = ''; });
  document.querySelectorAll('#view-editor [aria-invalid]').forEach((x) => x.removeAttribute('aria-invalid'));
}

// ---------- status rendering ----------

function setSaveStatus(kind, text, extra) {
  const icons = { saved: '✓', saving: '…', error: '⚠', pending: '✎', idle: '' };
  els.saveStatus.className = `save-status save-status--${kind}`;
  els.saveStatus.querySelector('.save-status__icon').textContent = icons[kind] || '';
  const t = els.saveStatus.querySelector('.save-status__text');
  t.textContent = text;
  if (extra) { t.append(' '); t.appendChild(extra); }
}

function renderSyncState() {
  const syncing = state.syncStatus === 'syncing';
  els.fieldset.disabled = syncing;
  els.addStep.disabled = syncing;
  els.readonly.hidden = !syncing;
  els.syncBadge.innerHTML = '';
  els.syncBadge.appendChild(statusChip(state.syncStatus));
  if (state.isComplete) {
    els.complete.disabled = true;
    els.complete.textContent = 'Plan is complete';
  } else {
    els.complete.disabled = syncing;
    els.complete.textContent = 'Mark complete';
  }
}

function announce(msg) {
  els.announcer.textContent = '';
  setTimeout(() => { els.announcer.textContent = msg; }, 50);
}

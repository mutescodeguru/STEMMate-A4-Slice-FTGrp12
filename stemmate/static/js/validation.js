// Client-side validation that mirrors the API contract (FR-03).
// The backend (C4) is the authority; this only gives faster feedback.
// Pure functions, no DOM, so P5 can unit test them with Jest.
import { LIMITS, LEVELS } from './config.js';

const isBlank = (v) => v === undefined || v === null || String(v).trim() === '';

/** Lenient rules used for every autosave. Returns [{field, message}]. */
export function draftErrors(plan) {
  const errors = [];
  if (!isBlank(plan.title) && plan.title.length > LIMITS.title)
    errors.push({ field: 'title', message: `Keep the title under ${LIMITS.title} characters.` });
  if (!isBlank(plan.level) && !LEVELS.includes(plan.level))
    errors.push({ field: 'level', message: 'Choose a level from the list.' });
  if (!isBlank(plan.safety_notes) && plan.safety_notes.length > LIMITS.safety_notes)
    errors.push({ field: 'safety_notes', message: `Keep safety notes under ${LIMITS.safety_notes} characters.` });
  if (!isBlank(plan.inclusion_prompt) && plan.inclusion_prompt.length > LIMITS.inclusion_prompt)
    errors.push({ field: 'inclusion_prompt', message: `Keep the inclusion prompt under ${LIMITS.inclusion_prompt} characters.` });

  const steps = plan.steps || [];
  if (steps.length > LIMITS.steps)
    errors.push({ field: 'steps', message: `A plan can have at most ${LIMITS.steps} steps.` });
  const seen = new Set();
  steps.forEach((s, i) => {
    if (seen.has(s.step_number))
      errors.push({ field: `steps[${i}].step_number`, message: 'Step numbers must not repeat.' });
    seen.add(s.step_number);
    if (!isBlank(s.description) && s.description.length > LIMITS.step_description)
      errors.push({ field: `steps[${i}].description`, message: `Keep step ${i + 1} under ${LIMITS.step_description} characters.` });
    if (s.duration !== null && s.duration !== undefined && !isValidDuration(s.duration))
      errors.push({ field: `steps[${i}].duration`, message: `Step ${i + 1}: use whole minutes from ${LIMITS.duration_min} to ${LIMITS.duration_max}.` });
  });
  return errors;
}

/** Strict rules checked before "Mark complete". Includes the draft rules. */
export function completeErrors(plan) {
  const errors = draftErrors(plan);
  if (isBlank(plan.title)) errors.push({ field: 'title', message: 'Add a title.' });
  if (isBlank(plan.level)) errors.push({ field: 'level', message: 'Choose a level.' });
  if (isBlank(plan.safety_notes)) errors.push({ field: 'safety_notes', message: 'Add safety notes.' });
  if (isBlank(plan.inclusion_prompt)) errors.push({ field: 'inclusion_prompt', message: 'Add at least one inclusion prompt.' });

  const steps = plan.steps || [];
  if (steps.length === 0) errors.push({ field: 'steps', message: 'Add at least one step.' });
  steps.forEach((s, i) => {
    if (isBlank(s.description))
      errors.push({ field: `steps[${i}].description`, message: `Step ${i + 1} needs a description.` });
    if (s.duration === null || s.duration === undefined)
      errors.push({ field: `steps[${i}].duration`, message: `Step ${i + 1} needs a time in minutes.` });
  });
  if (!plan.materials || plan.materials.length === 0)
    errors.push({ field: 'materials', message: 'Choose at least one material.' });

  // One message per field is enough.
  const byField = new Map();
  errors.forEach((e) => { if (!byField.has(e.field)) byField.set(e.field, e); });
  return [...byField.values()];
}

export function isValidDuration(d) {
  return Number.isInteger(d) && d >= LIMITS.duration_min && d <= LIMITS.duration_max;
}

export function totalDuration(steps) {
  return (steps || []).reduce((sum, s) => sum + (Number.isInteger(s.duration) ? s.duration : 0), 0);
}

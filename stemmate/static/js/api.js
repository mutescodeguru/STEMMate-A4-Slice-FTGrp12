// API client for the local Flask API (contract: STEMMate_P1_API_Contract).
// Same function names in mock-api.js, so the UI never knows which one it uses.
import { USE_MOCK } from './config.js';
import * as mock from './mock-api.js';

export class ApiError extends Error {
  constructor({ status = 0, code = 'NETWORK', message, fields = [], currentVersion = null } = {}) {
    super(message || 'Could not reach the app.');
    this.status = status;          // 0 = network failure (local app not running/unreachable)
    this.code = code;
    this.fields = fields;
    this.currentVersion = currentVersion;
  }
  get isNetwork() { return this.status === 0 || (this.status >= 500 && this.status !== 507); }
}

async function request(method, path, body) {
  let res;
  try {
    res = await fetch(path, {
      method,
      credentials: 'same-origin',
      headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
  } catch {
    throw new ApiError({ status: 0, code: 'NETWORK', message: 'Could not reach the app on this device.' });
  }
  if (res.status === 204) return null;
  let data = null;
  try { data = await res.json(); } catch { /* empty or non-JSON body */ }
  if (!res.ok) {
    const err = (data && data.error) || {};
    throw new ApiError({
      status: res.status,
      code: err.code || `HTTP_${res.status}`,
      message: err.message || 'Something went wrong.',
      fields: err.fields || [],
      currentVersion: (data && (data.current_version ?? err.current_version)) ?? null,
    });
  }
  return data;
}

const real = {
  login: (username, password) => request('POST', '/api/auth/login', { username, password }),
  logout: () => request('POST', '/api/auth/logout'),
  me: () => request('GET', '/api/auth/me'),
  savePlan: (planId, body) => request('PUT', `/api/plans/${encodeURIComponent(planId)}`, body),
  completePlan: (planId, version) => request('POST', `/api/plans/${encodeURIComponent(planId)}/complete`, { version }),
  listPlans: () => request('GET', '/api/plans'),
  getPlan: (planId) => request('GET', `/api/plans/${encodeURIComponent(planId)}`),
  latestDraft: () => request('GET', '/api/drafts/latest'),
  materials: () => request('GET', '/api/materials'),
  storage: () => request('GET', '/api/storage'),
  syncRun: () => request('POST', '/api/sync/run'),
  syncStatus: () => request('GET', '/api/sync/status'),
};

mock.setErrorClass(ApiError);

export const api = USE_MOCK ? mock.api : real;
export const usingMock = USE_MOCK;

/** plan_id is created in the browser (contract: UUID). */
export function newPlanId() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}

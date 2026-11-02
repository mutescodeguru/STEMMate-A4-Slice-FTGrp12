// Frontend settings (P4).
//
// Mock mode lets the UI run before P3's backend exists.
//   ?mock=1  -> always use the mock API (browser-only, fake data)
//   ?mock=0  -> always use the real Flask API
//   neither  -> real API when served by Flask on port 5000, mock otherwise
const params = new URLSearchParams(location.search);

export const USE_MOCK =
  params.get('mock') === '1' ? true :
  params.get('mock') === '0' ? false :
  location.port !== '5000';

export const AUTOSAVE_DELAY_MS = 1000;        // C2: save 1 s after the last edit (QR-02 target: 2 s)
export const SAVE_RETRY_DELAYS_MS = [2000, 4000, 8000];
export const SYNC_POLL_MS = 5000;             // contract: UI may poll /api/sync/status every 5 s

// Level values agreed with P2 (logical data model, draft v2).
export const LEVELS = ['lower primary', 'upper primary', 'junior secondary', 'senior secondary'];

// Draft limits from the API contract (lenient rules).
export const LIMITS = {
  title: 120,
  safety_notes: 2000,
  inclusion_prompt: 1000,
  steps: 30,
  step_description: 500,
  duration_min: 1,
  duration_max: 480,
};

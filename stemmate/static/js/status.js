// Sync status display (FR-05). Every status has its own text AND icon,
// so meaning never depends on colour alone (AR-01).

const ICONS = {
  local: '<svg aria-hidden="true" viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2"/><path d="M8 4v5h8V4M8 20v-6h8v6"/></svg>',
  pending: '<svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>',
  syncing: '<svg aria-hidden="true" class="spin" viewBox="0 0 24 24"><path d="M21 12a9 9 0 1 1-6.2-8.6"/></svg>',
  interrupted: '<svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 3 2 21h20L12 3z"/><path d="M12 10v5M12 18h.01"/></svg>',
  synced: '<svg aria-hidden="true" viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/></svg>',
};

// UI text from the API contract's sync status table.
const LABELS = {
  local: 'Saved on this device',
  pending: 'Saved, waiting to sync',
  syncing: 'Syncing…',
  interrupted: 'Sync interrupted, will retry',
  synced: 'Synced',
};

export const SYNC_STATUSES = Object.keys(LABELS);

export function statusLabel(status) {
  return LABELS[status] || 'Unknown status';
}

export function statusChip(status) {
  const span = document.createElement('span');
  span.className = `status status--${SYNC_STATUSES.includes(status) ? status : 'local'}`;
  span.innerHTML = `${ICONS[status] || ICONS.local}<span>${statusLabel(status)}</span>`;
  return span;
}

export function formatTime(iso) {
  if (!iso) return '';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  const today = new Date();
  const time = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  return d.toDateString() === today.toDateString()
    ? time
    : `${d.toLocaleDateString([], { day: 'numeric', month: 'short' })}, ${time}`;
}

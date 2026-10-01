// In-app replacement for window.confirm / window.prompt: same "await it" ergonomics, but
// rendered by <DialogHost /> in the app's own style instead of the browser's grey box.
let listener = null;

const open = (dialog) => new Promise((resolve) => {
  if (!listener) {
    // Host not mounted (should not happen): fall back rather than silently doing nothing.
    resolve(dialog.kind === 'prompt' ? window.prompt(dialog.message, dialog.defaultValue) : window.confirm(dialog.message));
    return;
  }
  listener({ ...dialog, resolve });
});

/** Resolves true (confirmed) or false (cancelled). */
export const confirmDialog = ({ title = 'Xác nhận', message, confirmLabel = 'Đồng ý', cancelLabel = 'Hủy', danger = false }) => (
  open({ kind: 'confirm', title, message, confirmLabel, cancelLabel, danger })
);

/** Resolves the entered text, or null if cancelled. */
export const promptDialog = ({ title = 'Nhập thông tin', message = '', defaultValue = '', confirmLabel = 'Lưu', cancelLabel = 'Hủy', placeholder = '' }) => (
  open({ kind: 'prompt', title, message, defaultValue, confirmLabel, cancelLabel, placeholder })
);

export const subscribeDialogs = (fn) => {
  listener = fn;
  return () => { if (listener === fn) listener = null; };
};

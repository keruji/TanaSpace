const dialog = document.querySelector('[role="dialog"][aria-modal="true"]');
if (dialog) {
  document.querySelector('.app-header')?.setAttribute('inert', '');
  document.querySelector('.sidebar')?.setAttribute('inert', '');
  document.querySelector('#main')?.setAttribute('inert', '');
  const close = dialog.querySelector('.modal-close');
  const focusable = () => Array.from(dialog.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled])'));
  (dialog.querySelector('.field-errors + input') || dialog.querySelector('input:not([type="hidden"]), select, textarea') || close)?.focus();
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') { close?.click(); }
    if (event.key !== 'Tab') return;
    const controls = focusable();
    if (!controls.length) return;
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
    else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
  });
}

// Persistent appearance, drawer and account menu. No content requests live here.
export function initWorkspaceShell() {
  const body = document.body;
  const sidebar = document.querySelector('#workspace-sidebar');
  const menu = document.querySelector('#account-menu');
  const account = document.querySelector('#account-toggle');
  const helpToggle = document.querySelector('[data-help-toggle]');
  const helpMenu = document.querySelector('[data-help-menu]');
  const mobile = matchMedia('(max-width: 640px)');
  const toggles = [...document.querySelectorAll('[data-sidebar-toggle]')];
  let desktop = document.documentElement.dataset.sidebar || (innerWidth > 800 ? 'expanded' : 'collapsed');
  let drawer = false;
  const controls = root => [...root.querySelectorAll('a[href], button:not([disabled]), input:not([disabled])')].filter(el => el.getClientRects().length);

  function closeMenu(restore = false) {
    const hadFocus = menu.contains(document.activeElement);
    menu.hidden = true;
    menu.inert = true;
    account.setAttribute('aria-expanded', 'false');
    helpMenu.hidden = true;
    helpToggle.setAttribute('aria-expanded', 'false');
    if (restore || hadFocus) account.focus({ preventScroll: true });
  }
  function setDrawer(open, restore = false) {
    drawer = open;
    body.classList.toggle('drawer-open', open);
    document.querySelector('.drawer-scrim').hidden = !open;
    const modalOpen = Boolean(document.querySelector('#modal-host [role=dialog]'));
    document.querySelector('.app-header').inert = open || modalOpen;
    document.querySelector('#workspace-view').inert = open;
    sidebar.toggleAttribute('inert', modalOpen || (mobile.matches && !open));
    if (open) {
      closeMenu();
      sidebar.setAttribute('role', 'dialog');
      sidebar.setAttribute('aria-modal', 'true');
      controls(sidebar)[0]?.focus();
    } else {
      sidebar.removeAttribute('role');
      sidebar.removeAttribute('aria-modal');
      if (restore) toggles[0].focus();
    }
    updateButtons();
  }
  function updateButtons() {
    const expanded = mobile.matches ? drawer : desktop === 'expanded';
    for (const button of toggles) {
      button.setAttribute('aria-expanded', String(expanded));
      button.setAttribute('aria-label', `${expanded ? 'Collapse' : 'Expand'} navigation`);
    }
  }
  function apply() {
    document.documentElement.dataset.sidebar = desktop;
    setDrawer(false);
    document.querySelector('[data-sidebar-close].drawer-close').hidden = !mobile.matches;
  }
  for (const button of toggles) {
    button.hidden = false;
    button.addEventListener('click', () => {
      if (mobile.matches) return setDrawer(!drawer, true);
      desktop = desktop === 'expanded' ? 'collapsed' : 'expanded';
      try { localStorage.setItem('tanaspace-sidebar', desktop); } catch (_) { /* visit-only fallback */ }
      apply();
    });
  }
  document.querySelectorAll('[data-sidebar-close]').forEach(el => el.addEventListener('click', () => setDrawer(false, true)));
  account.hidden = false;
  closeMenu();
  helpToggle.addEventListener('click', () => {
    helpMenu.hidden = !helpMenu.hidden;
    helpToggle.setAttribute('aria-expanded', String(!helpMenu.hidden));
  });
  function openMenu({ keyboard = false, last = false } = {}) {
    menu.hidden = false;
    menu.inert = false;
    account.setAttribute('aria-expanded', 'true');
    const items = controls(menu);
    if (keyboard) (last ? items.at(-1) : items[0])?.focus();
  }
  account.addEventListener('click', () => menu.hidden ? openMenu() : closeMenu(true));
  account.addEventListener('keydown', event => {
    if (['ArrowDown', 'ArrowUp'].includes(event.key)) { event.preventDefault(); openMenu({ keyboard: true, last: event.key === 'ArrowUp' }); }
  });
  menu.addEventListener('keydown', event => {
    const items = controls(menu), index = items.indexOf(document.activeElement);
    let next;
    if (event.key === 'ArrowDown') next = (index + 1) % items.length;
    if (event.key === 'ArrowUp') next = (index - 1 + items.length) % items.length;
    if (event.key === 'Home') next = 0;
    if (event.key === 'End') next = items.length - 1;
    if (next !== undefined) { event.preventDefault(); items[next].focus(); }
    if (event.key === 'Tab') closeMenu();
  });
  document.addEventListener('click', event => {
    if (!event.target.closest('.account-control')) closeMenu();
  });
  document.addEventListener('keydown', event => {
    if (event.key === 'Escape' && !menu.hidden) { event.preventDefault(); closeMenu(true); }
    if (drawer && event.key === 'Escape') { event.preventDefault(); setDrawer(false, true); }
    if (drawer && event.key === 'Tab') {
      const items = controls(sidebar), first = items[0], last = items.at(-1);
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  for (const link of sidebar.querySelectorAll('[data-nav]')) {
    const position = () => {
      const rect = link.getBoundingClientRect(), tip = link.querySelector('.nav-tooltip');
      tip.style.left = `${rect.right + 8}px`; tip.style.top = `${rect.top + rect.height / 2}px`;
    };
    link.addEventListener('mouseenter', position); link.addEventListener('focus', position);
  }
  mobile.addEventListener('change', apply);
  window.addEventListener('storage', event => {
    if (event.key === 'tanaspace-sidebar' && ['expanded', 'collapsed'].includes(event.newValue)) { desktop = event.newValue; apply(); }
  });
  body.classList.add('workspace-ready');
  apply();
  return { closeOverlays() { closeMenu(); setDrawer(false); } };
}

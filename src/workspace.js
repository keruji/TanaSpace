import htmx from 'htmx.org';
import { initWorkspaceShell } from './workspace-shell.js';
import { initSelects, closeSelects } from './select.js';

// HTMX handles transport and HTML swaps. This controller owns URL history so
// dirty forms can reject Back/Forward before a fragment is replaced.
export function initWorkspace() {
  const view = document.querySelector('#workspace-view');
  if (!view) return;
  htmx.config.historyCacheSize = 0;
  htmx.config.historyRestoreAsHxRequest = false;
  htmx.config.allowEval = false;
  htmx.config.allowScriptTags = false;
  htmx.config.timeout = 30000;
  const shell = initWorkspaceShell();
  const status = document.querySelector('#workspace-status');
  const baseline = new WeakMap();
  const pending = new Map();
  const outcomes = new Map();
  const swapCallbacks = new Map();
  let generation = 0, requestId = 0, writing = false, restoring = false, approvedPop = false, allowUnload = false;
  let state = history.state?.tana || { index: 0, url: location.pathname + location.search, origin: null, scroll: 0 };
  let opener;
  const currentURL = () => location.pathname + location.search;
  const main = () => document.querySelector('#main');
  const dialog = () => document.querySelector('#modal-host [role="dialog"]');
  const formValue = form => JSON.stringify([...new FormData(form)].filter(([key]) => !['csrfmiddlewaretoken', 'return_to'].includes(key)));
  function message(text = '') { status.textContent = text; status.hidden = !text; }
  function dirty() { return [...view.querySelectorAll('[data-dirty-check]')].some(form => baseline.has(form) && baseline.get(form) !== formValue(form)); }
  function mayLeave() { return !writing && (!dirty() || confirm('Discard your unsaved changes?')); }
  function remember() {
    state = { ...state, scroll: main()?.scrollTop || 0 };
    history.replaceState({ ...history.state, tana: state }, '', currentURL());
  }
  function commit(url, { replace = false, origin = null } = {}) {
    state = { index: replace ? state.index : state.index + 1, url, origin, scroll: main()?.scrollTop || 0 };
    history[replace ? 'replaceState' : 'pushState']({ tana: state }, '', url);
  }
  function windowFocus() {
    const win = dialog();
    if (!win) return;
    const error = win.querySelector('.form-field:has(.field-errors)');
    (error?.querySelector('input, select, textarea') || win.querySelector('input:not([type="hidden"]), select, textarea') || win.querySelector('.modal-close') || win).focus();
  }
  function hydrate({ focus = false, resetForms = false } = {}) {
    initSelects(view);
    for (const form of view.querySelectorAll('[data-dirty-check]')) {
      if (!baseline.has(form) || resetForms) baseline.set(form, formValue(form));
    }
    document.querySelector('#modal-host').inert = false;
    const win = dialog();
    if (!win && main()?.dataset.pageTitle) document.title = main().dataset.pageTitle;
    document.querySelector('.app-header').inert = Boolean(win);
    document.querySelector('.sidebar').inert = Boolean(win) || (innerWidth <= 640 && !document.body.classList.contains('drawer-open'));
    if (main()) main().inert = Boolean(win);
    for (const link of document.querySelectorAll('[data-nav]')) {
      const active = link.dataset.nav === main()?.dataset.activeNav;
      link.classList.toggle('active', active);
      if (active) link.setAttribute('aria-current', 'page'); else link.removeAttribute('aria-current');
    }
    const name = view.querySelector('[data-display-name]');
    if (name) document.querySelector('#account-display-name').textContent = name.textContent;
    if (focus) win ? windowFocus() : main()?.focus({ preventScroll: true });
  }
  function supersede() {
    closeSelects();
    generation++;
    for (const { xhr, method } of pending.values()) if (method === 'get') xhr.abort();
  }
  async function request(url, { target = 'workspace-view', method = 'GET', values, origin = '', onSwap } = {}) {
    const token = String(++requestId), ownGeneration = generation;
    if (onSwap) swapCallbacks.set(token, onSwap);
    try {
      await htmx.ajax(method, url, {
        source: document.querySelector(`#${target}`), target: `#${target}`,
        swap: target === 'main' ? 'outerHTML' : 'innerHTML', values,
        headers: { 'X-Workspace-Token': token, 'X-Workspace-Generation': String(ownGeneration), 'X-Workspace-Return': origin },
      });
      const success = outcomes.get(token);
      outcomes.delete(token);
      swapCallbacks.delete(token);
      return ownGeneration === generation && success === true;
    } catch (_) {
      outcomes.delete(token);
      swapCallbacks.delete(token);
      if (ownGeneration === generation) message(method === 'POST' ? 'Could not confirm the save. Check your records before trying again.' : 'Unable to load this content. Please try again.');
      return false;
    }
  }
  async function navigate(url, { replace = false, entry = null, confirmed = false } = {}) {
    if (!confirmed && !mayLeave()) return;
    remember(); shell.closeOverlays(); supersede(); message('Loading…');
    const navigationGeneration = generation;
    view.inert = true; view.setAttribute('aria-busy', 'true');
    const success = await request(url, { onSwap() {
      if (entry) state = entry; else commit(url, { replace });
    } });
    if (navigationGeneration !== generation) return;
    view.inert = false; view.removeAttribute('aria-busy');
    if (!success) return;
    if (main()) main().scrollTop = entry?.scroll || 0;
    hydrate({ focus: true, resetForms: true }); message();
  }
  async function openWindow(url, { entry = null, replace = false, confirmed = false } = {}) {
    if (!entry && !confirmed && !mayLeave()) return;
    if (!entry) remember();
    shell.closeOverlays(); supersede();
    const origin = entry?.origin || state.origin || { url: main().dataset.pageUrl, index: dialog() ? null : state.index, scroll: main().scrollTop };
    message('Loading window…');
    const navigationGeneration = generation;
    const host = document.querySelector('#modal-host');
    host.inert = true; host.setAttribute('aria-busy', 'true');
    const success = await request(url, { target: 'modal-host', origin: origin.url, onSwap() {
      if (entry) state = entry; else commit(url, { origin, replace });
    } });
    if (navigationGeneration !== generation) return;
    host.inert = false; host.removeAttribute('aria-busy');
    if (!success) {
      if (entry && navigationGeneration === generation) recoverHistory(entry);
      return;
    }
    hydrate({ focus: true, resetForms: true }); message();
  }
  async function closeWindow({ confirmed = false, toOrigin = false, fallbackURL = null } = {}) {
    if (!confirmed && !mayLeave()) return;
    if (state.origin && state.index > 0 && (!toOrigin || Number.isInteger(state.origin.index))) {
      approvedPop = true;
      history.go(toOrigin ? state.origin.index - state.index : -1);
    } else if (fallbackURL) {
      // Direct window visits have no tracked predecessor. Replace the current
      // entry with the link's detail URL instead of leaving the app or adding a loop.
      await openWindow(fallbackURL, { replace: true, confirmed: true });
    } else {
      await navigate(dialog()?.dataset.returnUrl || main().dataset.pageUrl, { replace: true, confirmed: true });
    }
  }
  async function refreshBase() {
    const position = main()?.scrollTop || 0;
    const success = await request(main().dataset.pageUrl, { target: 'main' });
    if (!success) return false;
    if (main()) main().scrollTop = position;
    hydrate();
    return success;
  }

  document.addEventListener('htmx:beforeRequest', event => {
    const { xhr, requestConfig } = event.detail;
    const token = requestConfig.headers['X-Workspace-Token'];
    if (token) pending.set(token, { xhr, method: requestConfig.verb });
  });
  document.addEventListener('htmx:beforeSwap', event => {
    closeSelects();
    const { xhr, requestConfig } = event.detail;
    const sent = requestConfig?.headers['X-Workspace-Generation'];
    if (sent !== undefined && Number(sent) !== generation) { event.detail.shouldSwap = false; event.detail.ignoreTitle = true; }
    // Commit route state before the returned controls become interactive.
    // Waiting for the request promise leaves a race with rapid subsequent clicks.
    const token = requestConfig?.headers['X-Workspace-Token'];
    if (event.detail.shouldSwap && xhr.status >= 200 && xhr.status < 300) {
      swapCallbacks.get(token)?.();
      swapCallbacks.delete(token);
    }
    // HTTP failures never replace the current form/list with an error document.
    if (xhr.status >= 400) {
      event.detail.shouldSwap = false;
      message(xhr.status === 403 ? 'Your session or security token expired. Reload before trying again.' : xhr.status === 429 ? 'Too many requests. Please wait and try again.' : 'Unable to load this content. It may no longer be available.');
    }
  });
  document.addEventListener('htmx:afterRequest', event => {
    const token = event.detail.requestConfig?.headers['X-Workspace-Token'];
    if (token) {
      pending.delete(token);
      outcomes.set(token, event.detail.successful && event.detail.xhr.status >= 200 && event.detail.xhr.status < 300);
    }
  });

  document.addEventListener('click', event => {
    if (!(event.target instanceof Element)) return;
    const link = event.target.closest('a[href]');
    if (!link || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey || link.target || link.hasAttribute('download')) return;
    const url = new URL(link.href);
    if (url.origin !== location.origin || !(url.pathname === '/tana' || url.pathname.startsWith('/tana/')) || url.hash) return;
    event.preventDefault();
    if (link.hasAttribute('data-window-close')) { closeWindow(); return; }
    if (link.hasAttribute('data-window-back')) { closeWindow({ fallbackURL: url.pathname + url.search }); return; }
    if (link.hasAttribute('data-window')) { opener = link; openWindow(url.pathname + url.search); }
    else navigate(url.pathname + url.search);
  });
  document.addEventListener('submit', async event => {
    const form = event.target;
    if (form.hasAttribute('data-logout')) {
      if (!mayLeave()) event.preventDefault();
      else allowUnload = true;
      return;
    }
    if (form.hasAttribute('data-workspace-search')) {
      event.preventDefault();
      const url = new URL(form.action); url.search = new URLSearchParams(new FormData(form));
      await navigate(url.pathname + url.search); return;
    }
    if (!form.hasAttribute('data-async-form')) return;
    event.preventDefault();
    if (writing) return;
    writing = true; message('Saving…');
    const oldBaseline = baseline.get(form);
    const values = Object.fromEntries(new FormData(form));
    const buttons = [...form.querySelectorAll('button[type="submit"]')]; buttons.forEach(el => el.disabled = true);
    const target = form.closest('#modal-host') ? 'modal-host' : 'workspace-view';
    const submissionRegion = document.getElementById(target);
    submissionRegion.inert = true; submissionRegion.setAttribute('aria-busy', 'true');
    const origin = state.origin?.url || dialog()?.dataset.returnUrl || main().dataset.pageUrl;
    let result;
    const capture = event => {
      if (event.detail.requestConfig.verb === 'post') result = event.detail.xhr;
    };
    document.addEventListener('htmx:afterRequest', capture);
    const ok = await request(form.action, { method: 'POST', values, target, origin });
    document.removeEventListener('htmx:afterRequest', capture);
    writing = false; buttons.forEach(el => el.disabled = false);
    submissionRegion.inert = false; submissionRegion.removeAttribute('aria-busy');
    if (!ok || !result || result.status >= 400) return;
    const changed = result.getResponseHeader('X-Workspace-Changed');
    const destination = result.getResponseHeader('X-Workspace-URL');
    if (destination) {
      const url = new URL(destination, location.origin); url.searchParams.set('return_to', origin);
      commit(url.pathname + url.search, { replace: true, origin: state.origin });
    }
    hydrate({ focus: true, resetForms: Boolean(changed) });
    if (!changed) {
      // A bound validation response must remain dirty relative to the pre-edit form.
      const replacement = view.querySelector('[data-dirty-check]');
      if (replacement && oldBaseline !== undefined) baseline.set(replacement, oldBaseline);
      message('Please check the highlighted fields.'); return;
    }
    if (result.getResponseHeader('X-Workspace-Close') === 'true') {
      await closeWindow({ confirmed: true, toOrigin: true });
    } else if (target === 'modal-host' && !await refreshBase()) {
      message('Saved, but the list could not refresh. Reload it before making more changes.');
      return;
    }
    message('Saved.');
  });
  document.addEventListener('keydown', event => {
    const win = dialog();
    if (!win) return;
    if (event.key === 'Escape') { event.preventDefault(); closeWindow(); }
    if (event.key === 'Tab') {
      const items = [...win.querySelectorAll('a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled])')].filter(el => el.getClientRects().length);
      const first = items[0], last = items.at(-1);
      if (!first) { event.preventDefault(); win.focus(); }
      else if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
  });
  window.addEventListener('beforeunload', event => { if (!allowUnload && (dirty() || writing)) { event.preventDefault(); event.returnValue = ''; } });
  window.addEventListener('popstate', async event => {
    if (restoring) { restoring = false; return; }
    const entry = event.state?.tana;
    if (!entry) { location.reload(); return; }
    const approved = approvedPop; approvedPop = false;
    if (!approved && !mayLeave()) { restoring = true; history.go(state.index - entry.index); return; }
    supersede(); shell.closeOverlays();
    view.inert = false; view.removeAttribute('aria-busy');
    const navigationGeneration = generation;
    if (!entry.origin && state.origin && entry.url === state.origin.url && main()?.dataset.pageUrl === entry.url) {
      document.querySelector('#modal-host').replaceChildren(); state = entry;
      hydrate(); main().scrollTop = entry.scroll || 0;
      await refreshBase();
      if (navigationGeneration !== generation) return;
      const restored = opener?.isConnected ? opener : [...view.querySelectorAll('a[href]')].find(link => link.href === opener?.href);
      (restored || main()).focus({ preventScroll: true });
    } else if (entry.origin && main()?.dataset.pageUrl === entry.origin.url) {
      await openWindow(entry.url, { entry });
    } else {
      // Do not save the old DOM's scroll under the destination history entry.
      const success = await request(entry.url, { onSwap() { state = entry; } });
      if (success) { hydrate({ focus: true, resetForms: true }); main().scrollTop = entry.scroll || 0; }
      else if (navigationGeneration === generation) recoverHistory(entry);
    }
  });
  function recoverHistory(entry) {
    // Deleted records and failed history requests must not leave a stale URL
    // pointing at unrelated visible content. The mounted collection is safe.
    document.querySelector('#modal-host').replaceChildren();
    state = { index: entry.index, url: main().dataset.pageUrl, origin: null, scroll: main().scrollTop };
    history.replaceState({ tana: state }, '', state.url);
    hydrate({ focus: true });
    message('That content is unavailable. Your previous page has been restored.');
  }
  history.replaceState({ tana: state }, '', currentURL());
  hydrate({ focus: Boolean(dialog()) });
}

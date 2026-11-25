import htmx from 'htmx.org';
import { initWorkspaceShell } from './workspace-shell.js';
import { initSelects, closeSelects } from './select.js';
import { initSearchBuilder } from './search-builder.js';

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
  let fieldSequence = 0, fieldXHR;
  const fieldStates = new WeakMap(), fieldCaches = new WeakMap();
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
  function commit(url, { replace = false, origin = null, previousWindow = null, closeToOrigin = false } = {}) {
    state = { index: replace ? state.index : state.index + 1, url, origin, previousWindow, closeToOrigin, scroll: main()?.scrollTop || 0 };
    history[replace ? 'replaceState' : 'pushState']({ tana: state }, '', url);
  }
  function windowFocus() {
    const win = dialog();
    if (!win) return;
    const error = win.querySelector('.form-field:has(.field-errors)');
    (error?.querySelector('input, select, textarea, summary') || win.querySelector('input:not([type="hidden"]):not([type="radio"]):not([data-icon-search]), select, textarea') || win.querySelector('.modal-close') || win).focus();
  }
  function closeIconPicker(picker, restoreFocus = false) {
    const panel = picker.querySelector('.type-icon-panel');
    if (picker.dataset.floating && panel.matches(':popover-open')) panel.hidePopover();
    picker.open = false;
    if (restoreFocus) picker.querySelector('summary').focus({ preventScroll: true });
  }
  function showIconPicker(picker) {
    const panel = picker.querySelector('.type-icon-panel');
    if (picker.dataset.floating) {
      const rect = picker.querySelector('summary').getBoundingClientRect();
      panel.style.left = '12px';
      panel.style.top = '0px';
      panel.style.maxHeight = 'none';
      panel.style.visibility = 'hidden';
      panel.showPopover();
      const panelRect = panel.getBoundingClientRect();
      panel.style.left = `${Math.max(12, Math.min(rect.left, innerWidth - panelRect.width - 12))}px`;
      const desired = panelRect.height;
      const below = innerHeight - rect.bottom - 12, above = rect.top - 12;
      const up = below < Math.min(desired, 160) && above > below;
      panel.style.maxHeight = `${Math.max(40, Math.min(desired, up ? above : below))}px`;
      const height = panel.getBoundingClientRect().height;
      panel.style.top = `${up ? rect.top - height - 4 : rect.bottom + 4}px`;
      panel.style.visibility = '';
    }
    picker.querySelector('[data-icon-search]').focus({ preventScroll: true });
  }
  function hydrate({ focus = false, resetForms = false } = {}) {
    initSearchBuilder(view);
    initSelects(view);
    for (const picker of view.querySelectorAll('[data-icon-picker]:not([data-picker-ready])')) {
      picker.dataset.pickerReady = 'true';
      const search = picker.querySelector('[data-icon-search]');
      search.hidden = false;
      const panel = picker.querySelector('.type-icon-panel');
      if ('showPopover' in HTMLElement.prototype) {
        picker.dataset.floating = 'true';
        panel.setAttribute('popover', 'manual');
      }
      picker.addEventListener('toggle', () => {
        if (picker.open) showIconPicker(picker);
        else if (picker.dataset.floating && panel.matches(':popover-open')) panel.hidePopover();
      });
    }
    for (const editor of view.querySelectorAll('[data-property-editor]')) configureProperty(editor);
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
    fieldSequence++; fieldXHR?.abort();
    generation++;
    for (const { xhr, method } of pending.values()) if (method === 'get') xhr.abort();
  }
  async function request(url, { target = 'workspace-view', method = 'GET', values, origin = '', onSwap, extraHeaders = {} } = {}) {
    const token = String(++requestId), ownGeneration = generation;
    if (onSwap) swapCallbacks.set(token, onSwap);
    try {
      await htmx.ajax(method, url, {
        source: document.querySelector(`#${target}`), target: `#${target}`,
        swap: target === 'main' ? 'outerHTML' : 'innerHTML', values,
        headers: { 'X-Workspace-Token': token, 'X-Workspace-Generation': String(ownGeneration), 'X-Workspace-Return': origin, ...extraHeaders },
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
    const previousWindow = dialog() ? new URL(state.url, location.origin).pathname : null;
    message('Loading window…');
    const navigationGeneration = generation;
    const host = document.querySelector('#modal-host');
    host.inert = true; host.setAttribute('aria-busy', 'true');
    const success = await request(url, { target: 'modal-host', origin: origin.url, onSwap() {
      if (entry) state = entry; else commit(url, { origin, replace, previousWindow });
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
    if (requestConfig.headers['X-Fields-Sequence']) fieldXHR = xhr;
  });
  document.addEventListener('htmx:beforeSwap', event => {
    closeSelects();
    const { xhr, requestConfig } = event.detail;
    const fieldToken = requestConfig?.headers['X-Fields-Sequence'];
    if (fieldToken && Number(fieldToken) !== fieldSequence) { event.detail.shouldSwap = false; event.detail.ignoreTitle = true; }
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
    if (link.hasAttribute('data-window-close')) { closeWindow({ toOrigin: Boolean(state.closeToOrigin) }); return; }
    if (link.hasAttribute('data-window-back')) { closeWindow({ fallbackURL: url.pathname + url.search }); return; }
    if (link.hasAttribute('data-window')) { opener = link; openWindow(url.pathname + url.search); }
    else navigate(url.pathname + url.search);
  });
  document.addEventListener('submit', async event => {
    const form = event.target;
    if (form.hasAttribute('data-logout') || form.hasAttribute('data-session-action')) {
      if (!mayLeave()) event.preventDefault();
      else allowUnload = true;
      return;
    }
    if (form.hasAttribute('data-workspace-search')) {
      event.preventDefault();
      const url = new URL(form.action); url.search = new URLSearchParams(new FormData(form));
      const builder = form.hasAttribute('data-search-builder');
      await navigate(url.pathname + url.search);
      if (builder && main()?.dataset.pageUrl === url.pathname + url.search) {
        view.querySelector('[data-search-builder] :is(input[name="value"], select[name="value"]):not([disabled])')?.focus();
      }
      return;
    }
    if (!form.hasAttribute('data-async-form')) return;
    event.preventDefault();
    if (event.submitter?.value === 'load_properties' && form.querySelector('#item-custom-fields')) {
      await loadFields(form); return;
    }
    if (fieldStates.get(form) === 'loading' || fieldStates.get(form) === 'failed') {
      message('Load the selected type’s properties before saving.'); return;
    }
    if (writing) return;
    const otherDirty = [...view.querySelectorAll('[data-dirty-check]')].some(other => other !== form && baseline.has(other) && baseline.get(other) !== formValue(other));
    if (otherDirty && !confirm('Discard your unsaved changes?')) return;
    writing = true; message('Saving…');
    const oldBaseline = baseline.get(form);
    const values = Object.fromEntries(new FormData(form, event.submitter));
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
      commit(url.pathname + url.search, { replace: true, origin: state.origin,
        previousWindow: state.previousWindow,
        closeToOrigin: target === 'modal-host' && state.previousWindow === url.pathname });
    }
    hydrate({ focus: true, resetForms: Boolean(changed) });
    if (!changed) {
      // A bound validation response must remain dirty relative to the pre-edit form.
      const replacement = view.querySelector('[data-dirty-check]');
      if (replacement && oldBaseline !== undefined) baseline.set(replacement, oldBaseline);
      message(result.getResponseHeader('X-Workspace-Form-Updated') === 'true' ? '' : 'Please check the highlighted fields.'); return;
    }
    if (result.getResponseHeader('X-Workspace-Close') === 'true') {
      await closeWindow({ confirmed: true, toOrigin: true });
    } else if (target === 'modal-host' && !await refreshBase()) {
      message('Saved, but the list could not refresh. Reload it before making more changes.');
      return;
    }
    message('Saved.');
  });

  async function loadFields(form) {
    if (writing) return;
    const region = form.querySelector('#item-custom-fields');
    if (!region) return;
    const selected = form.elements.item_type.value;
    const loaded = form.elements._loaded_type?.value || '';
    const cache = fieldCaches.get(form) || new Map();
    // Do not overwrite the last loaded type's draft while a replacement is pending.
    if (fieldStates.get(form) !== 'loading' && fieldStates.get(form) !== 'failed') {
      cache.set(loaded, Object.fromEntries([...new FormData(form)].filter(([key]) => key.startsWith('property_'))));
    }
    fieldCaches.set(form, cache);
    const values = Object.fromEntries(new FormData(form));
    for (const key of Object.keys(values)) if (key.startsWith('property_') || key === 'confirm_type_change') delete values[key];
    if (cache.has(selected)) { Object.assign(values, cache.get(selected)); values._loaded_type = selected; }
    else values._loaded_type = '';
    const sequence = ++fieldSequence;
    fieldXHR?.abort();
    fieldStates.set(form, 'loading');
    region.inert = true; region.setAttribute('aria-busy', 'true');
    const saveButtons = [...form.querySelectorAll('button[type="submit"]:not([value="load_properties"])')];
    saveButtons.forEach(button => button.disabled = true);
    message('Loading properties…');
    const ok = await request(region.dataset.fieldsUrl, { target: 'item-custom-fields', method: 'POST', values,
      extraHeaders: { 'X-Fields-Sequence': String(sequence) } });
    if (sequence !== fieldSequence || !region.isConnected) return;
    region.inert = false; region.removeAttribute('aria-busy');
    fieldStates.set(form, ok ? 'ready' : 'failed');
    if (ok) { initSelects(region); saveButtons.forEach(button => button.disabled = false); message(); }
    else message('Could not load properties. Use Load properties to retry before saving.');
  }
  function configureProperty(form) {
    const kind = form.elements.data_type.value;
    form.querySelector('[data-number-config]').hidden = kind !== 'number';
    form.querySelector('[data-dropdown-config]').hidden = kind !== 'dropdown';
  }
  document.addEventListener('change', event => {
    if (event.target.matches('[data-icon-picker] input[type="radio"]')) {
      const picker = event.target.closest('[data-icon-picker]');
      const selected = event.target.closest('label').querySelector('.type-icon');
      picker.querySelector('summary .type-icon').style.setProperty('--type-icon', selected.style.getPropertyValue('--type-icon'));
    }
    if (event.target.matches('[name="data_type"]') && event.target.closest('[data-property-editor]')) configureProperty(event.target.form);
    if (event.target.matches('select[name="item_type"]')) {
      const form = event.target.form;
      if (form?.querySelector('#item-custom-fields')) loadFields(form);
    }
  });
  document.addEventListener('input', event => {
    if (!event.target.matches('[data-icon-search]')) return;
    const picker = event.target.closest('[data-icon-picker]');
    const query = event.target.value.trim().toLocaleLowerCase();
    let matches = 0;
    for (const option of picker.querySelectorAll('.type-icon-option')) {
      const visible = option.title.toLocaleLowerCase().includes(query);
      option.hidden = !visible;
      if (visible) matches++;
    }
    picker.querySelector('[data-icon-empty]').hidden = matches > 0;
  });
  document.addEventListener('click', event => {
    if (!event.target.matches('[data-icon-picker] input[type="radio"]')) return;
    const picker = event.target.closest('[data-icon-picker]');
    const search = picker.querySelector('[data-icon-search]');
    search.value = '';
    search.dispatchEvent(new Event('input', { bubbles: true }));
    closeIconPicker(picker, true);
  });
  document.addEventListener('pointerdown', event => {
    for (const picker of view.querySelectorAll('[data-icon-picker][open]')) {
      if (!picker.contains(event.target)) closeIconPicker(picker);
    }
  });
  document.addEventListener('scroll', event => {
    for (const picker of view.querySelectorAll('[data-icon-picker][open]')) {
      if (event.target instanceof Element && event.target.contains(picker)) closeIconPicker(picker);
    }
  }, true);
  window.addEventListener('resize', () => {
    for (const picker of view.querySelectorAll('[data-icon-picker][open]')) closeIconPicker(picker);
  });

  document.addEventListener('keydown', event => {
    const win = dialog();
    if (!win) return;
    if (event.key === 'Enter' && event.target.matches('[data-icon-search]')) { event.preventDefault(); return; }
    const picker = win.querySelector('[data-icon-picker][open]');
    if (event.key === 'Escape' && picker) { event.preventDefault(); closeIconPicker(picker, true); return; }
    if (event.key === 'Escape') { event.preventDefault(); closeWindow({ toOrigin: Boolean(state.closeToOrigin) }); }
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

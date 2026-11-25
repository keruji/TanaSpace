// Progressive, select-only combobox. Django's select remains the form value and
// validation source; browsers without popovers keep the styled native control.
let active;
let sequence = 0;
let listening = false;

export function closeSelects() {
  active?.close();
}

export function initSelects(root) {
  if (!('showPopover' in HTMLElement.prototype)) return;
  if (!listening) {
    document.addEventListener('pointerdown', event => {
      if (active && !active.root.contains(event.target)) active.commit();
    });
    window.addEventListener('resize', closeSelects);
    document.addEventListener('scroll', event => {
      if (active && !active.list.contains(event.target)) active.close();
    }, true);
    listening = true;
  }
  for (const select of root.querySelectorAll('select:not([multiple]):not([data-select-ready]):not([data-native-select])')) {
    if (select.size > 1) continue;
    const container = document.createElement('div');
    container.className = 'select-control';
    select.before(container);
    container.append(select);
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'select-trigger';
    button.setAttribute('role', 'combobox');
    button.setAttribute('aria-expanded', 'false');
    button.setAttribute('aria-haspopup', 'listbox');
    button.disabled = select.disabled;
    const text = document.createElement('span');
    text.className = 'select-value';
    const arrow = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    arrow.setAttribute('viewBox', '0 0 24 24');
    arrow.setAttribute('class', 'ui-icon select-chevron');
    arrow.setAttribute('aria-hidden', 'true');
    const path = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    path.setAttribute('d', 'm6 9 6 6 6-6');
    arrow.append(path);
    button.append(text, arrow);
    const list = document.createElement('div');
    list.className = 'select-list';
    list.id = `select-list-${++sequence}`;
    list.setAttribute('role', 'listbox');
    list.setAttribute('popover', 'manual');
    button.setAttribute('aria-controls', list.id);
    const label = [...root.querySelectorAll('label')].find(label => label.htmlFor === select.id);
    if (label) {
      label.id ||= `${list.id}-label`;
      button.setAttribute('aria-labelledby', label.id);
      list.setAttribute('aria-labelledby', label.id);
      label.addEventListener('click', event => { event.preventDefault(); button.focus(); });
    } else {
      button.setAttribute('aria-label', select.getAttribute('aria-label') || select.name);
    }
    if (select.hasAttribute('aria-describedby')) button.setAttribute('aria-describedby', select.getAttribute('aria-describedby'));
    if (select.required) button.setAttribute('aria-required', 'true');
    if (select.getAttribute('aria-invalid') === 'true') button.setAttribute('aria-invalid', 'true');
    const error = document.createElement('span');
    error.className = 'select-error';
    error.setAttribute('role', 'alert');
    container.append(button, list, error);
    let opened = false, cursor = 0, buffer = '', typedAt = 0, hasSelection = false;
    const choices = [...select.options].filter(option =>
      !option.disabled && !option.closest('optgroup[disabled]') &&
      !(!option.value && select.required)
    );
    const nodes = choices.map((choice, index) => {
      const option = document.createElement('div');
      option.id = `${list.id}-${index}`;
      option.className = 'select-option';
      if (choice.parentElement.tagName === 'OPTGROUP') option.classList.add('select-option-indented');
      option.setAttribute('role', 'option');
      const name = document.createElement('span');
      name.textContent = !choice.value && /^choose\b/i.test(choice.textContent.trim())
        ? 'Clear selection' : choice.textContent;
      const check = document.createElement('span');
      check.className = 'select-check';
      check.setAttribute('aria-hidden', 'true');
      check.textContent = '✓';
      option.append(name, check);
      option.addEventListener('pointerdown', event => event.preventDefault());
      option.addEventListener('pointermove', () => { hasSelection = true; highlight(index); });
      option.addEventListener('click', () => { hasSelection = true; cursor = index; commit(); button.focus(); });
      list.append(option);
      return option;
    });
    function sync() {
      button.disabled = select.disabled;
      text.textContent = !select.value && select.required ? 'Choose an option' : select.selectedOptions[0]?.textContent || 'Choose an option';
      button.classList.toggle('is-placeholder', !select.value && (select.required || select.selectedOptions[0]?.disabled));
      choices.forEach((choice, index) => nodes[index].setAttribute('aria-selected', String(choice.selected)));
    }
    function highlight(index) {
      cursor = Math.max(0, Math.min(index, choices.length - 1));
      nodes.forEach((node, i) => node.classList.toggle('is-active', i === cursor));
      if (opened && nodes[cursor]) {
        button.setAttribute('aria-activedescendant', nodes[cursor].id);
        const option = nodes[cursor];
        if (option.offsetTop < list.scrollTop) list.scrollTop = option.offsetTop;
        else if (option.offsetTop + option.offsetHeight > list.scrollTop + list.clientHeight) {
          list.scrollTop = option.offsetTop + option.offsetHeight - list.clientHeight;
        }
      }
    }
    function close() {
      if (!opened) return;
      opened = false;
      list.hidePopover();
      button.setAttribute('aria-expanded', 'false');
      button.removeAttribute('aria-activedescendant');
      if (active?.root === container) active = null;
    }
    function commit() {
      if (opened && hasSelection && choices[cursor]) {
        select.value = choices[cursor].value;
        select.dispatchEvent(new Event('input', { bubbles: true }));
        select.dispatchEvent(new Event('change', { bubbles: true }));
      }
      close();
    }
    function open() {
      if (button.disabled || !choices.length) return;
      closeSelects();
      const rect = button.getBoundingClientRect();
      const below = innerHeight - rect.bottom - 12, above = rect.top - 12;
      const width = Math.min(rect.width, innerWidth - 24);
      list.style.width = `${width}px`;
      list.style.maxHeight = 'none';
      list.style.left = `${Math.max(12, Math.min(rect.left, innerWidth - width - 12))}px`;
      list.style.top = '0px';
      list.style.visibility = 'hidden';
      list.showPopover();

      // Measure the rendered options, including wrapping, padding, and borders.
      const desired = Math.min(240, Math.ceil(list.getBoundingClientRect().height));
      const up = below < Math.min(desired, 160) && above > below;
      const height = Math.max(40, Math.min(desired, up ? above : below));
      list.style.maxHeight = `${height}px`;
      const actualHeight = list.getBoundingClientRect().height;
      list.style.top = `${up ? rect.top - actualHeight - 6 : rect.bottom + 6}px`;
      list.style.visibility = '';
      opened = true;
      hasSelection = choices.some(choice => choice.selected);
      button.setAttribute('aria-expanded', 'true');
      active = { root: container, list, close, commit };
      highlight(Math.max(0, choices.findIndex(choice => choice.selected)));
    }
    button.addEventListener('click', () => opened ? close() : open());
    button.addEventListener('keydown', event => {
      if (event.key === 'Escape' && opened) {
        event.preventDefault(); event.stopPropagation(); close(); return;
      }
      if (event.key === 'Tab') { if (opened) commit(); return; }
      if (['ArrowDown', 'ArrowUp', 'Home', 'End', 'Enter', ' '].includes(event.key)) {
        event.preventDefault();
        if (!opened) { open(); if (event.key === 'Home') highlight(0); if (event.key === 'End') highlight(choices.length - 1); }
        else if (event.key === 'ArrowDown') highlight(cursor + 1);
        else if (event.key === 'ArrowUp') highlight(cursor - 1);
        else if (event.key === 'Home') highlight(0);
        else if (event.key === 'End') highlight(choices.length - 1);
        else { hasSelection = true; commit(); }
        if (opened) hasSelection = true;
      } else if (event.key.length === 1 && !event.ctrlKey && !event.metaKey && !event.altKey) {
        event.preventDefault();
        if (!opened) open();
        const hadSelection = hasSelection;
        hasSelection = true;
        buffer = Date.now() - typedAt < 700 ? buffer + event.key : event.key;
        typedAt = Date.now();
        const repeated = [...buffer].every(letter => letter.toLowerCase() === buffer[0].toLowerCase());
        const query = (repeated ? buffer[0] : buffer).toLocaleLowerCase();
        const start = repeated && hadSelection ? cursor + 1 : 0;
        for (let offset = 0; offset < choices.length; offset++) {
          const index = (start + offset) % choices.length;
          if (choices[index].textContent.toLocaleLowerCase().startsWith(query)) { highlight(index); break; }
        }
      }
    });
    button.addEventListener('blur', () => { if (opened) commit(); });
    select.addEventListener('change', () => {
      sync();
      if (select.validity.valid) { error.textContent = ''; button.removeAttribute('aria-invalid'); }
    });
    select.addEventListener('select-sync', sync);
    select.addEventListener('invalid', event => {
      event.preventDefault();
      error.textContent = select.validationMessage;
      button.setAttribute('aria-invalid', 'true');
      button.focus();
    });
    select.addEventListener('focus', () => button.focus());
    select.form?.addEventListener('reset', () => queueMicrotask(sync));
    // HTMX restores class/style after a swap. A data attribute survives that
    // settling step, keeping the native control hidden behind its replacement.
    select.dataset.selectReady = 'true';
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');
    sync();
  }
}

import { initSelects } from './select.js';

export function initSearchBuilder(root) {
  const form = root.querySelector('[data-search-builder]');
  if (!form || form.dataset.ready) return;
  form.dataset.ready = 'true';
  const types = [...form.querySelectorAll('[data-type-id]')].map(type => ({
    id: type.dataset.typeId,
    name: type.dataset.name,
    properties: [...type.querySelectorAll('[data-property-id]')].map(prop => ({
      id: prop.dataset.propertyId,
      name: prop.dataset.name,
      kind: prop.dataset.kind,
      options: [...prop.querySelectorAll('[data-option-id]')].map(option => ({ id: option.dataset.optionId, label: option.dataset.label })),
    })),
  }));
  const field = form.querySelector('[data-search-field]');
  const input = form.querySelector('[data-search-value]');
  const inputWrap = form.querySelector('[data-search-input]');
  const typeWrap = form.querySelector('[data-search-types]');
  const typeSelect = form.querySelector('[data-search-type]');
  const choiceWrap = form.querySelector('[data-search-choice-wrap]');
  const dateWraps = [...form.querySelectorAll('[data-search-dates]')];
  const selected = [...form.querySelectorAll('input[name=types]')].map(el => el.value);
  const selectedTypes = types.filter(type => selected.includes(type.id));
  const shared = [];
  if (selectedTypes.length) {
    for (const prop of selectedTypes[0].properties) {
      const group = selectedTypes.map(type => type.properties.find(candidate =>
        candidate.name.toLocaleLowerCase() === prop.name.toLocaleLowerCase() && candidate.kind === prop.kind));
      if (group.every(Boolean)) shared.push(group);
    }
  }
  for (const option of [...field.options]) if (option.value.startsWith('prop_')) option.remove();
  if (shared.length) {
    const group = document.createElement('optgroup');
    group.label = 'Tana Type properties';
    for (const props of shared) {
      const option = document.createElement('option');
      option.value = 'prop_' + props[0].id;
      option.textContent = props[0].name;
      group.append(option);
    }
    field.append(group);
  }
  if ([...field.options].some(option => option.value === form.dataset.field)) field.value = form.dataset.field;
  for (const option of typeSelect.options) if (selected.includes(option.value)) option.disabled = true;
  function update() {
    const mode = field.value;
    const isType = mode === 'types';
    const isDate = mode === 'created';
    inputWrap.hidden = isType || isDate;
    input.disabled = isType || isDate;
    typeWrap.hidden = !isType;
    typeSelect.disabled = !isType;
    typeSelect.name = isType ? 'value' : '';
    typeSelect.dispatchEvent(new Event('select-sync'));
    for (const wrap of dateWraps) wrap.hidden = !isDate;
    input.type = 'text';
    input.placeholder = '';
    input.removeAttribute('list');
    const prop = shared.find(group => 'prop_' + group[0].id === mode);
    const oldChoice = choiceWrap.querySelector('[data-search-choice]');
    const choice = document.createElement('select');
    choice.id = 'search-choice';
    choice.dataset.searchChoice = '';
    const oldControl = oldChoice.closest('.select-control');
    (oldControl || oldChoice).replaceWith(choice);
    const choiceLabel = choiceWrap.querySelector('label');
    choiceLabel.replaceWith(choiceLabel.cloneNode(true));
    const isChoice = prop && (prop[0].kind === 'dropdown' || prop[0].kind === 'boolean');
    choiceWrap.hidden = !isChoice;
    inputWrap.hidden = isType || isDate || isChoice;
    input.disabled = isType || isDate || isChoice;
    choice.disabled = !isChoice;
    choice.name = isChoice ? 'value' : '';
    if (prop) {
      if (prop[0].kind === 'date') input.type = 'date';
      if (prop[0].kind === 'number') { input.type = 'number'; input.step = 'any'; }
      if (isChoice) {
        choice.add(new Option(prop[0].kind === 'boolean' ? 'Choose Yes or No' : 'Choose an option', '', true, true));
        choice.options[0].disabled = true;
        choice.options[0].hidden = true;
      }
      if (prop[0].kind === 'boolean') {
        choice.add(new Option('Yes', 'Yes'));
        choice.add(new Option('No', 'No'));
      }
      if (prop[0].kind === 'dropdown') {
        const labels = prop[0].options.filter(option => prop.every(entry => entry.options.some(other => other.label.toLocaleLowerCase() === option.label.toLocaleLowerCase())));
        for (const option of labels) choice.add(new Option(option.label, option.label));
      }
    }
    initSelects(choiceWrap);
  }
  field.addEventListener('change', update);
  typeSelect.addEventListener('change', () => {
    if (typeSelect.value) form.requestSubmit();
  });
  for (const button of form.querySelectorAll('[data-property-choice]')) {
    button.addEventListener('click', () => {
      field.value = button.dataset.propertyChoice;
      field.dispatchEvent(new Event('change', { bubbles: true }));
      const target = choiceWrap.hidden ? input : choiceWrap.querySelector('.select-trigger, select');
      target.focus();
    });
  }
  function removeUnavailableProperties(typeIds) {
    const kinds = types.filter(type => typeIds.includes(type.id));
    for (const chip of form.querySelectorAll('.search-chip')) {
      const hidden = chip.querySelector('input');
      if (!hidden || !hidden.name.startsWith('prop_')) continue;
      const original = shared.find(group => 'prop_' + group[0].id === hidden.name);
      if (!original || !kinds.length || !kinds.every(type => type.properties.some(prop =>
        prop.name.toLocaleLowerCase() === original[0].name.toLocaleLowerCase() && prop.kind === original[0].kind &&
        (prop.kind !== 'dropdown' || prop.options.some(option => option.label.toLocaleLowerCase() === hidden.value.toLocaleLowerCase()))))) chip.remove();
    }
  }
  form.addEventListener('submit', () => {
    if (field.value === 'types' && typeSelect.value) removeUnavailableProperties([...selected, typeSelect.value]);
  });
  for (const button of form.querySelectorAll('[data-remove-search]')) {
    button.addEventListener('click', () => {
      button.closest('.search-chip').remove();
      if (button.dataset.removeSearch === 'types') {
        removeUnavailableProperties([...form.querySelectorAll('input[name=types]')].map(el => el.value));
      }
      if (button.dataset.removeSearch === 'created_from' || button.dataset.removeSearch === 'created_to') {
        form.querySelector('[name=' + button.dataset.removeSearch + ']').value = '';
      }
      input.value = '';
      typeSelect.value = '';
      field.value = 'name';
      update();
      field.dispatchEvent(new Event('select-sync'));
      form.requestSubmit();
    });
  }
  update();
}

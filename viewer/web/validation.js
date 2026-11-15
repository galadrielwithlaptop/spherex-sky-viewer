function viewerInputIssues(controls) {
  const issues = [];
  const number = (key, label, min, max, exclusive = false) => {
    const raw = String(controls[key] ?? '').trim(), n = Number(raw);
    if (!raw || !Number.isFinite(n) || n < min || (exclusive ? n >= max : n > max))
      issues.push({key, message: `${label}: enter a number from ${min} ${exclusive ? 'up to, but not including' : 'to'} ${max}.`});
  };
  const choice = (key, label, options) => {
    if (!options.includes(String(controls[key]))) issues.push({key, message: `${label}: choose one of the listed options.`});
  };
  number('ra', 'Right ascension (degrees)', 0, 360, true);
  number('dec', 'Declination (degrees)', -90, 90);
  number('fov', 'Field diameter (arcminutes)', 1, 60);
  choice('target', 'Target', ['custom','WISE0855',"Barnard's Star",'eps Ind B','RW Aur','R Dra']);
  choice('detector', 'Detector array', ['all',...[1,2,3,4,5,6].map(n => 'SPHEREx-D'+n)]);
  choice('sequence', 'Sequence type', ['matched','all']);
  choice('count', 'Sample size', ['6','12','24']);
  for (const key of ['from','through']) {
    const value = controls[key];
    if (value && (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0,10) !== value))
      issues.push({key, message: `${key === 'from' ? 'From' : 'Through'} date: enter a real calendar date (YYYY-MM-DD).`});
  }
  if (controls.from && controls.through && controls.from > controls.through)
    issues.push({key:'through', message:'Through date must be on or after From date. For example, 2025-05-01 through 2025-10-31.'});
  return issues;
}

function validateViewerInputs() {
  const search = document.querySelector('#search');
  const controls = Object.fromEntries(new FormData(search));
  for (const id of ['target','detector','sequence','count','from','through']) controls[id] = document.querySelector('#'+id).value;
  const issues = viewerInputIssues(controls);
  for (const id of ['from','through']) if (document.querySelector('#'+id).validity.badInput) issues.push({key:id,message:'Enter a complete, valid calendar date.'});
  for (const input of document.querySelectorAll('[aria-invalid]')) { input.removeAttribute('aria-invalid'); input.removeAttribute('aria-errormessage'); }
  for (const issue of issues) {
    const input = search.elements[issue.key] || document.getElementById(issue.key);
    input?.setAttribute('aria-invalid','true'); input?.setAttribute('aria-errormessage','input-errors');
  }
  const box = document.querySelector('#input-errors');
  box.hidden = !issues.length;
  box.textContent = issues.length ? 'Please correct these settings: '+issues.map(i=>i.message).join(' ') : '';
  if (issues.length) {
    const advancedKeys = ['detector','sequence','count','from','through'];
    const first = issues[0];
    if (advancedKeys.includes(first.key)) {
      const dialog = document.querySelector('#advanced-dialog');
      if (!dialog.open) dialog.showModal();
      document.querySelector('#advanced-errors').textContent = box.textContent;
      document.querySelector('#advanced-errors').hidden = false;
    } else box.focus();
  } else {
    document.querySelector('#advanced-errors').hidden = true;
  }
  return !issues.length;
}

document.addEventListener('change', event => {
  const el = event.target;
  if (['ra','dec','fov'].includes(el.name) || ['target','detector','sequence','count','from','through'].includes(el.id)) validateViewerInputs();
}, true);

// Validate URL inputs before the application can resume a saved sequence.
const initialQuery = new URLSearchParams(location.search);
for (const key of ['ra','dec','fov']) if (initialQuery.has(key)) document.querySelector('#search').elements[key].value = initialQuery.get(key);

for (const eventName of ['input','change']) document.addEventListener(eventName, event => {
  const el = event.target;
  if (!['speed','group','mode','overlay','brightness','timeline'].includes(el.id)) return;
  let valid = true;
  if (el.tagName === 'SELECT') valid = [...el.options].some(option => option.value === el.value);
  else { const n=Number(el.value); valid=el.value!=='' && Number.isFinite(n) && Number.isInteger(n) && n>=Number(el.min) && n<=Number(el.max); }
  if (valid) { el.removeAttribute('aria-invalid'); return; }
  event.preventDefault(); event.stopImmediatePropagation(); el.setAttribute('aria-invalid','true');
  const box=document.querySelector('#input-errors'); box.hidden=false; box.textContent='Invalid '+el.id+' setting. Choose a listed option or a value within the slider range.'; box.focus();
}, true);

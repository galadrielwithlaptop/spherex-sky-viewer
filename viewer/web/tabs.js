(() => {
  const tabs = [...document.querySelectorAll('[data-tab]')];
  const panels = [...document.querySelectorAll('[data-feature]')];
  const help = document.querySelector('#tab-help');
  const hints = {
    search: 'Choose a target or coordinates, then click Find observations. Your image stays visible across tabs.',
    playback: 'Load images in Find sky images first. Then play or step through dates. Detector/date settings are in Advanced settings at the top right.',
    compare: 'Select a wavelength group before comparing its mean coadd or last-minus-first difference. These views are exploratory.',
    overlays: 'Choose Gaia or AllWISE to overlay catalogue positions on the loaded image.',
    data: 'Inspect available observations, export metadata, and download products from the loaded sequence.',
    api: 'Open the interactive documentation to try coordinate queries and integrate the versioned API.'
  };
  function select(tab, focus = false) {
    for (const item of tabs) {
      const active = item === tab;
      item.setAttribute('aria-selected', String(active));
      item.tabIndex = active ? 0 : -1;
    }
    for (const panel of panels) panel.hidden = !panel.dataset.feature.split(' ').includes(tab.dataset.tab);
    help.textContent = hints[tab.dataset.tab];
    document.querySelector('.layout').classList.toggle('wide-viewer', ['playback', 'compare', 'overlays', 'data'].includes(tab.dataset.tab));
    if (focus) tab.focus();
  }
  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => select(tab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      select(tabs[next], true);
    });
  });
  const dialog = document.querySelector('#advanced-dialog');
  document.querySelector('#advanced-content').append(document.querySelector('#sequence-panel'));
  document.querySelector('#advanced-open').addEventListener('click', () => dialog.showModal());
  document.querySelector('#advanced-close').addEventListener('click', () => dialog.close());
  select(tabs[0]);
})();

// Progressive enhancement: every gallery link also works without JavaScript.
(() => {
  const dialog = document.querySelector('#image-viewer');
  if (!dialog || typeof dialog.showModal !== 'function') return;
  const image = dialog.querySelector('.lightbox-image');
  const title = dialog.querySelector('.lightbox-title');
  const caption = dialog.querySelector('.lightbox-caption');
  let opener;

  document.querySelectorAll('[data-view-image]').forEach((link) => {
    link.addEventListener('click', (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      opener = link;
      const figure = link.closest('figure');
      const source = link.querySelector('img');
      title.textContent = figure.querySelector('h3').textContent;
      caption.textContent = figure.querySelector('.figure-copy p').textContent;
      image.src = link.href;
      image.alt = source.alt;
      dialog.showModal();
    });
  });

  dialog.querySelector('.lightbox-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (event) => {
    if (event.target !== dialog) return;
    const bounds = dialog.getBoundingClientRect();
    if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) dialog.close();
  });
  dialog.addEventListener('close', () => {
    image.removeAttribute('src');
    opener?.focus({ preventScroll: true });
  });
})();

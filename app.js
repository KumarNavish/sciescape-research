// Progressive enhancement: original images and research links also work without JS.
const worlds = {
  bamboo: { title: 'Bamboo after rain', index: '01', yaw: 25, alt: 'Mist between tall bamboo trees, rain on stone steps, and a small wooden shelter.' },
  canal: { title: 'Canal at dusk', index: '02', yaw: 42, alt: 'Warm windows and small boats reflected in a canal at dusk.' },
  hut: { title: 'Mountain hut', index: '03', yaw: 0, alt: 'A wooden mountain hut with bunk beds, a stove and mountain views.' },
  'reading-room': { title: 'Quiet reading room', index: '04', yaw: 0, alt: 'An inviting furnished reading room with shelves and places to sit.' },
  oasis: { title: 'Desert oasis', index: '05', yaw: 0, alt: 'A desert oasis surrounded by dunes beneath an open sky.' },
};
const imagePath = id => `assets/${id}.png`;
const dialog = document.querySelector('#world-viewer');
let canvas = document.querySelector('#panorama');
const status = document.querySelector('#viewer-status');
const fallback = document.querySelector('#viewer-fallback');
let viewer, opener, currentWorld, loadVersion = 0;
let createPanorama;

// Cover changes are deliberate. No slideshow or background render loop.
document.querySelector('.scene-switcher').hidden = false;
document.querySelectorAll('[data-cover]').forEach(button => {
  button.addEventListener('click', () => {
    const id = button.dataset.cover;
    const world = worlds[id];
    const hero = document.querySelector('#hero-image');
    hero.src = imagePath(id);
    hero.alt = world.alt;
    document.querySelector('#hero-title').textContent = world.title;
    document.querySelector('#hero-number').textContent = `World ${world.index} / 05`;
    const enter = document.querySelector('#hero-enter');
    enter.dataset.world = id;
    enter.href = imagePath(id);
    document.querySelectorAll('[data-cover]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  });
});

function showFallback() {
  if (!dialog.open) return;
  dialog.classList.remove('ready');
  dialog.classList.add('fallback');
  status.textContent = 'The interactive view is unavailable. You can still enjoy the image or open the original below.';
  canvas.setAttribute('tabindex', '-1');
}

async function selectWorld(id) {
  const version = ++loadVersion;
  currentWorld = id;
  const world = worlds[id];
  dialog.classList.remove('ready', 'fallback');
  status.textContent = `Opening ${world.title.toLowerCase()}…`;
  document.querySelector('#viewer-title').textContent = world.title;
  document.querySelector('#viewer-original').href = imagePath(id);
  fallback.src = imagePath(id);
  fallback.alt = world.alt;
  canvas.setAttribute('aria-label', `${world.title}. Drag to look around; use arrow keys to turn, plus or minus to zoom, and Home to reset.`);
  canvas.setAttribute('tabindex', '0');
  document.querySelectorAll('[data-select]').forEach(item => item.setAttribute('aria-pressed', String(item.dataset.select === id)));
  try {
    if (!createPanorama) ({ createPanorama } = await import('./panorama.js'));
    if (version !== loadVersion || !dialog.open) return;
    if (!viewer) viewer = createPanorama(canvas, { onError: showFallback });
    await viewer.load(imagePath(id), { yaw: world.yaw, pitch: 0, fov: 75 });
    if (version !== loadVersion || !dialog.open) return;
    viewer.resize();
    dialog.classList.add('ready');
    status.textContent = '';
  } catch {
    if (version === loadVersion) showFallback();
  }
}

if (dialog && typeof dialog.showModal === 'function') {
  document.querySelectorAll('[data-world]').forEach(link => link.addEventListener('click', event => {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    opener = link;
    document.body.classList.add('viewer-open');
    dialog.showModal();
    selectWorld(link.dataset.world);
  }));
  document.querySelector('#viewer-close').addEventListener('click', () => dialog.close());
  dialog.addEventListener('close', () => {
    ++loadVersion;
    viewer?.destroy();
    viewer = null;
    const freshCanvas = canvas.cloneNode(false);
    canvas.replaceWith(freshCanvas);
    canvas = freshCanvas;
    dialog.classList.remove('ready', 'fallback');
    fallback.removeAttribute('src');
    document.body.classList.remove('viewer-open');
    opener?.focus({ preventScroll: true });
  });
  document.querySelectorAll('[data-select]').forEach(button => button.addEventListener('click', () => selectWorld(button.dataset.select)));
  document.querySelectorAll('[data-look]').forEach(button => button.addEventListener('click', () => {
    if (!viewer || !dialog.classList.contains('ready')) return;
    const view = viewer.getView();
    switch (button.dataset.look) {
      case 'left': view.yaw -= 18; break;
      case 'right': view.yaw += 18; break;
      case 'up': view.pitch += 12; break;
      case 'down': view.pitch -= 12; break;
      case 'in': view.fov -= 8; break;
      case 'out': view.fov += 8; break;
      case 'reset': Object.assign(view, { yaw: worlds[currentWorld].yaw, pitch: 0, fov: 75 }); break;
    }
    viewer.setView(view);
  }));
}

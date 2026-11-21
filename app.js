// Progressive enhancement: original images and research links also work without JS.
const worlds = {
  bamboo: {
    title: 'Bamboo after rain',
    index: '01',
    yaw: 25,
    alt: 'Mist between tall bamboo trees, rain on stone steps, and a small wooden shelter.',
    regions: [
      { yawMin: -35, yawMax: 35, node: 'wet_stone_steps_01', desc: 'Anchored foreground path · rain specular surface' },
      { yawMin: 35, yawMax: 115, node: 'timber_shelter_01', desc: 'Covered wooden shrine · candidate edit object' },
      { yawMin: -115, yawMax: -35, node: 'bamboo_grove_west', desc: 'Dense vertical stalks · occlusion boundary check' },
      { yawMin: 115, yawMax: 180, node: 'mist_bamboo_corridor', desc: 'Deep atmospheric corridor · far depth horizon' },
      { yawMin: -180, yawMax: -115, node: 'mist_bamboo_corridor', desc: 'Deep atmospheric corridor · far depth horizon' },
    ],
  },
  canal: {
    title: 'Canal at dusk',
    index: '02',
    yaw: 42,
    alt: 'Warm windows and small boats reflected in a canal at dusk.',
    regions: [
      { yawMin: -40, yawMax: 45, node: 'stone_footbridge_arch', desc: 'Masonry bridge span · reflection consistency target' },
      { yawMin: 45, yawMax: 135, node: 'blue_hour_facade_east', desc: 'Warm lit windows · protected neighbor surface' },
      { yawMin: -135, yawMax: -40, node: 'moored_canal_boats', desc: 'Wooden hull & water reflections · depth edge' },
      { yawMin: 135, yawMax: 180, node: 'canal_waterway_far', desc: 'Evening dusk horizon · calm surface plane' },
      { yawMin: -180, yawMax: -135, node: 'canal_waterway_far', desc: 'Evening dusk horizon · calm surface plane' },
    ],
  },
  hut: {
    title: 'Mountain hut',
    index: '03',
    yaw: 0,
    alt: 'A wooden mountain hut with bunk beds, a stove and mountain views.',
    regions: [
      { yawMin: -40, yawMax: 55, node: 'alpine_doorway_opening', desc: 'Portal opening onto snow peak · doorway passage check' },
      { yawMin: 55, yawMax: 145, node: 'timber_wall_skis', desc: 'Interior cedar planks · foreground prop anchors' },
      { yawMin: -145, yawMax: -40, node: 'cast_iron_stove_01', desc: 'Wood stove & kettle · local edit anchor' },
      { yawMin: 145, yawMax: 180, node: 'hut_bunk_alcove', desc: 'Back cabin sleeping bunks · return-visit check' },
      { yawMin: -180, yawMax: -145, node: 'hut_bunk_alcove', desc: 'Back cabin sleeping bunks · return-visit check' },
    ],
  },
  'reading-room': {
    title: 'Quiet reading room',
    index: '04',
    yaw: 0,
    alt: 'An inviting furnished reading room with shelves and places to sit.',
    regions: [
      { yawMin: -45, yawMax: 45, node: 'emerald_reading_lamps', desc: 'Desk lamp row · 240/240 clean local edit demo' },
      { yawMin: 45, yawMax: 135, node: 'oak_book_shelves', desc: 'Floor-to-ceiling shelving · high-frequency texture guard' },
      { yawMin: -135, yawMax: -45, node: 'arched_clerestory_windows', desc: 'Daylight window bays · ambient lighting anchor' },
      { yawMin: 135, yawMax: 180, node: 'reading_table_aisle', desc: 'Long wooden study tables · walkable floor plane' },
      { yawMin: -180, yawMax: -135, node: 'reading_table_aisle', desc: 'Long wooden study tables · walkable floor plane' },
    ],
  },
  oasis: {
    title: 'Desert oasis',
    index: '05',
    yaw: 0,
    alt: 'A desert oasis surrounded by dunes beneath an open sky.',
    regions: [
      { yawMin: -50, yawMax: 50, node: 'reflective_oasis_basin', desc: 'Still water mirror · sky-to-surface reflection check' },
      { yawMin: 50, yawMax: 140, node: 'palm_canopy_east', desc: 'Date palms & shade boundary · fine foliage occlusion' },
      { yawMin: -140, yawMax: -50, node: 'sunlit_dune_ridge', desc: 'Wind-sculpted sand slope · smooth geometry gradient' },
      { yawMin: 140, yawMax: 180, node: 'open_desert_horizon', desc: 'Wide twilight sky dome · far-field lighting' },
      { yawMin: -180, yawMax: -140, node: 'open_desert_horizon', desc: 'Wide twilight sky dome · far-field lighting' },
    ],
  },
};

const imagePath = id => `assets/${id}.png`;
const dialog = document.querySelector('#world-viewer');
let canvas = document.querySelector('#panorama');
const status = document.querySelector('#viewer-status');
const fallback = document.querySelector('#viewer-fallback');
const film = document.querySelector('#research-film');
const telemetryEl = document.querySelector('#viewer-telemetry');
const gazeNodeEl = document.querySelector('#viewer-gaze-node');
const gazeDescEl = document.querySelector('#viewer-gaze-desc');
const hudToggle = document.querySelector('#viewer-hud-toggle');
const gazeBar = document.querySelector('#viewer-gaze-bar');
const viewerReticle = document.querySelector('#viewer-reticle');

let viewer, opener, currentWorld, loadVersion = 0;
let createPanorama;
let hudEnabled = true;

// Playback is deliberate; stop it when the page or panorama takes over.
document.addEventListener('visibilitychange', () => {
  if (document.hidden) film?.pause();
});
window.addEventListener('pagehide', () => film?.pause());

// Cover changes are deliberate. No slideshow or background render loop.
const switcher = document.querySelector('.scene-switcher');
if (switcher) switcher.hidden = false;
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

// ================= INTERACTIVE SHARED WORLD-STATE WALKTHROUGH =================
const stateConfig = {
  gaze: {
    img: 'assets/bamboo.png',
    alt: 'Bamboo after rain shelter gaze-raycast check',
    eyebrow: '01 / GAZE-TO-SURFACE GROUNDING',
    heading: 'The guide sees the exact surface you point to.',
    copy: 'When rendering and conversation run on separate pipelines, the guide guesses from flat 2D crops and drifts off-surface (5.13 cm median error). Reading one typed 3D scene graph lets the guide raycast onto the same geometry you see and verify visibility before speaking.',
    modes: [
      {
        id: 'shared',
        label: 'Shared World State (0.37 cm)',
        badge: 'SHARED WORLD STATE · VERIFIED',
        metric: '0.37 cm median gaze error · 20/20 IDs',
        reticle: { left: '78%', top: '57%', anchored: true, tag: 'timber_shelter_01 · 0.37 cm' },
        log: `> visitor.gaze_raycast(yaw=+68.2°, pitch=-4.1°)
  world_state.hit   : node("timber_shelter_01")
  visibility_check  : PASSED (occluded=false)
  surface_error     : 0.37 cm median  [20/20 walk-and-gaze IDs]
  guide.response    : "That wooden shelter sits right beside the wet steps."`,
      },
      {
        id: 'separate',
        label: 'Separate Pipelines (5.13 cm drift)',
        badge: 'UNANCHORED PIPELINE · DRIFT',
        metric: '5.13 cm median gaze error',
        reticle: { left: '66%', top: '44%', anchored: false, tag: 'unanchored_guess · 5.13 cm drift' },
        log: `> visitor.gaze_raycast(yaw=+68.2°, pitch=-4.1°)
  separate_vlm_crop : ambiguous background bamboo (no shared depth graph)
  visibility_check  : SKIPPED
  surface_error     : 5.13 cm median  [gaze drifts off foreground edge]
  guide.response    : Guesses nearby stalks instead of the wooden shelter.`,
      },
    ],
  },
  edit: {
    img: 'assets/reading-room.png',
    alt: 'Quiet reading room local voice edit check',
    eyebrow: '02 / LOCALIZED VOICE EDITS & UNDO',
    heading: 'Change one object without smearing the room.',
    copy: 'Naive image-to-image regeneration leaks edits into untouched books, woodwork, and lighting. Sciescape bounds edits inside a typed scene-state commit with occlusion-aware background restoration—keeping 240/240 neighboring pixels intact and every change cleanly reversible.',
    modes: [
      {
        id: 'commit43',
        label: 'Apply Voice Edit (Commit #043)',
        badge: 'COMMIT #043 · 240/240 CLEAN NEIGHBORS',
        metric: '240/240 untouched pixels · reversible',
        patch: { left: '43%', top: '53%', width: '17%', height: '24%', clean: true, warm: true },
        log: `> visitor.speak("Warm the brass reading lamp on the center desk.")
  commit_id         : #043 (parent: #042)
  target_node       : node("emerald_lamp_03")
  neighbor_guard    : 240 / 240 untouched neighbor pixels verified
  background_restore: PASSED · instant rollback available via Undo`,
      },
      {
        id: 'commit42',
        label: 'Undo Commit (#043 → #042)',
        badge: 'COMMIT #042 · RESTORED EXACTLY',
        metric: 'Deterministic state rollback',
        patch: { left: '43%', top: '53%', width: '17%', height: '24%', clean: true, warm: false },
        log: `> world_state.checkout(commit=#042)
  reverted_node     : node("emerald_lamp_03") -> original emerald shade
  scene_hash        : byte-identical geometry & lighting restored
  automated_suite   : 573 / 573 tests passing solo`,
      },
      {
        id: 'smear',
        label: 'Unconstrained Pixel Edit (Baseline)',
        badge: 'UNCONSTRAINED BASELINE · NEIGHBOR DRIFT',
        metric: 'Surrounding shelves & lighting altered',
        patch: { left: '28%', top: '34%', width: '48%', height: '54%', clean: false, warm: true },
        log: `> baseline.regenerate_frame("Warm the brass reading lamp...")
  commit_id         : NONE (disposable pixels)
  neighbor_guard    : FAILED — bookshelf alignment & table grain drifted
  rollback          : UNAVAILABLE`,
      },
    ],
  },
  frontier: {
    img: 'assets/hut.png',
    alt: 'Alpine mountain hut doorway looking onto snow peak',
    eyebrow: '03 / FALSIFIABLE P1–P5 PROTOCOL & HONEST FRONTIER',
    heading: 'Honest about what still breaks—and how we test it.',
    copy: 'Single-view depth looks sharp from the front, but walking all the way behind an edited object opens geometric voids (2 of 21 early local dev cases passed full multi-view criteria). Our next 48–80 GB GPU runs freeze 21 unseen scenes and publish every failure alongside wins.',
    modes: [
      {
        id: 'protocol',
        label: 'Frozen 21-Scene Disproof Suite (P1–P5)',
        badge: 'ACTIVE 48–80 GB GPU FRONTIER',
        metric: '21 unseen scenes · 2 seeds · Apache-2.0',
        reticle: { left: '61%', top: '51%', anchored: true, tag: 'doorway_portal_01 · walk-behind check' },
        log: `> benchmark.status(suite="P1-P5_held_out")
  open_runner       : 23 / 23 Apache-2.0 resumable batch tests passing
  held_out_study    : 21 frozen prompts · 2 seeds · 240 voice-grounding runs
  strict_rule       : timeouts count as failures · negative results published
  live_gpu_demo     : huggingface.co/spaces/Navish/sciescape-world-benchmark`,
      },
      {
        id: 'baseline',
        label: 'Why 48–80 GB GPUs Matter Next',
        badge: 'HONEST LIMITATION LOGGED',
        metric: '2/21 early local dev baseline',
        reticle: { left: '34%', top: '60%', anchored: false, tag: 'walk_behind_occlusion · needs 48-80 GB' },
        log: `> frontier.open_problems()
  [1] 360° walk-behind geometry on edited objects (2/21 local dev pass)
  [2] Close-up lifelike conversational guide synced to scene state
  [3] Sub-second multi-view splat updates within browser WebGPU budgets
  next_step         : Click "Run Live GPU 3D Surface Lab" to inspect live depth`,
      },
    ],
  },
};

let activeStateTab = 'gaze';
const stateImg = document.querySelector('#state-img');
const stateVisual = document.querySelector('#state-visual');
const stateReticle = document.querySelector('#state-reticle');
const reticleTag = document.querySelector('#reticle-tag');
const stateEditPatch = document.querySelector('#state-edit-patch');
const stateVisualBadge = document.querySelector('#state-visual-badge');
const stateVisualMetric = document.querySelector('#state-visual-metric');
const stateStepEyebrow = document.querySelector('#state-step-eyebrow');
const stateStepHeading = document.querySelector('#state-step-heading');
const stateStepCopy = document.querySelector('#state-step-copy');
const stateControls = document.querySelector('#state-controls');
const stateLog = document.querySelector('#state-log');

function renderStateMode(tabKey, modeId) {
  const cfg = stateConfig[tabKey];
  const mode = cfg.modes.find(m => m.id === modeId) || cfg.modes[0];
  stateVisualBadge.textContent = mode.badge;
  stateVisualMetric.textContent = mode.metric;
  stateLog.textContent = mode.log;

  stateControls.querySelectorAll('.mode-pill').forEach(btn => {
    btn.setAttribute('aria-pressed', String(btn.dataset.mode === mode.id));
  });

  stateVisual.classList.toggle('is-warm-edit', Boolean(mode.patch?.warm));
  stateVisual.classList.toggle('is-smear', Boolean(mode.patch && !mode.patch.clean));

  if (mode.reticle) {
    stateReticle.hidden = false;
    stateReticle.style.left = mode.reticle.left;
    stateReticle.style.top = mode.reticle.top;
    stateReticle.classList.toggle('is-anchored', mode.reticle.anchored);
    stateReticle.classList.toggle('is-drift', !mode.reticle.anchored);
    reticleTag.textContent = mode.reticle.tag;
  } else {
    stateReticle.hidden = true;
  }

  if (mode.patch) {
    stateEditPatch.hidden = false;
    stateEditPatch.style.left = mode.patch.left;
    stateEditPatch.style.top = mode.patch.top;
    stateEditPatch.style.width = mode.patch.width;
    stateEditPatch.style.height = mode.patch.height;
    stateEditPatch.classList.toggle('is-clean', mode.patch.clean);
    stateEditPatch.classList.toggle('is-smear', !mode.patch.clean);
  } else {
    stateEditPatch.hidden = true;
  }
}

function selectStateTab(tabKey) {
  activeStateTab = tabKey;
  const cfg = stateConfig[tabKey];
  document.querySelectorAll('[data-state-tab]').forEach(btn => {
    btn.setAttribute('aria-selected', String(btn.dataset.stateTab === tabKey));
  });
  stateImg.src = cfg.img;
  stateImg.alt = cfg.alt;
  stateStepEyebrow.textContent = cfg.eyebrow;
  stateStepHeading.textContent = cfg.heading;
  stateStepCopy.textContent = cfg.copy;

  stateControls.innerHTML = '';
  cfg.modes.forEach((m, idx) => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'mode-pill';
    b.dataset.mode = m.id;
    b.setAttribute('aria-pressed', String(idx === 0));
    b.textContent = m.label;
    b.addEventListener('click', () => renderStateMode(tabKey, m.id));
    stateControls.appendChild(b);
  });
  renderStateMode(tabKey, cfg.modes[0].id);
}

if (stateControls) {
  document.querySelectorAll('[data-state-tab]').forEach(btn => {
    btn.addEventListener('click', () => selectStateTab(btn.dataset.stateTab));
  });
  selectStateTab('gaze');
}

// ================= INTERACTIVE 360° VIEWER + LIVE GAZE HUD =================
function formatSigned(num) {
  const r = Math.round(num);
  return `${r >= 0 ? '+' : '−'}${String(Math.abs(r)).padStart(2, '0')}°`;
}

function updateViewerHud(view) {
  if (!currentWorld || !worlds[currentWorld]) return;
  if (telemetryEl) {
    telemetryEl.textContent = `YAW ${formatSigned(view.yaw)} · PITCH ${formatSigned(view.pitch)} · FOV ${Math.round(view.fov)}°`;
  }
  const regions = worlds[currentWorld].regions || [];
  const match = regions.find(r => view.yaw >= r.yawMin && view.yaw <= r.yawMax) || regions[0];
  if (match && gazeNodeEl && gazeDescEl) {
    gazeNodeEl.textContent = `node: ${match.node}`;
    gazeDescEl.textContent = match.desc;
  }
}

function applyHudVisibility() {
  if (gazeBar) gazeBar.hidden = !hudEnabled;
  if (viewerReticle) viewerReticle.hidden = !hudEnabled;
  if (hudToggle) {
    hudToggle.setAttribute('aria-pressed', String(hudEnabled));
    hudToggle.textContent = hudEnabled ? 'Gaze HUD: On' : 'Gaze HUD: Off';
  }
}

if (hudToggle) {
  hudToggle.addEventListener('click', () => {
    hudEnabled = !hudEnabled;
    applyHudVisibility();
  });
}

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
  applyHudVisibility();
  try {
    if (!createPanorama) ({ createPanorama } = await import('./panorama.js'));
    if (version !== loadVersion || !dialog.open) return;
    if (!viewer) viewer = createPanorama(canvas, { onError: showFallback, onViewChange: updateViewerHud });
    await viewer.load(imagePath(id), { yaw: world.yaw, pitch: 0, fov: 75 });
    if (version !== loadVersion || !dialog.open) return;
    viewer.resize();
    updateViewerHud(viewer.getView());
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
    film?.pause();
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

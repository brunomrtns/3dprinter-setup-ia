import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

const MODES = [
  'mv_a_8k',
  'mv_b_8k',
  'mv_a_4k',
  'mv_b_4k',
  'hunyuan_21_posproc',
  'hunyuan_21',
  'hi3dgen',
  'kit',
  'casca',
  'interna',
  'kit_corte',
  'simetrico_interna',
  'simetrico_4vistas',
  'triposf512',
  'triposg',
  'hunyuan_mv_sf512',
  'hunyuan_mv',
  'posproc',
  'posproc_oco',
  'posproc_corte',
  'triposf256',
  'trellis2_fosco',
  'trellis2',
  'trellis',
  'triposr',
];
const MODE_LABEL = {
  mv_a_8k: '★ Grade 2x2 (8K)',
  mv_b_8k: '★ Fotos Reais (8K)',
  mv_a_4k: 'Grade 2x2 (4K Game-Ready)',
  mv_b_4k: 'Fotos Reais (4K Game-Ready)',
  hunyuan_21_posproc: '★ Hunyuan3D-2.1 + TripoSF 512 + Pós-proc (Pronto p/ Impressão)',
  hunyuan_21: '★ Hunyuan3D-2.1 (4096 latents MoE)',
  hi3dgen: '★ Hi3DGen (Normal-Bridging)',
  kit: '★ Kit Montado (CSG + 4 Rodas + Interna)',
  casca: 'Peça 1: Casca Carroceria (Janelas CSG)',
  interna: 'Peças 2+3: Banheira Interna + 4 Rodas',
  kit_corte: 'Corte Transversal do Kit',
  simetrico_interna: '★ Simétrico + Blueprint (Interna s/ Vidro)',
  simetrico_4vistas: '★ Simétrico + Blueprint (4 Vistas)',
  triposf512: 'TripoSF 512',
  triposg: 'TripoSG',
  hunyuan_mv_sf512: 'Hunyuan 2mv + TripoSF 512',
  hunyuan_mv: 'Hunyuan 2mv (4 vistas)',
  posproc: 'Pós-proc (Sólido)',
  posproc_oco: 'Pós-proc (Oco)',
  posproc_corte: 'Corte Oco',
  triposf256: 'TripoSF 256',
  trellis2_fosco: 'TRELLIS.2 (Vidro Fosco)',
  trellis2: 'TRELLIS.2',
  trellis: 'TRELLIS 1',
  triposr: 'TripoSR',
};
const VIEW_DIR = new THREE.Vector3(0.72, 0.34, 1.0).normalize();

const stage = document.getElementById('stage');
const casesEl = document.getElementById('cases');
const selCase = document.getElementById('selCase');
const selModeA = document.getElementById('selModeA');
const btnSwap = document.getElementById('btnSwap');
const btnAuto = document.getElementById('btnAuto');
const btnVs = document.getElementById('btnVs');
const btnReset = document.getElementById('btnReset');
const btnInfo = document.getElementById('btnInfo');
const btnShare = document.getElementById('btnShare');
const toastEl = document.getElementById('toast');
const infoDialog = document.getElementById('infoDialog');
const infoTitle = document.getElementById('infoTitle');
const infoBody = document.getElementById('infoBody');

const loader = new GLTFLoader();

let manifest = null;
let state = { caseId: null, vs: false, auto: true, sel: [null, null] };
let vps = [];
let activeDragIndex = -1;
let syncingCam = false;
let toastTimer = null;

// ---------- helpers ----------
function showToast(msg) {
  toastEl.textContent = msg;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), 2200);
}

function syncUrl() {
  const q = new URLSearchParams();
  if (state.caseId) q.set('case', state.caseId);
  if (state.sel[0]) q.set('mode', state.sel[0]);
  if (state.vs) {
    q.set('vs', '1');
    if (state.sel[1]) q.set('mode2', state.sel[1]);
  }
  if (!state.auto) q.set('auto', '0');
  history.replaceState(null, '', location.pathname + (q.toString() ? '?' + q : ''));
}

function setAuto(on, quiet) {
  state.auto = on;
  vps.forEach(v => { v.controls.autoRotate = on; });
  btnAuto.classList.toggle('on', on);
  btnAuto.setAttribute('aria-pressed', String(on));
  btnAuto.setAttribute('aria-label', on ? 'Pausar giro automático' : 'Retomar giro automático');
  btnAuto.innerHTML = `<span aria-hidden="true">${on ? '⏸' : '▶'}</span>`;
  if (!quiet) syncUrl();
}

function syncVsButton() {
  btnVs.classList.toggle('on', state.vs);
  btnVs.setAttribute('aria-pressed', String(state.vs));
}

function currentCase() {
  return manifest.cases.find(c => c.id === state.caseId);
}

// ---------- enquadramento automático (portrait / landscape / VS) ----------
function fitCamera(v, resetUserFlag = false) {
  if (!v || !v.bounds) return;
  const { center, size } = v.bounds;
  const aspect = Math.max(v.camera.aspect || 1, 0.25);
  const vFov = THREE.MathUtils.degToRad(v.camera.fov);
  const tanHalfV = Math.tan(vFov / 2);
  const tanHalfH = tanHalfV * aspect;

  // Cilindro de rotação em Y: mantém o objeto 100% visível durante todo o giro 360°
  const halfH = size.y / 2;
  const horizR = Math.hypot(size.x, size.z) / 2;
  const sinE = VIEW_DIR.y;
  const cosE = Math.hypot(VIEW_DIR.x, VIEW_DIR.z);

  const extV = halfH * cosE + horizR * sinE;
  const extH = horizR;
  const depth = horizR * cosE + halfH * sinE;

  // Margem confortável para o modelo ficar grande e inteiro sem encostar nas bordas
  const pad = window.innerWidth <= 640 ? 1.12 : 1.18;
  const distV = extV / tanHalfV;
  const distH = extH / tanHalfH;
  const dist = (Math.max(distV, distH) + depth * 0.45) * pad;

  v.controls.target.copy(center);
  v.camera.position.copy(center).addScaledVector(VIEW_DIR, dist);
  v.controls.minDistance = Math.max(0.25, dist * 0.22);
  v.controls.maxDistance = Math.max(12, dist * 4);
  v.camera.near = Math.max(0.01, dist / 200);
  v.camera.far = Math.max(100, dist * 20);
  v.camera.updateProjectionMatrix();
  v.controls.update();
  if (resetUserFlag) v.userMoved = false;
}

function syncCameraFrom(srcIdx) {
  if (!state.vs || syncingCam || vps.length < 2) return;
  const src = vps[srcIdx];
  const dst = vps[1 - srcIdx];
  if (!src || !dst) return;
  syncingCam = true;
  try {
    const offset = src.camera.position.clone().sub(src.controls.target);
    const dstCenter = dst.bounds ? dst.bounds.center : dst.controls.target;
    const srcCenter = src.bounds ? src.bounds.center : src.controls.target;
    const targetDelta = src.controls.target.clone().sub(srcCenter);
    dst.controls.target.copy(dstCenter).add(targetDelta);
    dst.camera.position.copy(dst.controls.target).add(offset);
    dst.userMoved = true;
    dst.controls.update();
  } finally {
    syncingCam = false;
  }
}

// ---------- viewport ----------
function makeViewport(index) {
  const label = index === 0 ? 'A' : 'B';
  const vp = document.createElement('div');
  vp.className = 'vp';
  vp.innerHTML = `
    <div class="vp-bar">
      <span class="vp-badge" aria-hidden="true">${label}</span>
      <select class="vp-sel" data-role="vpsel" aria-label="Gerador painel ${label}"></select>
    </div>
    <div class="vp-canvas-wrap" data-role="wrap">
      <div class="tag" data-role="tag">—</div>
      <div class="modes" data-role="modes"></div>
      <div class="spin" data-role="spin">carregando…</div>
      <div class="info" data-role="info"></div>
    </div>`;
  stage.appendChild(vp);

  const wrap = vp.querySelector('[data-role=wrap]');
  const vpSel = vp.querySelector('[data-role=vpsel]');
  vpSel.onchange = e => selectMode(index, e.target.value);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;
  wrap.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0d10);
  const pmrem = new THREE.PMREMGenerator(renderer);
  const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
  scene.environment = envTex;

  const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 100);
  camera.position.set(2.2, 1.4, 2.2);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.autoRotate = state.auto;
  controls.autoRotateSpeed = 1.6;
  controls.minDistance = 0.4;
  controls.maxDistance = 15;

  const hemi = new THREE.HemisphereLight(0xdfe8ff, 0x1a1d22, 0.55);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 1.4);
  dir.position.set(3, 5, 4);
  scene.add(dir);
  const rim = new THREE.DirectionalLight(0x88aaff, 0.5);
  rim.position.set(-4, 2, -3);
  scene.add(rim);

  const v = {
    index,
    el: vp,
    wrap,
    vpSel,
    scene,
    camera,
    controls,
    renderer,
    pmrem,
    envTex,
    group: null,
    bounds: null,
    userMoved: false,
    rafId: 0,
    ro: null,
    spin: vp.querySelector('[data-role=spin]'),
    info: vp.querySelector('[data-role=info]'),
    tag: vp.querySelector('[data-role=tag]'),
    modesEl: vp.querySelector('[data-role=modes]'),
  };

  // Interagir com a peça (arrastar/pinçar) pausa o giro automático e sincroniza no VS
  controls.addEventListener('start', () => {
    activeDragIndex = index;
    v.userMoved = true;
    if (state.auto) setAuto(false);
  });
  controls.addEventListener('change', () => {
    if (activeDragIndex === index) syncCameraFrom(index);
  });
  controls.addEventListener('end', () => {
    if (activeDragIndex === index) activeDragIndex = -1;
  });

  // Botões de modo dentro do viewport (desktop)
  MODES.forEach(m => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip';
    b.textContent = MODE_LABEL[m];
    b.onclick = () => selectMode(index, m);
    v.modesEl.appendChild(b);
  });

  function resize() {
    const w = wrap.clientWidth;
    const h = wrap.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
    if (v.bounds && !v.userMoved) fitCamera(v);
  }
  v.ro = new ResizeObserver(resize);
  v.ro.observe(wrap);
  resize();

  function loop() {
    v.rafId = requestAnimationFrame(loop);
    controls.update();
    renderer.render(scene, camera);
  }
  v.rafId = requestAnimationFrame(loop);

  return v;
}

function disposeViewport(v) {
  cancelAnimationFrame(v.rafId);
  v.ro?.disconnect();
  v.controls.dispose();
  v.envTex?.dispose();
  v.pmrem?.dispose();
  v.renderer.dispose();
  v.el.remove();
}

function rebuildViewports() {
  vps.forEach(disposeViewport);
  vps = [];
  const n = state.vs ? 2 : 1;
  stage.classList.toggle('vs', state.vs);
  for (let i = 0; i < n; i++) vps.push(makeViewport(i));
  renderMBar();
  refreshAll();
}

// ---------- dados & carregamento ----------
function selectMode(i, mode) {
  const c = currentCase();
  if (!c || !c.modes[mode]) return;
  state.sel[i] = mode;
  renderMBar();
  refreshViewport(i);
  syncUrl();
}

function fillModeSelect(sel, c, selectedMode) {
  sel.innerHTML = '';
  MODES.filter(m => c.modes[m]).forEach(m => {
    const o = document.createElement('option');
    o.value = m;
    o.textContent = MODE_LABEL[m];
    sel.appendChild(o);
  });
  sel.value = selectedMode || '';
}

function refreshViewport(i) {
  const v = vps[i];
  if (!v) return;
  const c = currentCase();
  const mode = state.sel[i];
  const info = mode && c && c.modes[mode];

  v.modesEl.querySelectorAll('.chip').forEach((b, j) => {
    const hasMode = Boolean(c && c.modes[MODES[j]]);
    b.classList.toggle('on', MODES[j] === mode);
    b.style.display = hasMode ? '' : 'none';
  });
  if (c) fillModeSelect(v.vpSel, c, mode);

  if (!info) {
    v.tag.textContent = MODE_LABEL[mode] || '—';
    v.info.textContent = 'sem modelo neste caso';
    if (v.group) { v.scene.remove(v.group); v.group = null; }
    v.bounds = null;
    v.spin.style.display = 'none';
    return;
  }

  v.tag.textContent = `${MODE_LABEL[mode]} — ${c.id}`;
  v.info.textContent = `${info.faces?.toLocaleString('pt-BR')} faces · ${info.verts?.toLocaleString('pt-BR')} verts · ${info.tempo_s ?? '—'}s · VRAM ${info.vram ?? '—'}MiB`;
  v.spin.textContent = 'carregando…';
  v.spin.style.display = 'flex';

  const req = (v._req = (v._req || 0) + 1);
  loader.load(`models/${c.id}__${mode}.glb?v=14`, g => {
    if (v._req !== req) return;
    v.spin.style.display = 'none';
    if (v.group) v.scene.remove(v.group);

    const grp = new THREE.Group();
    g.scene.traverse(o => {
      if (o.isMesh) {
        if (!o.geometry.attributes.normal) o.geometry.computeVertexNormals();
        const tex = o.material && o.material.map ? o.material.map : null;
        if (tex) {
          // GLB 3D texturizado: garante sRGB explícito e material neutro sem acinzentar branco
          tex.colorSpace = THREE.SRGBColorSpace;
          tex.needsUpdate = true;
          o.material = new THREE.MeshStandardMaterial({
            map: tex,
            roughness: 0.65,
            metalness: 0.0,
            envMapIntensity: 0.85,
            side: THREE.DoubleSide,
          });
        } else {
          o.material = new THREE.MeshStandardMaterial({
            color: 0xbfc4cc,
            roughness: 0.55,
            metalness: 0.05,
            side: THREE.DoubleSide,
            flatShading: mode.startsWith('trellis2'),
          });
        }
        o.castShadow = o.receiveShadow = false;
      }
    });
    grp.add(g.scene);

    // Normaliza: maior dim = 1.6, base em y=0, centro x/z = 0
    grp.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(grp);
    const size = box.getSize(new THREE.Vector3());
    const dim = Math.max(size.x, size.y, size.z) || 1;
    grp.scale.setScalar(1.6 / dim);
    grp.updateMatrixWorld(true);

    const box2 = new THREE.Box3().setFromObject(grp);
    const c2 = box2.getCenter(new THREE.Vector3());
    grp.position.x -= c2.x;
    grp.position.z -= c2.z;
    grp.position.y -= box2.min.y;
    grp.updateMatrixWorld(true);

    const finalBox = new THREE.Box3().setFromObject(grp);
    v.bounds = {
      center: finalBox.getCenter(new THREE.Vector3()),
      size: finalBox.getSize(new THREE.Vector3()),
    };
    v.scene.add(grp);
    v.group = grp;

    // Garante aspect atualizado antes de enquadrar
    const w = v.wrap.clientWidth;
    const h = v.wrap.clientHeight;
    if (w && h) {
      v.renderer.setSize(w, h, false);
      v.camera.aspect = w / h;
    }
    fitCamera(v, true);
  }, undefined, () => {
    if (v._req !== req) return;
    v.spin.textContent = 'erro ao carregar';
  });
}

function refreshAll() {
  vps.forEach((v, i) => refreshViewport(i));
}

// ---------- UI ----------
function pickCase(id) {
  state.caseId = id;
  const c = currentCase();
  const avail = MODES.filter(m => c.modes[m]);
  if (!avail.includes(state.sel[0])) state.sel[0] = avail[0] || null;
  if (!avail.includes(state.sel[1])) state.sel[1] = avail[1] || avail[0] || null;
  renderCaseChips();
  renderMBar();
  refreshAll();
  syncUrl();
}

function renderMBar() {
  const c = currentCase();
  if (!c) return;
  if (selCase.options.length !== manifest.cases.length) {
    selCase.innerHTML = '';
    manifest.cases.forEach(cs => {
      const o = document.createElement('option');
      o.value = cs.id;
      o.textContent = cs.id;
      selCase.appendChild(o);
    });
  }
  selCase.value = state.caseId;
  fillModeSelect(selModeA, c, state.sel[0]);
  // No modo VS mobile, cada painel tem seu próprio seletor (A/B) — barra superior fica limpa com Caso + Inverter
  selModeA.hidden = state.vs;
  btnSwap.hidden = !state.vs;
  vps.forEach((v, i) => fillModeSelect(v.vpSel, c, state.sel[i]));
}

function renderCaseChips() {
  casesEl.innerHTML = '';
  manifest.cases.forEach(c => {
    const b = document.createElement('button');
    b.type = 'button';
    b.className = 'chip' + (c.id === state.caseId ? ' on' : '');
    b.textContent = c.id;
    b.onclick = () => pickCase(c.id);
    casesEl.appendChild(b);
  });
}

function openInfoDialog() {
  const c = currentCase();
  if (!c) return;
  infoTitle.textContent = c.id;
  const indices = state.vs ? [0, 1] : [0];
  const cards = indices.map(i => {
    const mode = state.sel[i];
    const m = mode && c.modes[mode];
    const prefix = state.vs ? `${i === 0 ? 'Painel A' : 'Painel B'} · ` : '';
    const title = `${prefix}${MODE_LABEL[mode] || '—'}`;
    if (!m) return `<div class="dlg-card"><div class="dlg-card-title">${title}</div><div class="dlg-meta">Sem modelo neste caso</div></div>`;
    const manifold = m.manifold_depois == null ? '—' : (m.manifold_depois ? 'sim' : 'não');
    return `
      <div class="dlg-card">
        <div class="dlg-card-title">${title}</div>
        <div class="dlg-meta">
          Faces: ${m.faces?.toLocaleString('pt-BR') ?? '—'} · Vértices: ${m.verts?.toLocaleString('pt-BR') ?? '—'}<br>
          Tempo: ${m.tempo_s ?? '—'}s · VRAM pico: ${m.vram ?? '—'} MiB · Manifold: ${manifold}
        </div>
      </div>`;
  }).join('');
  infoBody.innerHTML = `
    <div style="color:var(--mut);font-size:12px;margin-bottom:10px">${c.category || 'Comparativo local (Fase C)'}</div>
    ${cards}
    <div class="dlg-tip">Arraste para girar · Pinça/scroll para zoom · Toque em ⟲ para reenquadrar.${state.vs ? ' No modo VS, os dois modelos giram sincronizados.' : ''}</div>`;
  infoDialog.showModal();
}

// Fallback de light-dismiss para navegadores sem <dialog closedby="any"> (ex.: Safari)
if (!('closedBy' in HTMLDialogElement.prototype)) {
  const outside = (e, dlg) => {
    const r = dlg.getBoundingClientRect();
    return e.clientX < r.left || e.clientX > r.right || e.clientY < r.top || e.clientY > r.bottom;
  };
  let pressedOutside = false;
  infoDialog.addEventListener('pointerdown', e => { pressedOutside = outside(e, infoDialog); });
  infoDialog.addEventListener('pointerup', e => { if (pressedOutside && outside(e, infoDialog)) infoDialog.close(); });
}

selCase.onchange = e => pickCase(e.target.value);
selModeA.onchange = e => selectMode(0, e.target.value);
btnSwap.onclick = () => {
  if (!state.vs) return;
  [state.sel[0], state.sel[1]] = [state.sel[1], state.sel[0]];
  renderMBar();
  refreshAll();
  syncUrl();
};

btnAuto.onclick = () => setAuto(!state.auto);
btnVs.onclick = () => {
  state.vs = !state.vs;
  syncVsButton();
  rebuildViewports();
  syncUrl();
};
btnReset.onclick = () => {
  vps.forEach(v => fitCamera(v, true));
};
btnInfo.onclick = openInfoDialog;
btnShare.onclick = async () => {
  syncUrl();
  const url = location.href;
  try {
    await navigator.clipboard.writeText(url);
    showToast('Link copiado!');
  } catch {
    prompt('Copie o link da view atual:', url);
  }
};

// ---------- boot ----------
manifest = await fetch('manifest.json?v=14').then(r => r.json());
const qs = new URLSearchParams(location.search);
const wantCase = manifest.cases.find(c => c.id === qs.get('case')) || manifest.cases[0];
state.caseId = wantCase.id;
{
  const avail = MODES.filter(m => wantCase.modes[m]);
  const m1 = avail.includes(qs.get('mode')) ? qs.get('mode') : (avail[0] || null);
  const m2 = avail.includes(qs.get('mode2')) ? qs.get('mode2') : (avail[1] || avail[0] || null);
  state.sel = [m1, m2];
  state.vs = qs.get('vs') === '1';
}
syncVsButton();
renderCaseChips();
rebuildViewports();
setAuto(qs.get('auto') !== '0', true);
syncUrl();

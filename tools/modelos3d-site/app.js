import * as THREE from 'three';
import { OrbitControls } from 'three/addons/OrbitControls.js';
import { GLTFLoader } from 'three/addons/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/RoomEnvironment.js';

const MODES = ['trellis2', 'triposg', 'trellis', 'triposr'];
const MODE_LABEL = { trellis2: 'TRELLIS.2', triposg: 'TripoSG', trellis: 'TRELLIS 1', triposr: 'TripoSR' };
const stage = document.getElementById('stage');
const casesEl = document.getElementById('cases');
const loader = new GLTFLoader();

let manifest = null;
let state = { caseId: null, vs: false, auto: true, sel: [{}, {}] }; // sel[i] = mode por viewport

// ---------- viewport ----------
function makeViewport(index) {
  const vp = document.createElement('div');
  vp.className = 'vp';
  vp.innerHTML = `
    <div class="tag" data-role="tag">—</div>
    <div class="modes" data-role="modes" style="position:absolute;top:34px;left:8px;right:8px;display:flex;gap:4px;overflow-x:auto;scrollbar-width:none;z-index:3"></div>
    <div class="spin" data-role="spin">carregando…</div>
    <div class="info" data-role="info"></div>`;
  stage.appendChild(vp);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  vp.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x0b0d10);
  const pmrem = new THREE.PMREMGenerator(renderer);
  scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

  const camera = new THREE.PerspectiveCamera(40, 1, 0.01, 100);
  camera.position.set(2.2, 1.6, 2.2);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.autoRotate = state.auto;
  controls.autoRotateSpeed = 1.6;
  controls.minDistance = 0.5;
  controls.maxDistance = 15;

  const hemi = new THREE.HemisphereLight(0xdfe8ff, 0x1a1d22, 0.5);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 1.4);
  dir.position.set(3, 5, 4);
  scene.add(dir);
  const rim = new THREE.DirectionalLight(0x88aaff, 0.5);
  rim.position.set(-4, 2, -3);
  scene.add(rim);

  const v = {
    el: vp, scene, camera, controls, renderer,
    group: null, cur: null,
    spin: vp.querySelector('[data-role=spin]'),
    info: vp.querySelector('[data-role=info]'),
    tag: vp.querySelector('[data-role=tag]'),
    modesEl: vp.querySelector('[data-role=modes]'),
  };

  // botões de modo dentro do viewport
  MODES.forEach(m => {
    const b = document.createElement('button');
    b.className = 'chip'; b.style.cssText = 'padding:5px 10px;font-size:11px;flex:0 0 auto';
    b.textContent = MODE_LABEL[m];
    b.onclick = () => selectMode(index, m);
    v.modesEl.appendChild(b);
  });

  function resize() {
    const w = vp.clientWidth, h = vp.clientHeight;
    if (!w || !h) return;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  new ResizeObserver(resize).observe(vp);
  resize();

  (function loop() {
    requestAnimationFrame(loop);
    controls.update();
    renderer.render(scene, camera);
  })();

  return v;
}

let vps = [];

function rebuildViewports() {
  vps.forEach(v => { v.renderer.dispose(); v.el.remove(); });
  vps = [];
  const n = state.vs ? 2 : 1;
  stage.classList.toggle('vs', state.vs);
  for (let i = 0; i < n; i++) vps.push(makeViewport(i));
  refreshAll();
}

// ---------- dados ----------
function currentCase() {
  return manifest.cases.find(c => c.id === state.caseId);
}

function selectMode(i, mode) {
  const c = currentCase();
  if (!c || !c.modes[mode]) return;
  state.sel[i] = mode;
  refreshViewport(i);
}

function refreshViewport(i) {
  const v = vps[i];
  const c = currentCase();
  const mode = state.sel[i];
  const info = mode && c && c.modes[mode];
  v.modesEl.querySelectorAll('.chip').forEach((b, j) => {
    b.classList.toggle('on', MODES[j] === mode);
    b.style.opacity = (c && c.modes[MODES[j]]) ? '1' : '.3';
  });
  if (!info) {
    v.tag.textContent = MODE_LABEL[mode] || '—';
    v.info.textContent = 'sem modelo neste caso';
    if (v.group) { v.scene.remove(v.group); v.group = null; }
    v.spin.style.display = 'none';
    return;
  }
  v.tag.textContent = `${MODE_LABEL[mode]} — ${c.id}`;
  v.info.textContent = `${info.faces?.toLocaleString('pt-BR')} faces · ${info.verts?.toLocaleString('pt-BR')} verts · ${info.tempo_s ?? '—'}s · VRAM ${info.vram ?? '—'}MiB`;
  v.spin.style.display = 'flex';
  const req = (v._req = (v._req || 0) + 1);
  loader.load(`models/${c.id}__${mode}.glb`, g => {
    if (v._req !== req) return; // resposta velha de troca rápida de modelo
    v.spin.style.display = 'none';
    if (v.group) v.scene.remove(v.group);
    const grp = new THREE.Group();
    g.scene.traverse(o => {
      if (o.isMesh) {
        o.material = new THREE.MeshStandardMaterial({ color: 0xbfc4cc, roughness: 0.55, metalness: 0.05 });
        o.castShadow = o.receiveShadow = false;
      }
    });
    grp.add(g.scene);
    // normaliza: maior dim = 1.6, base em y=0, centro x/z = 0
    grp.updateMatrixWorld(true);
    const box = new THREE.Box3().setFromObject(grp);
    const size = box.getSize(new THREE.Vector3());
    const dim = Math.max(size.x, size.y, size.z) || 1;
    const s = 1.6 / dim;
    grp.scale.setScalar(s);
    grp.updateMatrixWorld(true);
    const box2 = new THREE.Box3().setFromObject(grp);
    const c2 = box2.getCenter(new THREE.Vector3());
    grp.position.x -= c2.x; grp.position.z -= c2.z;
    grp.position.y -= box2.min.y;
    v.scene.add(grp);
    v.group = grp;
    v.camera.position.set(1.6, 1.2, 1.6);
    v.controls.target.set(0, 0.8, 0);
    v.controls.update();
  }, undefined, () => { v.spin.textContent = 'erro ao carregar'; });
}

function refreshAll() {
  vps.forEach((v, i) => refreshViewport(i));
}

// ---------- UI ----------
function renderCaseChips() {
  casesEl.innerHTML = '';
  manifest.cases.forEach(c => {
    const b = document.createElement('button');
    b.className = 'chip' + (c.id === state.caseId ? ' on' : '');
    b.textContent = c.id;
    b.onclick = () => {
      state.caseId = c.id;
      // preserva seleções válidas; defaults: trellis2 / triposg
      const avail = MODES.filter(m => c.modes[m]);
      if (!avail.includes(state.sel[0])) state.sel[0] = avail[0] || null;
      if (!avail.includes(state.sel[1])) state.sel[1] = avail[1] || avail[0] || null;
      renderCaseChips();
      refreshAll();
    };
    casesEl.appendChild(b);
  });
}

document.getElementById('btnAuto').onclick = e => {
  state.auto = !state.auto;
  vps.forEach(v => v.controls.autoRotate = state.auto);
  e.target.classList.toggle('on', state.auto);
  e.target.textContent = `Girar: ${state.auto ? 'auto' : 'off'}`;
};
document.getElementById('btnVs').onclick = e => {
  state.vs = !state.vs;
  e.target.classList.toggle('on', state.vs);
  e.target.textContent = `Comparar: ${state.vs ? 'on' : 'off'}`;
  rebuildViewports();
};
document.getElementById('btnReset').onclick = () => {
  vps.forEach(v => {
    v.camera.position.set(1.6, 1.2, 1.6);
    v.controls.target.set(0, 0.8, 0);
    v.controls.update();
  });
};

// ---------- boot ----------
manifest = await fetch('manifest.json').then(r => r.json());
state.caseId = manifest.cases[0].id;
state.sel = [null, null];
renderCaseChips();
rebuildViewports();
document.getElementById('btnAuto').classList.add('on');

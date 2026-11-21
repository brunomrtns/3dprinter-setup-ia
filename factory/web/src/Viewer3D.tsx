import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

interface Props {
  glbUrl: string | null;
  has8k?: boolean;
  variant?: '4k' | '8k';
  onVariantChange?: (v: '4k' | '8k') => void;
}

type LightPreset = 'studio' | 'neutral' | 'dramatic';

export const Viewer3D: React.FC<Props> = ({ glbUrl, has8k, variant = '4k', onVariantChange }) => {
  const frameRef = useRef<HTMLDivElement>(null);
  const mountRef = useRef<HTMLDivElement>(null);
  const [mode, setMode] = useState<'painted' | 'clay'>('painted');
  const [lightPreset, setLightPreset] = useState<LightPreset>('studio');
  const [autoRotate, setAutoRotate] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [meshStats, setMeshStats] = useState<{ tris: number } | null>(null);

  const materialsRef = useRef<Array<{ mesh: THREE.Mesh; painted: THREE.Material; clay: THREE.Material }>>([]);
  const controlsRef = useRef<OrbitControls | null>(null);
  const fitRef = useRef<(() => void) | null>(null);
  const lightsRef = useRef<{ key: THREE.DirectionalLight; fill: THREE.DirectionalLight; rim: THREE.DirectionalLight; amb: THREE.AmbientLight; renderer: THREE.WebGLRenderer } | null>(null);

  useEffect(() => {
    const el = mountRef.current;
    if (!el || !glbUrl) return;
    setLoading(true);
    setError(null);
    setMeshStats(null);
    materialsRef.current = [];

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(42, el.clientWidth / Math.max(1, el.clientHeight), 0.01, 200);
    camera.position.set(1.9, 1.35, 1.9);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.08;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    el.innerHTML = '';
    el.appendChild(renderer.domElement);

    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;

    const amb = new THREE.AmbientLight(0xffffff, 0.35);
    const key = new THREE.DirectionalLight(0xffffff, 1.75);
    key.position.set(3.2, 5.2, 3.6);
    const fill = new THREE.DirectionalLight(0x9bd6ff, 0.55);
    fill.position.set(-3.5, 2.2, -2.5);
    const rim = new THREE.DirectionalLight(0x1fc2ab, 0.45);
    rim.position.set(0, 3.5, -4.5);
    scene.add(amb, key, fill, rim);
    lightsRef.current = { key, fill, rim, amb, renderer };

    const grid = new THREE.GridHelper(3.2, 16, 0x252736, 0x161822);
    grid.position.y = -0.002;
    scene.add(grid);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.2;
    controlsRef.current = controls;

    // Stop auto-rotate when user starts dragging (matches approved UX)
    const onControlStart = () => {
      controls.autoRotate = false;
      setAutoRotate(false);
    };
    controls.addEventListener('start', onControlStart);

    const loader = new GLTFLoader();
    loader.setWithCredentials(true);
    let cancelled = false;
    loader.load(
      glbUrl,
      (g) => {
        if (cancelled) return;
        const grp = new THREE.Group();
        const clayMat = new THREE.MeshStandardMaterial({
          color: 0xc2c8d4,
          roughness: 0.52,
          metalness: 0.05,
          side: THREE.DoubleSide,
        });

        let totalTris = 0;
        g.scene.traverse((o) => {
          if ((o as THREE.Mesh).isMesh) {
            const m = o as THREE.Mesh;
            const geo = m.geometry;
            if (!geo.attributes.normal) geo.computeVertexNormals();
            totalTris += geo.index ? Math.round(geo.index.count / 3) : Math.round((geo.attributes.position?.count || 0) / 3);
            const orig = m.material as THREE.MeshStandardMaterial;
            const tex = orig && orig.map ? orig.map : null;
            const hasPbr = Boolean(orig && (orig.metalnessMap || orig.roughnessMap));
            let paintedMat: THREE.Material;
            if (tex && hasPbr) {
              tex.colorSpace = THREE.SRGBColorSpace;
              tex.needsUpdate = true;
              orig.side = THREE.DoubleSide;
              paintedMat = orig;
            } else if (tex) {
              tex.colorSpace = THREE.SRGBColorSpace;
              tex.needsUpdate = true;
              paintedMat = new THREE.MeshPhysicalMaterial({
                map: tex,
                roughness: 0.55,
                metalness: 0.0,
                clearcoat: 0.4,
                clearcoatRoughness: 0.22,
                envMapIntensity: 0.7,
                side: THREE.DoubleSide,
              });
            } else {
              paintedMat = clayMat;
            }
            materialsRef.current.push({ mesh: m, painted: paintedMat, clay: clayMat });
            m.material = paintedMat;
          }
        });
        setMeshStats({ tris: totalTris });

        grp.add(g.scene);
        const box = new THREE.Box3().setFromObject(grp);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const maxDim = Math.max(size.x, size.y, size.z) || 1;
        const scale = 1.65 / maxDim;
        grp.scale.setScalar(scale);
        grp.position.set(-center.x * scale, -box.min.y * scale, -center.z * scale);
        scene.add(grp);

        const fitCamera = () => {
          const b2 = new THREE.Box3().setFromObject(grp);
          const c2 = b2.getCenter(new THREE.Vector3());
          const s2 = b2.getSize(new THREE.Vector3());
          const radius = Math.max(s2.x, s2.y, s2.z) * 0.65;
          const dist = radius / Math.sin((camera.fov * Math.PI) / 360) * 1.15;
          camera.position.set(c2.x + dist * 0.72, c2.y + dist * 0.44, c2.z + dist * 0.78);
          controls.target.copy(c2);
          controls.update();
        };
        fitRef.current = fitCamera;
        fitCamera();
        setMode('painted');
        setAutoRotate(true);
        controls.autoRotate = true;
        setLoading(false);
      },
      undefined,
      (err) => {
        if (cancelled) return;
        setError(`Falha ao carregar modelo 3D: ${String(err)}`);
        setLoading(false);
      }
    );

    let rafId = 0;
    const animate = () => {
      rafId = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const ro = new ResizeObserver(() => {
      if (!el) return;
      camera.aspect = el.clientWidth / Math.max(1, el.clientHeight);
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    });
    ro.observe(el);

    return () => {
      cancelled = true;
      cancelAnimationFrame(rafId);
      ro.disconnect();
      controls.removeEventListener('start', onControlStart);
      controls.dispose();
      pmrem.dispose();
      renderer.dispose();
    };
  }, [glbUrl]);

  useEffect(() => {
    for (const item of materialsRef.current) {
      item.mesh.material = mode === 'clay' ? item.clay : item.painted;
    }
  }, [mode]);

  useEffect(() => {
    if (controlsRef.current) {
      controlsRef.current.autoRotate = autoRotate;
    }
  }, [autoRotate]);

  useEffect(() => {
    const l = lightsRef.current;
    if (!l) return;
    if (lightPreset === 'studio') {
      l.amb.intensity = 0.35; l.key.intensity = 1.75; l.fill.intensity = 0.55; l.rim.intensity = 0.45; l.renderer.toneMappingExposure = 1.08;
    } else if (lightPreset === 'neutral') {
      l.amb.intensity = 0.75; l.key.intensity = 1.1; l.fill.intensity = 0.85; l.rim.intensity = 0.1; l.renderer.toneMappingExposure = 1.0;
    } else {
      l.amb.intensity = 0.15; l.key.intensity = 2.4; l.fill.intensity = 0.25; l.rim.intensity = 1.1; l.renderer.toneMappingExposure = 1.15;
    }
  }, [lightPreset]);

  function toggleFullscreen() {
    if (!frameRef.current) return;
    if (!document.fullscreenElement) {
      frameRef.current.requestFullscreen?.().catch(() => {});
    } else {
      document.exitFullscreen?.().catch(() => {});
    }
  }

  return (
    <div ref={frameRef} className="viewer-frame">
      <div className="viewer-toolbar">
        <div className="viewer-pill-group">
          <button className={`vt-btn ${mode === 'painted' ? 'active' : ''}`} onClick={() => setMode('painted')}>
            Pintado PBR
          </button>
          <button className={`vt-btn ${mode === 'clay' ? 'active' : ''}`} onClick={() => setMode('clay')}>
            Clay (Malha)
          </button>
        </div>

        <div className="viewer-pill-group">
          {onVariantChange && has8k && (
            <>
              <button className={`vt-btn ${variant === '4k' ? 'active' : ''}`} onClick={() => onVariantChange('4k')}>4K</button>
              <button className={`vt-btn ${variant === '8k' ? 'active' : ''}`} onClick={() => onVariantChange('8k')}>8K</button>
            </>
          )}
          <button
            className={`vt-btn ${lightPreset === 'studio' ? 'active' : ''}`}
            onClick={() => setLightPreset(lightPreset === 'studio' ? 'neutral' : lightPreset === 'neutral' ? 'dramatic' : 'studio')}
            title="Alternar iluminação"
          >
            Luz: {lightPreset === 'studio' ? 'Studio' : lightPreset === 'neutral' ? 'Neutra' : 'Dramática'}
          </button>
          <button className={`vt-btn ${autoRotate ? 'active' : ''}`} onClick={() => setAutoRotate((v) => !v)} title="Pausar/Retomar giro 360°">
            {autoRotate ? 'Pausar 360°' : 'Girar 360°'}
          </button>
          <button className="vt-btn" onClick={() => fitRef.current?.()} title="Centralizar câmera">
            Reset
          </button>
          <button className="vt-btn" onClick={toggleFullscreen} title="Tela cheia">
            Tela cheia
          </button>
        </div>
      </div>

      <div ref={mountRef} style={{ width: '100%', height: '100%' }} />

      {loading && (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', background: 'rgba(7,7,10,0.72)', backdropFilter: 'blur(4px)' }}>
          <div style={{ textAlign: 'center', display: 'grid', gap: 8 }}>
            <div style={{ fontSize: 13.5, fontWeight: 500 }}>Carregando modelo 3D ({variant.toUpperCase()})…</div>
            <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>Preparando materiais PBR e iluminação de estúdio</div>
          </div>
        </div>
      )}
      {error && (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: '#fda4af', padding: 24, textAlign: 'center' }}>
          {error}
        </div>
      )}
      {!glbUrl && !loading && (
        <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: 'var(--text-muted)', fontSize: 13.5 }}>
          Modelo 3D ainda em processamento no PC local.
        </div>
      )}

      <div className="viewer-hint">
        Arraste para girar · Scroll para zoom · Botão direito para mover
        {meshStats ? ` · ${meshStats.tris.toLocaleString('pt-BR')} triângulos` : ''}
      </div>
    </div>
  );
};

import React, { useEffect, useRef, useState } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/examples/jsm/environments/RoomEnvironment.js';

interface Props {
  glbUrl: string | null;
}

export const Viewer3D: React.FC<Props> = ({ glbUrl }) => {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [painted, setPainted] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const meshMatsRef = useRef<Array<{ mesh: THREE.Mesh; paintedMat: THREE.Material; clayMat: THREE.Material }>>([]);

  useEffect(() => {
    for (const item of meshMatsRef.current) {
      item.mesh.material = painted ? item.paintedMat : item.clayMat;
    }
  }, [painted]);

  useEffect(() => {
    const el = mountRef.current;
    if (!el || !glbUrl) return;

    setLoading(true);
    setErr(null);
    meshMatsRef.current = [];

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.NoToneMapping;
    el.innerHTML = '';
    el.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x0b0d10);
    const pmrem = new THREE.PMREMGenerator(renderer);
    const envTex = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    scene.environment = envTex;

    const camera = new THREE.PerspectiveCamera(40, el.clientWidth / Math.max(1, el.clientHeight), 0.01, 100);
    camera.position.set(2.0, 1.3, 2.0);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.autoRotate = true;
    controls.autoRotateSpeed = 1.4;
    controls.addEventListener('start', () => { controls.autoRotate = false; });

    scene.add(new THREE.HemisphereLight(0xdfe8ff, 0x1a1d22, 0.55));
    const dir = new THREE.DirectionalLight(0xffffff, 1.4);
    dir.position.set(3, 5, 4);
    scene.add(dir);

    const loader = new GLTFLoader();
    let cancelled = false;
    loader.load(
      glbUrl,
      (g) => {
        if (cancelled) return;
        const grp = new THREE.Group();
        const clayMat = new THREE.MeshStandardMaterial({
          color: 0xbfc4cc,
          roughness: 0.55,
          metalness: 0.05,
          side: THREE.DoubleSide,
        });

        g.scene.traverse((o) => {
          if ((o as THREE.Mesh).isMesh) {
            const m = o as THREE.Mesh;
            if (!m.geometry.attributes.normal) m.geometry.computeVertexNormals();
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
            meshMatsRef.current.push({ mesh: m, paintedMat, clayMat });
            m.material = painted ? paintedMat : clayMat;
          }
        });

        grp.add(g.scene);
        const box = new THREE.Box3().setFromObject(grp);
        const size = box.getSize(new THREE.Vector3());
        const center = box.getCenter(new THREE.Vector3());
        const maxD = Math.max(size.x, size.y, size.z, 0.001);
        grp.scale.setScalar(1.6 / maxD);
        grp.position.sub(center.multiplyScalar(1.6 / maxD));
        scene.add(grp);
        controls.target.set(0, 0, 0);
        controls.update();
        setLoading(false);
      },
      undefined,
      () => {
        if (!cancelled) {
          setErr('Não foi possível carregar o modelo 3D.');
          setLoading(false);
        }
      }
    );

    let raf = 0;
    const loop = () => {
      raf = requestAnimationFrame(loop);
      controls.update();
      renderer.render(scene, camera);
    };
    loop();

    const onResize = () => {
      if (!el) return;
      camera.aspect = el.clientWidth / Math.max(1, el.clientHeight);
      camera.updateProjectionMatrix();
      renderer.setSize(el.clientWidth, el.clientHeight);
    };
    window.addEventListener('resize', onResize);

    return () => {
      cancelled = true;
      cancelAnimationFrame(raf);
      window.removeEventListener('resize', onResize);
      controls.dispose();
      envTex.dispose();
      pmrem.dispose();
      renderer.dispose();
    };
  }, [glbUrl]);

  return (
    <div className="viewer-box">
      <div className="viewer-toolbar">
        <button className={`btn ${painted ? 'primary' : ''}`} onClick={() => setPainted(true)}>
          Pintado (PBR)
        </button>
        <button className={`btn ${!painted ? 'primary' : ''}`} onClick={() => setPainted(false)}>
          Sem pintura (Malha)
        </button>
      </div>
      {loading && <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: '#93a1b5' }}>Carregando modelo 3D…</div>}
      {err && <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', color: '#ef4444' }}>{err}</div>}
      <div ref={mountRef} style={{ width: '100%', height: '100%' }} />
    </div>
  );
};

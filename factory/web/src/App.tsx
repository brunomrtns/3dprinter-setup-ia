import React, { useEffect, useMemo, useRef, useState } from 'react';
import { apiFetch, downloadUrl, getSsoLoginUrl, redirectToSsoLogin, ssoLogout } from './api';
import { Viewer3D } from './Viewer3D';

const STAGE_PT: Record<string, string> = {
  preprocess: 'Limpando fotos',
  shape: 'Esculpindo malha',
  paint: 'Pintando em 8K',
  pbr: 'Aplicando PBR',
  pack: 'Empacotando GLB',
  qa: 'Conferindo QA',
  edit: 'Editando peça',
};

const GATE_PT: Record<string, string> = {
  lap_var: 'Nitidez da textura',
  bright_patches: 'Ausência de falhas brancas',
  saturation_band: 'Equilíbrio de cor',
  mr_pbr_present: 'Brilho / PBR real',
  glb_sizes_sane: 'Tamanho dos arquivos',
  photo_consistency: 'Fidelidade às fotos',
};

const STATUS_META: Record<string, { label: string; cls: string }> = {
  draft: { label: 'Rascunho', cls: 'neutral' },
  queued: { label: 'Na fila', cls: 'info' },
  claimed: { label: 'Iniciando no PC', cls: 'info' },
  running: { label: 'Processando', cls: 'info' },
  review: { label: 'Aguardando revisão', cls: 'warn' },
  published: { label: 'Publicada', cls: 'ok' },
  rejected: { label: 'Em ajuste', cls: 'warn' },
  failed: { label: 'Falhou', cls: 'err' },
};

const MODE_PT: Record<string, string> = {
  multi: 'Multi-foto',
  single: 'Foto única',
  mesh: 'Malha pronta',
};

type Page = 'home' | 'wizard' | 'queue' | 'detail';
type InspectorTab = 'qa' | 'chat' | 'files';

/* Crisp inline SVG icons (zero raw emoji UI) */
const IconCube = ({ size = 18 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 2.5L21 7.5V16.5L12 21.5L3 16.5V7.5L12 2.5Z" />
    <path d="M12 12L21 7.5M12 12L3 7.5M12 12V21.5" />
  </svg>
);

const IconGrid = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" />
  </svg>
);

const IconPlus = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.1" strokeLinecap="round">
    <path d="M12 5v14M5 12h14" />
  </svg>
);

const IconLayers = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 12 12 17 22 12" /><polyline points="2 17 12 22 22 17" />
  </svg>
);

const IconSearch = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
    <circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" />
  </svg>
);

const IconDownload = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 3v12m0 0l-4-4m4 4l4-4M4 19h16" />
  </svg>
);

const IconLogout = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><polyline points="16 17 21 12 16 7" /><line x1="21" y1="12" x2="9" y2="12" />
  </svg>
);

const IconArrowLeft = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M19 12H5m0 0l6 6m-6-6l6-6" />
  </svg>
);

const IconUpload = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" /><polyline points="17 8 12 3 7 8" /><line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

export const App: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [authChecking, setAuthChecking] = useState(true);

  const [page, setPage] = useState<Page>('home');
  const [assets, setAssets] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [worker, setWorker] = useState<any>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>('qa');
  const [viewerVariant, setViewerVariant] = useState<'4k' | '8k'>('4k');

  // Gallery filters
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Wizard state
  const [wStep, setWStep] = useState(1);
  const [wMode, setWMode] = useState<'single' | 'multi' | 'mesh'>('multi');
  const [wName, setWName] = useState('');
  const [wNotes, setWNotes] = useState('');
  const [wFiles, setWFiles] = useState<File[]>([]);
  const [wPreviews, setWPreviews] = useState<string[]>([]);
  const [wDragOver, setWDragOver] = useState(false);
  const [wPhotoWarning, setWPhotoWarning] = useState<string | null>(null);
  const [wSubmitting, setWSubmitting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Chat / Review state
  const [chatText, setChatText] = useState('');
  const [chatSending, setChatSending] = useState(false);
  const [rejectComment, setRejectComment] = useState('');
  const [showRejectBox, setShowRejectBox] = useState(false);

  async function refreshAll() {
    const [a, j, w] = await Promise.all([
      apiFetch<{ assets: any[] }>('/assets'),
      apiFetch<{ jobs: any[] }>('/jobs'),
      apiFetch<any>('/worker/status'),
    ]);
    setAssets(a.assets);
    setJobs(j.jobs);
    setWorker(w);
  }

  async function loadDetail(id: string) {
    const d = await apiFetch<{ asset: any }>(`/assets/${id}`);
    setDetail(d.asset);
  }

  useEffect(() => {
    apiFetch<{ user: any }>('/auth/me')
      .then((r) => {
        sessionStorage.removeItem('fab3d_sso_hops');
        setUser(r.user);
        setAuthChecking(false);
        refreshAll();
      })
      .catch(() => {
        setAuthChecking(false);
        const now = Date.now();
        const raw = sessionStorage.getItem('fab3d_sso_hops');
        const hops: number[] = raw ? JSON.parse(raw).filter((t: number) => now - t < 15000) : [];
        if (hops.length < 2) {
          hops.push(now);
          sessionStorage.setItem('fab3d_sso_hops', JSON.stringify(hops));
          redirectToSsoLogin();
        }
      });
  }, []);

  useEffect(() => {
    if (!user) return;
    const t = setInterval(() => {
      refreshAll().catch(() => {});
      if (page === 'detail' && selectedAssetId) loadDetail(selectedAssetId).catch(() => {});
    }, 8000);
    return () => clearInterval(t);
  }, [user, page, selectedAssetId]);

  function openAsset(id: string) {
    setSelectedAssetId(id);
    setDetail(null);
    setViewerVariant('4k');
    setInspectorTab('qa');
    setShowRejectBox(false);
    setPage('detail');
    loadDetail(id).catch(() => {});
  }

  function handleFiles(fileList: FileList | null) {
    if (!fileList) return;
    const arr = Array.from(fileList).slice(0, wMode === 'multi' ? 4 : 1);
    wPreviews.forEach((u) => URL.revokeObjectURL(u));
    const urls = arr.map((f) => (f.type.startsWith('image/') ? URL.createObjectURL(f) : ''));
    setWFiles(arr);
    setWPreviews(urls);
    setWPhotoWarning(null);
    if (wMode !== 'mesh' && urls[0]) {
      const img = new Image();
      img.onload = () => {
        if (img.width < 512 || img.height < 512) {
          setWPhotoWarning(
            `Resolução baixa detectada (${img.width}×${img.height}px). O recorte de fundo será automático; melhoria por IA externa está disponível quando ativada no worker.`
          );
        }
      };
      img.src = urls[0];
    }
  }

  async function onSubmitWizard() {
    if (!wName.trim() || wFiles.length === 0) return;
    setWSubmitting(true);
    try {
      const { asset } = await apiFetch<{ asset: any }>('/assets', {
        method: 'POST',
        body: JSON.stringify({ name: wName.trim(), mode: wMode, notes: wNotes.trim() }),
      });
      const fd = new FormData();
      wFiles.forEach((f) => fd.append('files', f));
      await apiFetch(`/assets/${asset.id}/inputs`, { method: 'POST', body: fd });
      await apiFetch('/jobs', { method: 'POST', body: JSON.stringify({ asset_id: asset.id }) });
      setWName('');
      setWNotes('');
      setWFiles([]);
      setWPreviews([]);
      setWStep(1);
      await refreshAll();
      setPage('queue');
    } catch (err: any) {
      alert(err.message);
    } finally {
      setWSubmitting(false);
    }
  }

  async function onSendChat(e: React.FormEvent) {
    e.preventDefault();
    if (!detail || !chatText.trim() || chatSending) return;
    setChatSending(true);
    try {
      await apiFetch(`/assets/${detail.id}/chat`, {
        method: 'POST',
        body: JSON.stringify({ content: chatText.trim() }),
      });
      setChatText('');
      await loadDetail(detail.id);
      await refreshAll();
    } finally {
      setChatSending(false);
    }
  }

  async function onApproveJob(jobId: string) {
    await apiFetch(`/jobs/${jobId}/approve`, { method: 'POST' });
    if (selectedAssetId) await loadDetail(selectedAssetId);
    await refreshAll();
  }

  async function onRejectJob(jobId: string) {
    await apiFetch(`/jobs/${jobId}/reject`, {
      method: 'POST',
      body: JSON.stringify({ comment: rejectComment }),
    });
    setRejectComment('');
    setShowRejectBox(false);
    if (selectedAssetId) await loadDetail(selectedAssetId);
    await refreshAll();
  }

  const activeJobsCount = useMemo(
    () => jobs.filter((j) => ['queued', 'claimed', 'running'].includes(j.status)).length,
    [jobs]
  );

  const reviewCount = useMemo(
    () => assets.filter((a) => a.status === 'review').length,
    [assets]
  );

  const publishedCount = useMemo(
    () => assets.filter((a) => a.status === 'published').length,
    [assets]
  );

  const filteredAssets = useMemo(() => {
    const q = search.trim().toLowerCase();
    return assets.filter((a) => {
      if (statusFilter !== 'all' && a.status !== statusFilter) return false;
      if (q && !a.name.toLowerCase().includes(q) && !(a.notes || '').toLowerCase().includes(q)) return false;
      return true;
    });
  }, [assets, search, statusFilter]);

  if (!user) {
    return (
      <div className="auth-splash">
        <div className="auth-card">
          <div className="brand-icon" style={{ width: 48, height: 48, borderRadius: 12 }}>
            <IconCube size={24} />
          </div>
          <h2 style={{ margin: 0, fontSize: 20, letterSpacing: '-0.02em' }}>Fábrica 3D</h2>
          <p style={{ margin: 0, color: 'var(--text-secondary)', fontSize: 13.5, lineHeight: 1.5 }}>
            {authChecking
              ? 'Verificando sua sessão Bruno Integrations…'
              : 'Redirecionando para o login unificado Bruno Integrations…'}
          </p>
          <a className="btn primary" href={getSsoLoginUrl('/fab3d/')} style={{ width: '100%', marginTop: 6 }}>
            Entrar com Bruno Integrations
          </a>
          <div style={{ fontSize: 11.5, color: 'var(--text-muted)' }}>
            Login com Google ou e-mail · Uso estritamente privado
          </div>
        </div>
      </div>
    );
  }

  const initials = (user.name || user.email || 'B')
    .split(/\s+/)
    .map((s: string) => s[0])
    .join('')
    .slice(0, 2)
    .toUpperCase();

  const totalVram = (worker?.vramUsedMib || 0) + (worker?.vramFreeMib || 0);
  const vramPct = totalVram > 0 ? Math.round(((worker?.vramUsedMib || 0) / totalVram) * 100) : 0;

  const latestJob = detail?.jobs?.[0];
  const verFiles = (detail?.versions?.[0]?.filesJson || {}) as Record<string, string>;
  const jobFiles = (latestJob?.resultsJson?.files || {}) as Record<string, string>;
  const filesMap = Object.keys(verFiles).length > 0 ? verFiles : jobFiles;
  const has4k = Boolean(filesMap.glb_4k);
  const has8k = Boolean(filesMap.glb_8k);
  const hasGlb = has4k || has8k;
  const effectiveVar: '4k' | '8k' = viewerVariant === '8k' && has8k ? '8k' : has4k ? '4k' : '8k';
  const viewerUrl = detail && hasGlb ? downloadUrl(detail.id, effectiveVar) : null;
  const qaObj = detail?.versions?.[0]?.qaJson || latestJob?.resultsJson?.qa || null;
  const statusInfo = STATUS_META[detail?.status || 'draft'] || STATUS_META.draft;

  return (
    <div className="app-shell">
      {/* Mobile Header */}
      <div className="mobile-bar">
        <div className="brand-lockup" style={{ padding: 0 }}>
          <div className="brand-icon" style={{ width: 28, height: 28 }}><IconCube size={16} /></div>
          <span className="brand-title">Fábrica 3D</span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button className={`btn sm ${page === 'home' ? 'primary' : ''}`} onClick={() => setPage('home')}>Peças</button>
          <button className={`btn sm ${page === 'wizard' ? 'primary' : ''}`} onClick={() => { setWStep(1); setPage('wizard'); }}>+ Nova</button>
          <button className={`btn sm ${page === 'queue' ? 'primary' : ''}`} onClick={() => setPage('queue')}>Fila ({activeJobsCount})</button>
        </div>
      </div>

      {/* Desktop Sidebar */}
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-icon"><IconCube size={19} /></div>
          <div>
            <div className="brand-title">Fábrica 3D</div>
            <div className="brand-sub">Bruno Integrations Studio</div>
          </div>
        </div>

        <nav className="nav-section">
          <div className="nav-label">Estúdio</div>
          <button className={`nav-item ${page === 'home' || page === 'detail' ? 'active' : ''}`} onClick={() => setPage('home')}>
            <span className="nav-item-left"><IconGrid /> Minhas Peças</span>
            <span className="nav-pill">{assets.length}</span>
          </button>
          <button className={`nav-item ${page === 'wizard' ? 'active' : ''}`} onClick={() => { setWStep(1); setPage('wizard'); }}>
            <span className="nav-item-left"><IconPlus /> Nova Peça</span>
          </button>
          <button className={`nav-item ${page === 'queue' ? 'active' : ''}`} onClick={() => setPage('queue')}>
            <span className="nav-item-left"><IconLayers /> Fila GPU</span>
            {activeJobsCount > 0 && <span className="nav-pill">{activeJobsCount}</span>}
          </button>
        </nav>

        <div className="sidebar-footer">
          <div className="worker-card">
            <div className="worker-head">
              <span>
                <span className={`status-dot ${worker?.online ? 'online' : 'offline'}`} />
                {worker?.online ? 'Worker RTX 3060' : 'PC Local Offline'}
              </span>
              <span style={{ fontSize: 11, color: worker?.online ? 'var(--ok)' : 'var(--accent-warm)' }}>
                {worker?.online ? 'Ativo' : 'Standby'}
              </span>
            </div>
            {worker?.online ? (
              <>
                <div className="vram-bar"><div className="vram-fill" style={{ width: `${vramPct}%` }} /></div>
                <div className="worker-meta">
                  <span>VRAM livre</span>
                  <span>{worker.vramFreeMib} MiB</span>
                </div>
              </>
            ) : (
              <div style={{ fontSize: 11.5, color: 'var(--text-muted)', lineHeight: 1.4 }}>
                Jobs ficam na fila e iniciam assim que o worker local conectar.
              </div>
            )}
          </div>

          <div className="user-card">
            <div className="avatar">{initials}</div>
            <div className="user-info">
              <div className="user-name">{user.name || 'Bruno'}</div>
              <div className="user-email">{user.email}</div>
            </div>
            <button className="icon-btn" onClick={() => ssoLogout()} title="Sair da conta">
              <IconLogout />
            </button>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="main-content scroller">
        {/* ── HOME / GALERIA ──────────────────────────────────────────────── */}
        {page === 'home' && (
          <div>
            <div className="page-header">
              <div>
                <h1 className="page-title">Minhas Peças 3D</h1>
                <p className="page-subtitle">Galeria PBR privada com inspeção interativa, revisão QA e downloads 8K/4K.</p>
              </div>
              <button className="btn primary" onClick={() => { setWStep(1); setPage('wizard'); }}>
                <IconPlus /> Nova Peça
              </button>
            </div>

            <div className="kpi-grid">
              <div className="kpi-card">
                <div className="kpi-label">Total na Biblioteca</div>
                <div className="kpi-value">{assets.length}</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Publicadas (Prontas)</div>
                <div className="kpi-value" style={{ color: 'var(--ok)' }}>{publishedCount}</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Aguardando Revisão</div>
                <div className="kpi-value" style={{ color: reviewCount > 0 ? 'var(--accent-warm)' : 'var(--text)' }}>{reviewCount}</div>
              </div>
              <div className="kpi-card">
                <div className="kpi-label">Jobs Ativos na GPU</div>
                <div className="kpi-value" style={{ color: activeJobsCount > 0 ? 'var(--accent)' : 'var(--text)' }}>{activeJobsCount}</div>
              </div>
            </div>

            <div className="toolbar">
              <div className="search-wrap">
                <IconSearch />
                <input
                  className="input"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Buscar peça por nome ou nota…"
                />
              </div>
              <div className="filter-pills">
                {[
                  ['all', 'Todas'],
                  ['published', 'Publicadas'],
                  ['review', 'Em revisão'],
                  ['running', 'Processando'],
                ].map(([key, label]) => (
                  <button
                    key={key}
                    className={`pill-btn ${statusFilter === key ? 'active' : ''}`}
                    onClick={() => setStatusFilter(key)}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </div>

            {filteredAssets.length === 0 ? (
              <div className="wizard-card" style={{ textAlign: 'center', padding: 48 }}>
                <div style={{ color: 'var(--text-muted)', marginBottom: 14 }}>Nenhuma peça encontrada com esse filtro.</div>
                <button className="btn primary" onClick={() => { setSearch(''); setStatusFilter('all'); }}>
                  Limpar filtros
                </button>
              </div>
            ) : (
              <div className="asset-grid">
                {filteredAssets.map((a) => {
                  const st = STATUS_META[a.status] || STATUS_META.draft;
                  const thumbKey = a.versions?.[0]?.filesJson?.thumbnail || a.jobs?.[0]?.resultsJson?.files?.thumbnail;
                  const hasModel = Boolean(a.versions?.[0]?.filesJson?.glb_8k || a.versions?.[0]?.filesJson?.glb_4k);
                  return (
                    <article key={a.id} className="asset-card" onClick={() => openAsset(a.id)}>
                      <div className="asset-thumb">
                        {thumbKey ? (
                          <img src={downloadUrl(a.id, '4k', thumbKey)} alt={a.name} loading="lazy" />
                        ) : (
                          <div className="asset-thumb-placeholder">
                            <IconCube size={38} />
                            <span style={{ fontSize: 11.5 }}>Modelo GLB · Clique para abrir em 3D</span>
                          </div>
                        )}
                        <div className="asset-thumb-badges">
                          <span className={`badge ${st.cls}`}>{st.label}</span>
                          <span className="badge neutral">v{a.currentVersion || 0}</span>
                        </div>
                      </div>
                      <div className="asset-body">
                        <h3 className="asset-name">{a.name}</h3>
                        <div className="asset-meta">
                          <span>{MODE_PT[a.mode] || a.mode}</span>
                          <span>·</span>
                          <span>{new Date(a.updatedAt).toLocaleDateString('pt-BR')}</span>
                        </div>
                        <div className="asset-actions" onClick={(e) => e.stopPropagation()}>
                          <button className="btn sm primary" onClick={() => openAsset(a.id)}>
                            Abrir Studio 3D
                          </button>
                          {hasModel && (
                            <div style={{ display: 'flex', gap: 6 }}>
                              <a className="btn sm" href={downloadUrl(a.id, '4k')} download title="Baixar GLB 4K">
                                <IconDownload /> 4K
                              </a>
                              <a className="btn sm" href={downloadUrl(a.id, '8k')} download title="Baixar GLB 8K">
                                <IconDownload /> 8K
                              </a>
                            </div>
                          )}
                        </div>
                      </div>
                    </article>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── WIZARD NOVA PEÇA ────────────────────────────────────────────── */}
        {page === 'wizard' && (
          <div>
            <div className="page-header">
              <div>
                <h1 className="page-title">Nova Peça 3D</h1>
                <p className="page-subtitle">Envie suas fotos ou malha — a Fábrica aplica automaticamente a receita PBR 8K aprovada.</p>
              </div>
              <button className="btn ghost" onClick={() => setPage('home')}><IconArrowLeft /> Voltar à galeria</button>
            </div>

            <div className="wizard-card">
              <div className="stepper">
                {[
                  [1, 'Modo de entrada'],
                  [2, 'Enviar arquivos'],
                  [3, 'Nome & confirmar'],
                ].map(([num, label]) => (
                  <div key={num as number} className={`step-chip ${wStep === num ? 'active' : wStep > (num as number) ? 'done' : ''}`}>
                    <span className="step-num">{wStep > (num as number) ? '✓' : num}</span>
                    <span>{label}</span>
                  </div>
                ))}
              </div>

              {wStep === 1 && (
                <div style={{ display: 'grid', gap: 20 }}>
                  <div className="mode-grid">
                    {[
                      ['multi', 'Múltiplas Fotos (2–4)', 'Frente, laterais e traseira para máxima fidelidade de pintura e geometria.'],
                      ['single', 'Foto Única', 'Ideal para miniaturas, personagens e props com uma boa foto de referência.'],
                      ['mesh', 'Malha Pronta (GLB/OBJ)', 'Já tem a geometria pronta? Envie direto para pintura PBR 8K automática.'],
                    ].map(([m, title, desc]) => (
                      <button
                        key={m}
                        type="button"
                        className={`mode-option ${wMode === m ? 'selected' : ''}`}
                        onClick={() => setWMode(m as any)}
                      >
                        <div style={{ color: wMode === m ? 'var(--accent)' : 'var(--text-secondary)' }}><IconCube size={22} /></div>
                        <div style={{ fontWeight: 600, fontSize: 14 }}>{title}</div>
                        <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.45 }}>{desc}</div>
                      </button>
                    ))}
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                    <button className="btn primary" onClick={() => setWStep(2)}>Continuar →</button>
                  </div>
                </div>
              )}

              {wStep === 2 && (
                <div style={{ display: 'grid', gap: 16 }}>
                  <div
                    className={`dropzone ${wDragOver ? 'dragover' : ''}`}
                    onClick={() => fileInputRef.current?.click()}
                    onDragOver={(e) => { e.preventDefault(); setWDragOver(true); }}
                    onDragLeave={() => setWDragOver(false)}
                    onDrop={(e) => {
                      e.preventDefault();
                      setWDragOver(false);
                      handleFiles(e.dataTransfer.files);
                    }}
                  >
                    <div style={{ color: 'var(--accent)' }}><IconUpload /></div>
                    <div style={{ fontWeight: 600, fontSize: 14 }}>
                      Arraste {wMode === 'mesh' ? 'seu arquivo .glb / .obj / .stl' : wMode === 'multi' ? 'até 4 fotos (PNG, JPG, WEBP)' : 'sua foto de referência'} aqui
                    </div>
                    <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>ou clique para selecionar do computador</div>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple={wMode === 'multi'}
                      accept={wMode === 'mesh' ? '.glb,.gltf,.obj,.stl' : 'image/png,image/jpeg,image/webp'}
                      onChange={(e) => handleFiles(e.target.files)}
                      style={{ display: 'none' }}
                    />
                  </div>

                  {wFiles.length > 0 && (
                    <div className="preview-grid">
                      {wFiles.map((f, idx) => (
                        <div key={idx} className="preview-tile">
                          {wPreviews[idx] ? (
                            <img src={wPreviews[idx]} alt={f.name} />
                          ) : (
                            <div style={{ height: '100%', display: 'grid', placeItems: 'center', padding: 8, textAlign: 'center', fontSize: 11, color: 'var(--text-secondary)' }}>
                              {f.name}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {wPhotoWarning && (
                    <div className="badge warn" style={{ borderRadius: 10, padding: '10px 14px', fontSize: 12.5 }}>
                      {wPhotoWarning}
                    </div>
                  )}

                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
                    <button className="btn" onClick={() => setWStep(1)}>← Voltar</button>
                    <button className="btn primary" disabled={wFiles.length === 0} onClick={() => setWStep(3)}>Continuar →</button>
                  </div>
                </div>
              )}

              {wStep === 3 && (
                <div style={{ display: 'grid', gap: 16 }}>
                  <div>
                    <label style={{ display: 'block', fontSize: 12.5, color: 'var(--text-secondary)', marginBottom: 6 }}>Nome da peça</label>
                    <input className="input" value={wName} onChange={(e) => setWName(e.target.value)} placeholder="Ex: Miniatura VW Fox 2012" />
                  </div>
                  <div>
                    <label style={{ display: 'block', fontSize: 12.5, color: 'var(--text-secondary)', marginBottom: 6 }}>Observações (opcional)</label>
                    <textarea className="textarea" rows={3} value={wNotes} onChange={(e) => setWNotes(e.target.value)} placeholder="Ex: manter rodas metálicas e vidros fumê…" />
                  </div>
                  <div style={{ padding: 14, borderRadius: 10, background: 'var(--surface-elevated)', border: '1px solid var(--border)', fontSize: 12.5, color: 'var(--text-secondary)', display: 'flex', justifyContent: 'space-between', flexWrap: 'wrap', gap: 8 }}>
                    <span>Modo: <strong style={{ color: 'var(--text)' }}>{MODE_PT[wMode]}</strong> · {wFiles.length} arquivo(s)</span>
                    <span>Receita padrão: <strong style={{ color: 'var(--accent)' }}>PBR 8K/4K + QA automático</strong></span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginTop: 6 }}>
                    <button className="btn" onClick={() => setWStep(2)}>← Voltar</button>
                    <button className="btn primary" disabled={!wName.trim() || wSubmitting} onClick={onSubmitWizard}>
                      {wSubmitting ? 'Enviando para a fila…' : 'Criar Peça na GPU'}
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── FILA GPU ────────────────────────────────────────────────────── */}
        {page === 'queue' && (
          <div>
            <div className="page-header">
              <div>
                <h1 className="page-title">Fila de Processamento GPU</h1>
                <p className="page-subtitle">Acompanhe em tempo real os jobs executados no seu PC com RTX 3060 12GB.</p>
              </div>
              <button className="btn primary" onClick={() => { setWStep(1); setPage('wizard'); }}>
                <IconPlus /> Nova Peça
              </button>
            </div>

            {jobs.length === 0 ? (
              <div className="wizard-card" style={{ textAlign: 'center', padding: 48, color: 'var(--text-muted)' }}>
                Nenhum job registrado ainda.
              </div>
            ) : (
              <div className="queue-list">
                {jobs.map((j) => {
                  const st = STATUS_META[j.status] || STATUS_META.draft;
                  return (
                    <div key={j.id} className="queue-card">
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <strong style={{ fontSize: 15 }}>{j.asset?.name || j.assetId}</strong>
                          <span className="badge neutral">{j.type === 'edit' ? 'Edição IA' : 'Nova peça'}</span>
                          <span className={`badge ${st.cls}`}>{st.label}</span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <span style={{ fontSize: 12, color: 'var(--text-secondary)', fontFamily: 'var(--font-mono)' }}>
                            {STAGE_PT[j.stage] || j.stage} · {j.progress}%
                          </span>
                          <button className="btn sm" onClick={() => openAsset(j.assetId)}>Abrir Studio</button>
                        </div>
                      </div>
                      <div className="progress-track">
                        <div className="progress-bar" style={{ width: `${j.progress}%` }} />
                      </div>
                      {j.error && <div style={{ fontSize: 12, color: '#fda4af' }}>{j.error}</div>}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* ── STUDIO 3D (DETALHE DA PEÇA) ─────────────────────────────────── */}
        {page === 'detail' && (
          <div>
            <div className="page-header" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
                <button className="btn sm" onClick={() => setPage('home')}><IconArrowLeft /> Galeria</button>
                <h1 className="page-title" style={{ fontSize: 20 }}>{detail?.name || 'Carregando peça…'}</h1>
                {detail && <span className={`badge ${statusInfo.cls}`}>{statusInfo.label}</span>}
                {detail && <span className="badge neutral">v{detail.currentVersion || 0}</span>}
              </div>
              {detail && hasGlb && (
                <div style={{ display: 'flex', gap: 8 }}>
                  {has4k && <a className="btn sm" href={downloadUrl(detail.id, '4k')} download><IconDownload /> Baixar 4K</a>}
                  {has8k && <a className="btn sm primary" href={downloadUrl(detail.id, '8k')} download><IconDownload /> Baixar 8K</a>}
                </div>
              )}
            </div>

            {latestJob?.status === 'review' && (
              <div className="review-banner">
                <div>
                  <strong style={{ fontSize: 14, color: '#fbbf24' }}>Peça pronta para sua revisão visual</strong>
                  <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', marginTop: 2 }}>
                    Inspecione o modelo 3D em Pintado PBR e Clay antes de publicar na biblioteca.
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                  <button className="btn ok" onClick={() => onApproveJob(latestJob.id)}>Aprovar e Publicar</button>
                  <button className="btn danger" onClick={() => setShowRejectBox((v) => !v)}>Pedir Ajustes</button>
                </div>
                {showRejectBox && (
                  <div style={{ width: '100%', display: 'flex', gap: 8, marginTop: 8 }}>
                    <input
                      className="input"
                      value={rejectComment}
                      onChange={(e) => setRejectComment(e.target.value)}
                      placeholder="Descreva o que precisa ajustar…"
                    />
                    <button className="btn danger" onClick={() => onRejectJob(latestJob.id)}>Confirmar devolução</button>
                  </div>
                )}
              </div>
            )}

            <div className="studio-layout">
              <Viewer3D
                glbUrl={viewerUrl}
                has8k={has8k && has4k}
                variant={effectiveVar}
                onVariantChange={(v) => setViewerVariant(v)}
              />

              <aside className="inspector-panel">
                <div className="tab-bar">
                  <button className={`tab-btn ${inspectorTab === 'qa' ? 'active' : ''}`} onClick={() => setInspectorTab('qa')}>
                    Inspeção & QA
                  </button>
                  <button className={`tab-btn ${inspectorTab === 'chat' ? 'active' : ''}`} onClick={() => setInspectorTab('chat')}>
                    Chat IA ({detail?.chatMessages?.length || 0})
                  </button>
                  <button className={`tab-btn ${inspectorTab === 'files' ? 'active' : ''}`} onClick={() => setInspectorTab('files')}>
                    Arquivos
                  </button>
                </div>

                <div className="inspector-body scroller">
                  {inspectorTab === 'qa' && (
                    <>
                      {detail?.notes && (
                        <div style={{ fontSize: 12.5, color: 'var(--text-secondary)', lineHeight: 1.5, padding: 12, borderRadius: 8, background: 'var(--surface-elevated)', border: '1px solid var(--border)' }}>
                          {detail.notes}
                        </div>
                      )}
                      <div>
                        <div className="nav-label" style={{ padding: '0 0 8px' }}>Verificações de Qualidade</div>
                        {qaObj?.gates ? (
                          <div style={{ display: 'grid', gap: 8 }}>
                            {Object.entries(qaObj.gates).map(([k, v]: [string, any]) => (
                              <div key={k} className="qa-row">
                                <span>{GATE_PT[k] || k}</span>
                                <span className={`badge ${v.pass ? 'ok' : 'warn'}`}>{v.pass ? 'OK' : 'Atenção'}</span>
                              </div>
                            ))}
                          </div>
                        ) : (
                          <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>
                            Peça aprovada anteriormente ou sem relatório detalhado de gates.
                          </div>
                        )}
                      </div>
                    </>
                  )}

                  {inspectorTab === 'chat' && (
                    <>
                      <div className="chat-list scroller">
                        {(detail?.chatMessages || []).length === 0 && (
                          <div style={{ fontSize: 12.5, color: 'var(--text-muted)', lineHeight: 1.5 }}>
                            Peça ajustes em português natural (ex.: "limpar manchas na pintura", "aumentar brilho metálico"). Cada edição gera uma nova versão para sua revisão.
                          </div>
                        )}
                        {(detail?.chatMessages || []).map((m: any) => (
                          <div key={m.id} className={`chat-bubble ${m.role === 'user' ? 'user' : 'agent'}`}>
                            <div style={{ fontSize: 10.5, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 4 }}>
                              {m.role === 'user' ? 'Você' : 'Assistente de Edição IA'}
                            </div>
                            {m.content}
                          </div>
                        ))}
                      </div>
                      <form onSubmit={onSendChat} style={{ display: 'flex', gap: 8, marginTop: 'auto' }}>
                        <input
                          className="input"
                          value={chatText}
                          onChange={(e) => setChatText(e.target.value)}
                          placeholder="Pedir ajuste na peça…"
                        />
                        <button className="btn primary" type="submit" disabled={chatSending || !chatText.trim()}>
                          Enviar
                        </button>
                      </form>
                    </>
                  )}

                  {inspectorTab === 'files' && (
                    <div style={{ display: 'grid', gap: 10 }}>
                      <div className="nav-label" style={{ padding: 0 }}>Downloads da Versão Atual</div>
                      {has8k && (
                        <a className="qa-row" href={downloadUrl(detail.id, '8k')} download style={{ textDecoration: 'none', color: 'var(--text)' }}>
                          <span>GLB 8K (Alta Definição)</span>
                          <span className="badge info">Baixar</span>
                        </a>
                      )}
                      {has4k && (
                        <a className="qa-row" href={downloadUrl(detail.id, '4k')} download style={{ textDecoration: 'none', color: 'var(--text)' }}>
                          <span>GLB 4K (Web / Leve)</span>
                          <span className="badge ok">Baixar</span>
                        </a>
                      )}
                      {!hasGlb && (
                        <div style={{ fontSize: 12.5, color: 'var(--text-muted)' }}>Nenhum arquivo disponível ainda.</div>
                      )}
                      <div style={{ fontSize: 11.5, color: 'var(--text-muted)', marginTop: 8 }}>
                        Versões registradas: {detail?.versions?.length || 0} · Jobs: {detail?.jobs?.length || 0}
                      </div>
                    </div>
                  )}
                </div>
              </aside>
            </div>
          </div>
        )}
      </main>
    </div>
  );
};

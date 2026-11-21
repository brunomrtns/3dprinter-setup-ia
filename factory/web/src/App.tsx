import React, { useEffect, useState } from 'react';
import { apiFetch, downloadUrl, getToken, setToken } from './api';
import { Viewer3D } from './Viewer3D';

const STAGE_PT: Record<string, string> = {
  preprocess: 'Limpando fotos…',
  shape: 'Esculpindo malha…',
  paint: 'Pintando em 8K…',
  pbr: 'Aplicando brilho/PBR…',
  pack: 'Empacotando GLB 8K/4K…',
  qa: 'Conferindo qualidade…',
  edit: 'Aplicando ajustes solicitados…',
};

const GATE_PT: Record<string, string> = {
  lap_var: 'Nitidez da textura',
  bright_patches: 'Ausência de falhas brancas',
  saturation_band: 'Equilíbrio de cor',
  mr_pbr_present: 'Brilho/PBR real',
  glb_sizes_sane: 'Tamanho dos arquivos',
  photo_consistency: 'Fidelidade às fotos',
};

const STATUS_PT: Record<string, string> = {
  draft: 'Rascunho',
  queued: 'Na fila',
  claimed: 'Iniciando no PC…',
  running: 'Processando',
  review: 'Precisa de revisão',
  published: 'Publicada',
  rejected: 'Devolvida p/ edição',
  failed: 'Falhou',
};

type Page = 'home' | 'wizard' | 'queue' | 'detail';

export const App: React.FC = () => {
  const [user, setUser] = useState<any>(null);
  const [email, setEmail] = useState('bruno@brunointegrations.com');
  const [password, setPassword] = useState('');
  const [authErr, setAuthErr] = useState('');

  const [page, setPage] = useState<Page>('home');
  const [assets, setAssets] = useState<any[]>([]);
  const [jobs, setJobs] = useState<any[]>([]);
  const [worker, setWorker] = useState<any>(null);
  const [selectedAssetId, setSelectedAssetId] = useState<string | null>(null);
  const [detail, setDetail] = useState<any>(null);

  // Wizard T3.3 state (zero technical knobs!)
  const [wStep, setWStep] = useState(1);
  const [wMode, setWMode] = useState<'single' | 'multi' | 'mesh'>('multi');
  const [wName, setWName] = useState('');
  const [wNotes, setWNotes] = useState('');
  const [wFiles, setWFiles] = useState<File[]>([]);
  const [wPhotoWarning, setWPhotoWarning] = useState<string | null>(null);
  const [wSubmitting, setWSubmitting] = useState(false);

  // Chat T3.5 state
  const [chatText, setChatText] = useState('');
  const [rejectComment, setRejectComment] = useState('');

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
    if (!getToken()) return;
    apiFetch<{ user: any }>('/auth/me')
      .then((r) => {
        setUser(r.user);
        refreshAll();
      })
      .catch(() => setToken(null));
  }, []);

  useEffect(() => {
    if (!user) return;
    const t = setInterval(() => {
      refreshAll().catch(() => {});
      if (page === 'detail' && selectedAssetId) loadDetail(selectedAssetId).catch(() => {});
    }, 8000);
    return () => clearInterval(t);
  }, [user, page, selectedAssetId]);

  async function onLogin(e: React.FormEvent) {
    e.preventDefault();
    setAuthErr('');
    try {
      const r = await apiFetch<{ token: string; user: any }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      setToken(r.token);
      setUser(r.user);
      await refreshAll();
    } catch (err: any) {
      setAuthErr(err.message);
    }
  }

  function onSelectFiles(fileList: FileList | null) {
    if (!fileList) return;
    const arr = Array.from(fileList).slice(0, wMode === 'multi' ? 4 : 1);
    setWFiles(arr);
    setWPhotoWarning(null);
    // M5 client-side weak-input pre-check (resolution)
    if (wMode !== 'mesh' && arr[0]) {
      const img = new Image();
      img.onload = () => {
        if (img.width < 512 || img.height < 512) {
          setWPhotoWarning(
            `Foto com resolução baixa (${img.width}×${img.height}). O fundo será removido automaticamente; re-render por IA externa está disponível quando ativado no worker (M5).`
          );
        }
      };
      img.src = URL.createObjectURL(arr[0]);
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
      wFiles.forEach((f, i) => fd.append(`file_${i}`, f));
      await apiFetch(`/assets/${asset.id}/inputs`, { method: 'POST', body: fd });
      await apiFetch('/jobs', { method: 'POST', body: JSON.stringify({ asset_id: asset.id }) });
      setWStep(1);
      setWName('');
      setWNotes('');
      setWFiles([]);
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
    if (!detail || !chatText.trim()) return;
    await apiFetch(`/assets/${detail.id}/chat`, {
      method: 'POST',
      body: JSON.stringify({ content: chatText.trim() }),
    });
    setChatText('');
    await loadDetail(detail.id);
    await refreshAll();
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
    if (selectedAssetId) await loadDetail(selectedAssetId);
    await refreshAll();
  }

  if (!user) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', padding: 20 }}>
        <form onSubmit={onLogin} className="card" style={{ width: '100%', maxWidth: 380, display: 'grid', gap: 12 }}>
          <h2 style={{ margin: 0 }}>Fábrica 3D</h2>
          <p style={{ margin: 0, color: '#93a1b5', fontSize: 13 }}>Bruno Integrations · Acesso privado</p>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="E-mail" required />
          <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Senha" required />
          {authErr && <div style={{ color: '#ef4444', fontSize: 13 }}>{authErr}</div>}
          <button className="btn primary" type="submit">Entrar</button>
          <div style={{ fontSize: 11, color: '#93a1b5' }}>Uso estritamente privado e pessoal. Proibido uso comercial.</div>
        </form>
      </div>
    );
  }

  const latestJob = detail?.jobs?.[0];
  const hasGlb = Boolean(detail?.versions?.[0]?.filesJson?.glb_4k || detail?.versions?.[0]?.filesJson?.glb_8k || latestJob?.resultsJson?.files?.glb_4k || latestJob?.resultsJson?.files?.glb_8k);
  const viewerUrl = detail && hasGlb ? downloadUrl(detail.id, '4k') : null;
  const qaObj = detail?.versions?.[0]?.qaJson || latestJob?.resultsJson?.qa || null;

  return (
    <div>
      <header className="topbar">
        <div className="brand">
          <span>Fábrica 3D</span>
          <span className={`badge ${worker?.online ? 'ok' : 'warn'}`}>
            {worker?.online ? `PC Online · ${worker.vramFreeMib} MiB VRAM livres` : 'PC offline — aguardando worker'}
          </span>
        </div>
        <nav className="nav">
          <button className={`btn ${page === 'home' ? 'primary' : ''}`} onClick={() => setPage('home')}>Minhas Peças</button>
          <button className={`btn ${page === 'wizard' ? 'primary' : ''}`} onClick={() => { setWStep(1); setPage('wizard'); }}>+ Nova Peça</button>
          <button className={`btn ${page === 'queue' ? 'primary' : ''}`} onClick={() => setPage('queue')}>Fila ({jobs.filter((j) => ['queued', 'claimed', 'running'].includes(j.status)).length})</button>
          <button className="btn" onClick={() => { setToken(null); setUser(null); }}>Sair</button>
        </nav>
      </header>

      <main className="container">
        {page === 'home' && (
          <div>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
              <h2 style={{ margin: 0 }}>Minhas Peças</h2>
              <button className="btn primary" onClick={() => { setWStep(1); setPage('wizard'); }}>+ Nova Peça</button>
            </div>
            {assets.length === 0 ? (
              <div className="card" style={{ textAlign: 'center', padding: 40, color: '#93a1b5' }}>
                Nenhuma peça ainda. Clique em <b>+ Nova Peça</b> para enviar suas fotos.
              </div>
            ) : (
              <div className="grid">
                {assets.map((a) => (
                  <div key={a.id} className="card" style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <strong>{a.name}</strong>
                      <span className={`badge ${a.status === 'published' ? 'ok' : a.status === 'failed' ? 'err' : 'warn'}`}>
                        {STATUS_PT[a.status] || a.status}
                      </span>
                    </div>
                    <div style={{ fontSize: 12, color: '#93a1b5' }}>
                      Modo: {a.mode === 'multi' ? 'Vários ângulos' : a.mode === 'single' ? '1 foto' : 'Peça existente'} · v{a.currentVersion || 0}
                    </div>
                    <div style={{ display: 'flex', gap: 8, marginTop: 'auto', flexWrap: 'wrap' }}>
                      <button className="btn primary" onClick={async () => { setSelectedAssetId(a.id); await loadDetail(a.id); setPage('detail'); }}>Ver</button>
                      {a.currentVersion > 0 && (
                        <a className="btn" href={downloadUrl(a.id, '8k')}>Baixar 8K</a>
                      )}
                      <button className="btn" onClick={async () => { if (confirm(`Remover ${a.name}?`)) { await apiFetch(`/assets/${a.id}`, { method: 'DELETE' }); await refreshAll(); } }}>Excluir</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {page === 'wizard' && (
          <div className="card" style={{ maxWidth: 820, margin: '0 auto', display: 'grid', gap: 16 }}>
            <h2 style={{ margin: 0 }}>Nova Peça — Passo {wStep} de 3</h2>
            {wStep === 1 && (
              <>
                <p style={{ margin: 0, color: '#93a1b5' }}>Como você quer criar? (Qualidade 8K + PBR sempre ativada automaticamente.)</p>
                <div className="wizard-grid">
                  <button className={`mode-card ${wMode === 'multi' ? 'active' : ''}`} onClick={() => setWMode('multi')}>
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}><strong>Consigo fotografar de vários ângulos</strong><span className="badge ok">Recomendado</span></div>
                    <p style={{ fontSize: 13, color: '#93a1b5' }}>Envie 3 a 4 fotos (frente, lado, costas, outro lado). Qualidade máxima.</p>
                  </button>
                  <button className={`mode-card ${wMode === 'single' ? 'active' : ''}`} onClick={() => setWMode('single')}>
                    <strong>Tenho uma foto</strong>
                    <p style={{ fontSize: 13, color: '#93a1b5' }}>Envie 1 foto limpa. Fidelidade alta na frente; costas estimadas pela IA.</p>
                  </button>
                  <button className={`mode-card ${wMode === 'mesh' ? 'active' : ''}`} onClick={() => setWMode('mesh')}>
                    <strong>Quero melhorar uma peça que já existe</strong>
                    <p style={{ fontSize: 13, color: '#93a1b5' }}>Suba um arquivo GLB, OBJ ou STL para pintura/PBR automático.</p>
                  </button>
                </div>
                <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
                  <button className="btn primary" onClick={() => setWStep(2)}>Continuar →</button>
                </div>
              </>
            )}

            {wStep === 2 && (
              <>
                <div className="badge ok" style={{ width: 'fit-content' }}>Fundo será removido automaticamente</div>
                {wMode === 'multi' && (
                  <p style={{ margin: 0, fontSize: 13, color: '#93a1b5' }}>
                    Dica de ângulos: 1) Frente · 2) Lateral esquerda · 3) Traseira · 4) Lateral direita (luz uniforme, objeto ocupando ~70% do quadro).
                  </p>
                )}
                <input
                  type="file"
                  multiple={wMode === 'multi'}
                  accept={wMode === 'mesh' ? '.glb,.gltf,.obj,.stl' : 'image/png,image/jpeg,image/webp'}
                  onChange={(e) => onSelectFiles(e.target.files)}
                />
                {wFiles.length > 0 && (
                  <div style={{ fontSize: 13, color: '#93a1b5' }}>
                    {wFiles.length} arquivo(s) selecionado(s): {wFiles.map((f) => f.name).join(', ')}
                  </div>
                )}
                {wPhotoWarning && <div className="msg system">{wPhotoWarning}</div>}
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <button className="btn" onClick={() => setWStep(1)}>← Voltar</button>
                  <button className="btn primary" disabled={wFiles.length === 0} onClick={() => setWStep(3)}>Continuar →</button>
                </div>
              </>
            )}

            {wStep === 3 && (
              <>
                <input className="input" value={wName} onChange={(e) => setWName(e.target.value)} placeholder="Nome da peça (ex.: Fox Branco, Dragão)" />
                <textarea className="input" rows={3} value={wNotes} onChange={(e) => setWNotes(e.target.value)} placeholder="Observações livres (opcional)" />
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <button className="btn" onClick={() => setWStep(2)}>← Voltar</button>
                  <button className="btn primary" disabled={!wName.trim() || wSubmitting} onClick={onSubmitWizard}>
                    {wSubmitting ? 'Enviando…' : 'Enviar para fila'}
                  </button>
                </div>
              </>
            )}
          </div>
        )}

        {page === 'queue' && (
          <div className="card">
            <h2 style={{ marginTop: 0 }}>Fila & Status</h2>
            {!worker?.online && (
              <div className="msg system" style={{ marginBottom: 14 }}>
                PC local offline — os jobs ficam salvos na fila e começam automaticamente quando o worker ligar.
              </div>
            )}
            <div style={{ display: 'grid', gap: 10 }}>
              {jobs.map((j) => (
                <div key={j.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: 12, background: '#181e28', borderRadius: 8, flexWrap: 'wrap', gap: 8 }}>
                  <div>
                    <strong>{j.asset?.name || j.assetId}</strong> <span className="badge">{j.type === 'edit' ? 'Edição' : 'Nova'}</span>
                    <div style={{ fontSize: 12, color: '#93a1b5' }}>
                      {STAGE_PT[j.stage] || j.stage} · {j.progress}% {j.error ? `· Erro: ${j.error}` : ''}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                    <span className={`badge ${j.status === 'published' ? 'ok' : j.status === 'failed' ? 'err' : 'warn'}`}>
                      {STATUS_PT[j.status] || j.status}
                    </span>
                    <button className="btn" onClick={async () => { setSelectedAssetId(j.assetId); await loadDetail(j.assetId); setPage('detail'); }}>Abrir</button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {page === 'detail' && detail && (
          <div style={{ display: 'grid', gap: 18 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 10 }}>
              <div>
                <button className="btn" onClick={() => setPage('home')}>← Voltar</button>
                <h2 style={{ display: 'inline', marginLeft: 12 }}>{detail.name}</h2>
                <span className="badge" style={{ marginLeft: 10 }}>{STATUS_PT[detail.status] || detail.status}</span>
              </div>
              {hasGlb && (
                <div style={{ display: 'flex', gap: 8 }}>
                  <a className="btn primary" href={downloadUrl(detail.id, '8k')}>Download GLB 8K</a>
                  <a className="btn" href={downloadUrl(detail.id, '4k')}>Download GLB 4K</a>
                </div>
              )}
            </div>

            <div className="detail-layout">
              <Viewer3D glbUrl={viewerUrl} />
              <div style={{ display: 'grid', gap: 14, alignContent: 'start' }}>
                {latestJob?.status === 'review' && (
                  <div className="card" style={{ borderColor: '#f59e0b' }}>
                    <h3 style={{ marginTop: 0 }}>Revisão Humana (Gate de Publicação)</h3>
                    <input className="input" value={rejectComment} onChange={(e) => setRejectComment(e.target.value)} placeholder="Comentário caso reprove (opcional)" style={{ marginBottom: 10 }} />
                    <div style={{ display: 'flex', gap: 8 }}>
                      <button className="btn ok" onClick={() => onApproveJob(latestJob.id)}>Aprovar e Publicar</button>
                      <button className="btn err" onClick={() => onRejectJob(latestJob.id)}>Reprovar</button>
                    </div>
                  </div>
                )}

                {qaObj?.gates && (
                  <div className="card">
                    <h3 style={{ marginTop: 0 }}>Qualidade Automática (QA)</h3>
                    <div style={{ display: 'grid', gap: 6, fontSize: 13 }}>
                      {Object.entries(qaObj.gates).map(([k, g]: any) => (
                        <div key={k} style={{ display: 'flex', justifyContent: 'space-between' }}>
                          <span>{GATE_PT[k] || k}</span>
                          <span className={`badge ${g.pass ? 'ok' : 'err'}`}>{g.pass ? 'PASS' : 'FAIL'}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="card">
                  <h3 style={{ marginTop: 0 }}>Chat de Edição (Agente IA)</h3>
                  <div className="chat-box">
                    {(detail.chatMessages || []).length === 0 && (
                      <div style={{ color: '#93a1b5', fontSize: 12 }}>Peça melhorias em linguagem natural (ex.: "limpar manchas da traseira").</div>
                    )}
                    {(detail.chatMessages || []).map((m: any) => (
                      <div key={m.id} className={`msg ${m.role}`}>
                        <div>{m.content}</div>
                        {m.planJson && (
                          <pre style={{ fontSize: 11, margin: '6px 0 0', opacity: 0.8, whiteSpace: 'pre-wrap' }}>
                            Plano: {JSON.stringify(m.planJson)}
                          </pre>
                        )}
                      </div>
                    ))}
                  </div>
                  <form onSubmit={onSendChat} style={{ display: 'flex', gap: 8, marginTop: 10 }}>
                    <input className="input" value={chatText} onChange={(e) => setChatText(e.target.value)} placeholder="Descreva o ajuste desejado…" />
                    <button className="btn primary" type="submit">Enviar</button>
                  </form>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="footer-note">
        Fábrica 3D · Bruno Integrations · Uso estritamente privado e pessoal (proibido uso comercial).
      </footer>
    </div>
  );
};

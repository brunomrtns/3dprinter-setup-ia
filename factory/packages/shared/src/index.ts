export const STAGE_LABELS_PT: Record<string, string> = {
  preprocess: 'Limpando fotos…',
  shape: 'Esculpindo malha…',
  paint: 'Pintando em 8K…',
  pbr: 'Aplicando brilho/PBR…',
  pack: 'Empacotando GLB 8K/4K…',
  qa: 'Conferindo qualidade…',
  edit: 'Aplicando ajustes solicitados…',
};

export const GATE_LABELS_PT: Record<string, string> = {
  lap_var: 'Nitidez da textura',
  bright_patches: 'Ausência de falhas brancas',
  saturation_band: 'Equilíbrio de cor',
  mr_pbr_present: 'Brilho/PBR real',
  glb_sizes_sane: 'Tamanho dos arquivos',
  photo_consistency: 'Fidelidade às fotos',
};

export const STATUS_LABELS_PT: Record<string, string> = {
  draft: 'Rascunho',
  queued: 'Na fila',
  claimed: 'Iniciando no PC…',
  running: 'Processando',
  review: 'Aguardando revisão',
  published: 'Publicada',
  rejected: 'Devolvida p/ edição',
  failed: 'Falhou',
};

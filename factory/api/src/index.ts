import Fastify, { FastifyReply, FastifyRequest } from 'fastify';
import cors from '@fastify/cors';
import jwt from '@fastify/jwt';
import multipart from '@fastify/multipart';
import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';
import { ensureBucket, getObjectStream, uploadBuffer } from './storage';
import { fab3dQueue, getWorkerHeartbeat, setWorkerHeartbeat } from './queue';

const prisma = new PrismaClient();
const app = Fastify({ logger: true, bodyLimit: 100 * 1024 * 1024 });

const JWT_SECRET = process.env.JWT_SECRET || 'dev-only-secret-change-in-env';
const WORKER_TOKEN = process.env.WORKER_TOKEN || '';
const LEASE_MIN = Number(process.env.JOB_LEASE_MINUTES || 30);
const BI_IDENTITY_URL = (process.env.BI_IDENTITY_URL || 'http://bi-api:3300').replace(/\/$/, '');
const ADMIN_EMAILS = new Set(
  (process.env.ADMIN_EMAILS || process.env.ADMIN_EMAIL || 'bruno@brunointegrations.com')
    .split(',')
    .map((s) => s.trim().toLowerCase())
    .filter(Boolean)
);

const ALLOWED_IMAGE_MIMES = new Set(['image/png', 'image/jpeg', 'image/webp']);
const ALLOWED_MESH_EXT = new Set(['.glb', '.gltf', '.obj', '.stl']);

declare module '@fastify/jwt' {
  interface FastifyJWT {
    payload: { sub: string; email: string; name: string; role: string };
    user: { sub: string; email: string; name: string; role: string };
  }
}

async function resolveBiIdentityUser(req: FastifyRequest, reply: FastifyReply) {
  const cookieHeader = req.headers.cookie || '';
  if (!cookieHeader.includes('bi_auth=') && !cookieHeader.includes('bi_refresh=')) {
    return null;
  }
  try {
    const resp = await fetch(`${BI_IDENTITY_URL}/api/auth/check`, {
      method: 'GET',
      headers: { cookie: cookieHeader },
    });
    if (!resp.ok) return null;

    // Forward rotated bi_auth Set-Cookie headers to browser transparently
    const setCookies = typeof (resp.headers as any).getSetCookie === 'function'
      ? ((resp.headers as any).getSetCookie() as string[])
      : [];
    if (setCookies.length > 0) {
      reply.header('set-cookie', setCookies);
    }

    const biUser = (await resp.json()) as {
      id: string;
      email: string;
      name: string;
      status?: string;
      isSuperAdmin?: boolean;
    };
    if (!biUser?.email || (biUser.status && biUser.status !== 'ACTIVE')) {
      return null;
    }

    const email = biUser.email.toLowerCase();
    const existing = await prisma.user.findUnique({ where: { email } });
    const role =
      existing?.role === 'admin' || biUser.isSuperAdmin || ADMIN_EMAILS.has(email)
        ? 'admin'
        : 'user';
    const localUser = await prisma.user.upsert({
      where: { email },
      update: { name: biUser.name || email, role },
      create: {
        email,
        name: biUser.name || email,
        passwordHash: 'sso-bi-identity',
        role,
      },
    });
    return {
      sub: localUser.id,
      email: localUser.email,
      name: localUser.name,
      role: localUser.role,
    };
  } catch (err) {
    req.log.warn({ err }, 'BI Identity SSO check failed');
    return null;
  }
}

async function requireUser(req: FastifyRequest, reply: FastifyReply) {
  // 1. Standard Bruno Integrations SSO (BI Identity cookies bi_auth / bi_refresh)
  const ssoUser = await resolveBiIdentityUser(req, reply);
  if (ssoUser) {
    req.user = ssoUser;
    return;
  }
  // 2. Fallback: Bearer JWT (for CLI/automated scripts)
  try {
    await req.jwtVerify();
  } catch {
    return reply.code(401).send({ error: 'Não autenticado' });
  }
}

async function requireAdmin(req: FastifyRequest, reply: FastifyReply) {
  await requireUser(req, reply);
  if (reply.sent) return;
  if (req.user.role !== 'admin') {
    return reply.code(403).send({ error: 'Apenas administrador pode publicar/aprovar' });
  }
}

async function requireWorker(req: FastifyRequest, reply: FastifyReply) {
  const tok = req.headers['x-worker-token'];
  if (!WORKER_TOKEN || tok !== WORKER_TOKEN) {
    return reply.code(401).send({ error: 'Worker token inválido' });
  }
}

async function releaseExpiredLeases() {
  const now = new Date();
  await prisma.job.updateMany({
    where: {
      status: { in: ['claimed', 'running'] },
      leaseUntil: { lt: now },
    },
    data: {
      status: 'queued',
      workerId: null,
      leaseUntil: null,
    },
  });
}

async function start() {
  await ensureBucket();

  await app.register(cors, { origin: true, credentials: true });
  await app.register(jwt, { secret: JWT_SECRET });
  await app.register(multipart, { limits: { fileSize: 80 * 1024 * 1024, files: 10 } });

  // ── Health ────────────────────────────────────────────────────────────────
  app.get('/api/fab3d/health', async () => {
    const hb = await getWorkerHeartbeat();
    return { ok: true, service: 'fab3d-api', workerOnline: Boolean(hb?.online) };
  });

  // ── Auth ──────────────────────────────────────────────────────────────────
  app.post('/api/fab3d/auth/login', async (req, reply) => {
    const body = (req.body || {}) as { email?: string; password?: string };
    if (!body.email || !body.password) {
      return reply.code(400).send({ error: 'Informe e-mail e senha' });
    }
    const user = await prisma.user.findUnique({ where: { email: body.email.trim().toLowerCase() } });
    if (!user) return reply.code(401).send({ error: 'Credenciais inválidas' });
    const ok = await bcrypt.compare(body.password, user.passwordHash);
    if (!ok) return reply.code(401).send({ error: 'Credenciais inválidas' });

    const token = app.jwt.sign(
      { sub: user.id, email: user.email, name: user.name, role: user.role },
      { expiresIn: '7d' }
    );
    return { token, user: { id: user.id, email: user.email, name: user.name, role: user.role } };
  });

  app.get('/api/fab3d/auth/me', { preHandler: [requireUser] }, async (req) => {
    return { user: req.user };
  });

  // ── Worker status (for UI) ────────────────────────────────────────────────
  app.get('/api/fab3d/worker/status', { preHandler: [requireUser] }, async () => {
    const hb = await getWorkerHeartbeat();
    return hb || { online: false, workerId: null, currentJobId: null, vramFreeMib: 0, vramUsedMib: 0, ts: null };
  });

  // ── Assets ────────────────────────────────────────────────────────────────
  app.get('/api/fab3d/assets', { preHandler: [requireUser] }, async (req) => {
    const assets = await prisma.asset.findMany({
      where: req.user.role === 'admin' ? {} : { userId: req.user.sub },
      orderBy: { createdAt: 'desc' },
      include: {
        versions: { orderBy: { versionNum: 'desc' }, take: 1 },
        jobs: { orderBy: { createdAt: 'desc' }, take: 1 },
      },
    });
    return { assets };
  });

  app.post('/api/fab3d/assets', { preHandler: [requireUser] }, async (req, reply) => {
    const body = (req.body || {}) as { name?: string; mode?: string; notes?: string };
    const name = (body.name || '').trim();
    const mode = body.mode || 'multi';
    if (!name) return reply.code(400).send({ error: 'Nome da peça é obrigatório' });
    if (!['single', 'multi', 'mesh'].includes(mode)) {
      return reply.code(400).send({ error: 'Modo inválido (single|multi|mesh)' });
    }
    const asset = await prisma.asset.create({
      data: {
        userId: req.user.sub,
        name,
        mode,
        notes: (body.notes || '').trim(),
        status: 'draft',
      },
    });
    return reply.code(201).send({ asset });
  });

  app.get('/api/fab3d/assets/:id', { preHandler: [requireUser] }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const asset = await prisma.asset.findUnique({
      where: { id },
      include: {
        versions: { orderBy: { versionNum: 'desc' } },
        jobs: { orderBy: { createdAt: 'desc' }, include: { inputs: true } },
        chatMessages: { orderBy: { createdAt: 'asc' } },
      },
    });
    if (!asset) return reply.code(404).send({ error: 'Peça não encontrada' });
    if (req.user.role !== 'admin' && asset.userId !== req.user.sub) {
      return reply.code(403).send({ error: 'Acesso negado' });
    }
    return { asset };
  });

  app.delete('/api/fab3d/assets/:id', { preHandler: [requireUser] }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const asset = await prisma.asset.findUnique({ where: { id } });
    if (!asset) return reply.code(404).send({ error: 'Peça não encontrada' });
    if (req.user.role !== 'admin' && asset.userId !== req.user.sub) {
      return reply.code(403).send({ error: 'Acesso negado' });
    }
    await prisma.asset.delete({ where: { id } });
    return { deleted: true };
  });

  // Upload inputs (photos or mesh) -> MinIO
  app.post('/api/fab3d/assets/:id/inputs', { preHandler: [requireUser] }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const asset = await prisma.asset.findUnique({ where: { id } });
    if (!asset) return reply.code(404).send({ error: 'Peça não encontrada' });
    if (req.user.role !== 'admin' && asset.userId !== req.user.sub) {
      return reply.code(403).send({ error: 'Acesso negado' });
    }

    // Ensure there is a draft job to attach inputs to
    let job = await prisma.job.findFirst({
      where: { assetId: id, status: 'draft' },
      orderBy: { createdAt: 'desc' },
    });
    if (!job) {
      job = await prisma.job.create({
        data: { assetId: id, type: 'new', mode: asset.mode, status: 'draft', stage: 'preprocess' },
      });
    }

    const parts = req.parts();
    const saved = [];
    let idx = 0;
    for await (const part of parts) {
      if (part.type !== 'file') continue;
      const buf = await part.toBuffer();
      const fname = (part.filename || `input_${idx}`).replace(/[^a-zA-Z0-9._-]/g, '_');
      const ext = fname.includes('.') ? fname.slice(fname.lastIndexOf('.')).toLowerCase() : '';
      const isImg = ALLOWED_IMAGE_MIMES.has(part.mimetype);
      const isMesh = ALLOWED_MESH_EXT.has(ext);
      if (!isImg && !isMesh) {
        return reply.code(400).send({ error: `Arquivo não suportado: ${fname} (${part.mimetype})` });
      }
      const kind = isMesh ? 'mesh' : 'photo';
      const key = `${asset.userId}/${asset.id}/${job.id}/inputs/${idx}_${fname}`;
      await uploadBuffer(key, buf, part.mimetype || 'application/octet-stream');
      const inp = await prisma.jobInput.create({
        data: {
          jobId: job.id,
          kind,
          minioKey: key,
          filename: fname,
          mimeType: part.mimetype || 'application/octet-stream',
          sizeBytes: buf.length,
          metaJson: { index: idx, fieldname: part.fieldname },
        },
      });
      saved.push(inp);
      idx++;
    }

    if (saved.length === 0) {
      return reply.code(400).send({ error: 'Nenhum arquivo recebido' });
    }
    return reply.code(201).send({ jobId: job.id, inputs: saved });
  });

  // Stream file from MinIO (GLB 8k/4k or render) with auth (also accepts ?token= for <img>/<three.js>)
  app.get('/api/fab3d/assets/:id/download', async (req, reply) => {
    const q = req.query as { variant?: string; key?: string; token?: string };
    if (q.token && !req.headers.authorization) {
      req.headers.authorization = `Bearer ${q.token}`;
    }
    await requireUser(req, reply);
    if (reply.sent) return;

    const { id } = req.params as { id: string };
    const asset = await prisma.asset.findUnique({
      where: { id },
      include: {
        versions: { orderBy: { versionNum: 'desc' }, take: 5 },
        jobs: { orderBy: { createdAt: 'desc' }, take: 15 },
      },
    });
    if (!asset) return reply.code(404).send({ error: 'Peça não encontrada' });
    if (req.user.role !== 'admin' && asset.userId !== req.user.sub) {
      return reply.code(403).send({ error: 'Acesso negado' });
    }

    let targetKey = q.key || '';
    if (!targetKey) {
      const variant = q.variant === '4k' ? 'glb_4k' : 'glb_8k';
      const fallbackVariant = variant === 'glb_4k' ? 'glb_8k' : 'glb_4k';
      const fileMaps: Array<Record<string, string>> = [
        ...asset.versions.map((v) => (v.filesJson || {}) as Record<string, string>),
        ...asset.jobs.map((j) => ((j.resultsJson as Record<string, unknown>)?.files || {}) as Record<string, string>),
      ];
      for (const fm of fileMaps) {
        if (fm[variant]) { targetKey = fm[variant]; break; }
      }
      if (!targetKey) {
        for (const fm of fileMaps) {
          if (fm[fallbackVariant]) { targetKey = fm[fallbackVariant]; break; }
        }
      }
    }
    if (!targetKey || !targetKey.includes(`/${asset.id}/`)) {
      return reply.code(404).send({ error: 'Arquivo não disponível para esta peça' });
    }

    const stream = await getObjectStream(targetKey);
    const fname = targetKey.split('/').pop() || 'asset.glb';
    const isPng = fname.endsWith('.png');
    reply.header('Content-Type', isPng ? 'image/png' : 'model/gltf-binary');
    if (!isPng) {
      reply.header('Content-Disposition', `inline; filename="${fname}"`);
    }
    return reply.send(stream);
  });

  // Admin migration helper: import already-built GLBs into an Asset + AssetVersion
  app.post('/api/fab3d/admin/migrate-asset', { preHandler: [requireAdmin] }, async (req, reply) => {
    const parts = req.parts();
    let name = '';
    let mode = 'multi';
    let notes = '';
    let qaJson: Record<string, unknown> = {};
    const uploaded: Record<string, Buffer> = {};

    for await (const part of parts) {
      if (part.type === 'field') {
        const val = String(part.value || '');
        if (part.fieldname === 'name') name = val;
        else if (part.fieldname === 'mode') mode = val;
        else if (part.fieldname === 'notes') notes = val;
        else if (part.fieldname === 'qa_json') {
          try { qaJson = JSON.parse(val); } catch { qaJson = {}; }
        }
      } else {
        uploaded[part.fieldname] = await part.toBuffer();
      }
    }

    if (!name) return reply.code(400).send({ error: 'name obrigatório' });

    const asset = await prisma.asset.create({
      data: { userId: req.user.sub, name, mode, notes, status: 'published', currentVersion: 1 },
    });

    const filesMap: Record<string, string> = {};
    for (const [field, buf] of Object.entries(uploaded)) {
      const ext = field.includes('thumb') || field.includes('render') ? 'png' : 'glb';
      const key = `${req.user.sub}/${asset.id}/migrated/${field}.${ext}`;
      await uploadBuffer(key, buf, ext === 'png' ? 'image/png' : 'model/gltf-binary');
      filesMap[field] = key;
    }

    const ver = await prisma.assetVersion.create({
      data: {
        assetId: asset.id,
        versionNum: 1,
        filesJson: filesMap,
        qaJson: qaJson as object,
        publishedAt: new Date(),
      },
    });

    return reply.code(201).send({ asset, version: ver });
  });

  // ── Jobs (User) ───────────────────────────────────────────────────────────
  app.post('/api/fab3d/jobs', { preHandler: [requireUser] }, async (req, reply) => {
    const body = (req.body || {}) as { asset_id?: string; assetId?: string };
    const assetId = body.asset_id || body.assetId;
    if (!assetId) return reply.code(400).send({ error: 'asset_id obrigatório' });

    const asset = await prisma.asset.findUnique({ where: { id: assetId } });
    if (!asset) return reply.code(404).send({ error: 'Peça não encontrada' });
    if (req.user.role !== 'admin' && asset.userId !== req.user.sub) {
      return reply.code(403).send({ error: 'Acesso negado' });
    }

    let job = await prisma.job.findFirst({
      where: { assetId, status: 'draft' },
      orderBy: { createdAt: 'desc' },
    });
    if (job) {
      job = await prisma.job.update({
        where: { id: job.id },
        data: { status: 'queued', stage: 'preprocess', progress: 0 },
      });
    } else {
      job = await prisma.job.create({
        data: { assetId, type: 'new', mode: asset.mode, status: 'queued', stage: 'preprocess' },
      });
    }

    await prisma.asset.update({ where: { id: assetId }, data: { status: 'queued' } });
    await fab3dQueue.add('run-job', { jobId: job.id, assetId });

    const position = await prisma.job.count({
      where: { status: { in: ['queued', 'claimed', 'running'] }, createdAt: { lte: job.createdAt } },
    });

    return reply.code(202).send({ job_id: job.id, jobId: job.id, status: job.status, position });
  });

  app.get('/api/fab3d/jobs', { preHandler: [requireUser] }, async (req) => {
    await releaseExpiredLeases();
    const jobs = await prisma.job.findMany({
      where: req.user.role === 'admin' ? {} : { asset: { userId: req.user.sub } },
      orderBy: { createdAt: 'desc' },
      take: 50,
      include: { asset: { select: { id: true, name: true, mode: true } } },
    });
    return { jobs };
  });

  app.get('/api/fab3d/jobs/:id', { preHandler: [requireUser] }, async (req, reply) => {
    await releaseExpiredLeases();
    const { id } = req.params as { id: string };
    const job = await prisma.job.findUnique({
      where: { id },
      include: { asset: true, inputs: true },
    });
    if (!job) return reply.code(404).send({ error: 'Job não encontrado' });
    if (req.user.role !== 'admin' && job.asset.userId !== req.user.sub) {
      return reply.code(403).send({ error: 'Acesso negado' });
    }
    const position =
      job.status === 'queued'
        ? await prisma.job.count({ where: { status: 'queued', createdAt: { lte: job.createdAt } } })
        : 0;
    return { job, position };
  });

  app.post('/api/fab3d/jobs/:id/approve', { preHandler: [requireAdmin] }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const job = await prisma.job.findUnique({ where: { id }, include: { asset: true } });
    if (!job) return reply.code(404).send({ error: 'Job não encontrado' });

    const res = (job.resultsJson || {}) as { files?: Record<string, string>; qa?: Record<string, unknown> };
    let filesToSave = res.files || {};
    if (!filesToSave.glb_8k && !filesToSave.glb_4k) {
      const prevVer = await prisma.assetVersion.findFirst({
        where: { assetId: job.assetId },
        orderBy: { versionNum: 'desc' },
      });
      const prevJobs = await prisma.job.findMany({
        where: { assetId: job.assetId, resultsJson: { not: null as any } },
        orderBy: { createdAt: 'desc' },
        take: 10,
      });
      const prevVerFiles = (prevVer?.filesJson || {}) as Record<string, string>;
      if (prevVerFiles.glb_8k || prevVerFiles.glb_4k) {
        filesToSave = prevVerFiles;
      } else {
        for (const pj of prevJobs) {
          const pf = ((pj.resultsJson as Record<string, unknown>)?.files || {}) as Record<string, string>;
          if (pf.glb_8k || pf.glb_4k) {
            filesToSave = pf;
            break;
          }
        }
      }
    }
    const nextVer = (job.asset.currentVersion || 0) + 1;

    const version = await prisma.assetVersion.create({
      data: {
        assetId: job.assetId,
        jobId: job.id,
        versionNum: nextVer,
        filesJson: filesToSave as object,
        qaJson: (res.qa || {}) as object,
        publishedAt: new Date(),
      },
    });
    await prisma.job.update({ where: { id }, data: { status: 'published', progress: 100 } });
    await prisma.asset.update({
      where: { id: job.assetId },
      data: { status: 'published', currentVersion: nextVer },
    });
    return { approved: true, version };
  });

  app.post('/api/fab3d/jobs/:id/reject', { preHandler: [requireAdmin] }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const body = (req.body || {}) as { comment?: string };
    const job = await prisma.job.findUnique({ where: { id } });
    if (!job) return reply.code(404).send({ error: 'Job não encontrado' });

    await prisma.job.update({ where: { id }, data: { status: 'rejected' } });
    await prisma.asset.update({ where: { id: job.assetId }, data: { status: 'rejected' } });
    if (body.comment) {
      await prisma.chatMessage.create({
        data: {
          assetId: job.assetId,
          jobId: job.id,
          role: 'system',
          content: `Revisão reprovada: ${body.comment}`,
        },
      });
    }
    return { rejected: true };
  });

  // ── Chat (Modo Edição Agêntico M6) ────────────────────────────────────────
  app.get('/api/fab3d/assets/:id/chat', { preHandler: [requireUser] }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const asset = await prisma.asset.findUnique({ where: { id } });
    if (!asset) return reply.code(404).send({ error: 'Peça não encontrada' });
    if (req.user.role !== 'admin' && asset.userId !== req.user.sub) {
      return reply.code(403).send({ error: 'Acesso negado' });
    }
    const messages = await prisma.chatMessage.findMany({
      where: { assetId: id },
      orderBy: { createdAt: 'asc' },
    });
    return { messages };
  });

  const chatRateMap = new Map<string, number[]>();
  const CHAT_MAX_PER_HOUR = Number(process.env.CHAT_MAX_PER_HOUR || 10);
  const CHAT_MAX_PROMPT_LEN = 400;

  app.post('/api/fab3d/assets/:id/chat', { preHandler: [requireAdmin] }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const body = (req.body || {}) as { content?: string };
    const content = (body.content || '').replace(/[\x00-\x1f\x7f]/g, ' ').trim();
    if (!content) return reply.code(400).send({ error: 'Mensagem vazia' });
    if (content.length > CHAT_MAX_PROMPT_LEN) {
      return reply.code(400).send({ error: `Pedido muito longo (máx. ${CHAT_MAX_PROMPT_LEN} caracteres)` });
    }

    const now = Date.now();
    const prev = (chatRateMap.get(req.user.sub) || []).filter((t) => now - t < 3600_000);
    if (prev.length >= CHAT_MAX_PER_HOUR) {
      return reply.code(429).send({ error: `Limite de ${CHAT_MAX_PER_HOUR} pedidos de IA por hora atingido` });
    }
    prev.push(now);
    chatRateMap.set(req.user.sub, prev);

    const asset = await prisma.asset.findUnique({ where: { id } });
    if (!asset) return reply.code(404).send({ error: 'Peça não encontrada' });
    if (req.user.role !== 'admin' && asset.userId !== req.user.sub) {
      return reply.code(403).send({ error: 'Acesso negado' });
    }

    const editJob = await prisma.job.create({
      data: {
        assetId: id,
        type: 'edit',
        mode: asset.mode,
        status: 'queued',
        stage: 'edit',
        prompt: content,
      },
    });

    const msg = await prisma.chatMessage.create({
      data: { assetId: id, jobId: editJob.id, role: 'user', content },
    });
    await fab3dQueue.add('edit-job', { jobId: editJob.id, assetId: id });
    return reply.code(202).send({ message: msg, jobId: editJob.id });
  });

  // ── Worker Routes (x-worker-token) ────────────────────────────────────────
  app.post('/api/fab3d/worker/heartbeat', { preHandler: [requireWorker] }, async (req) => {
    const body = (req.body || {}) as {
      workerId?: string;
      currentJobId?: string | null;
      vramFreeMib?: number;
      vramUsedMib?: number;
    };
    const hb = {
      workerId: body.workerId || 'local-rtx3060',
      currentJobId: body.currentJobId ?? null,
      vramFreeMib: Number(body.vramFreeMib || 0),
      vramUsedMib: Number(body.vramUsedMib || 0),
      ts: new Date().toISOString(),
    };
    await setWorkerHeartbeat(hb);
    return { ok: true };
  });

  app.post('/api/fab3d/worker/claim', { preHandler: [requireWorker] }, async (req) => {
    await releaseExpiredLeases();
    const body = (req.body || {}) as { workerId?: string; leaseMinutes?: number };
    const workerId = body.workerId || 'local-rtx3060';
    const leaseMin = Number(body.leaseMinutes || LEASE_MIN);

    // Serial GPU: do not claim if another job is actively running on this worker
    const nextJob = await prisma.job.findFirst({
      where: { status: 'queued' },
      orderBy: { createdAt: 'asc' },
      include: { asset: true, inputs: true },
    });
    if (!nextJob) return { job: null };

    const leaseUntil = new Date(Date.now() + leaseMin * 60 * 1000);
    const claimed = await prisma.job.update({
      where: { id: nextJob.id },
      data: { status: 'claimed', workerId, leaseUntil },
      include: { asset: true, inputs: true },
    });
    await prisma.asset.update({ where: { id: claimed.assetId }, data: { status: 'running' } });
    return { job: claimed };
  });

  app.get('/api/fab3d/worker/jobs/:id/inputs/:inputId', { preHandler: [requireWorker] }, async (req, reply) => {
    const { id, inputId } = req.params as { id: string; inputId: string };
    const inp = await prisma.jobInput.findFirst({ where: { id: inputId, jobId: id } });
    if (!inp) return reply.code(404).send({ error: 'Input não encontrado' });
    const stream = await getObjectStream(inp.minioKey);
    reply.header('Content-Type', inp.mimeType);
    return reply.send(stream);
  });

  app.patch('/api/fab3d/worker/jobs/:id/progress', { preHandler: [requireWorker] }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const body = (req.body || {}) as {
      status?: string;
      stage?: string;
      progress?: number;
      metrics?: Record<string, unknown>;
      error?: string;
    };
    const job = await prisma.job.findUnique({ where: { id } });
    if (!job) return reply.code(404).send({ error: 'Job não encontrado' });

    const leaseUntil = new Date(Date.now() + LEASE_MIN * 60 * 1000);
    const updated = await prisma.job.update({
      where: { id },
      data: {
        status: body.status || 'running',
        stage: body.stage || job.stage,
        progress: typeof body.progress === 'number' ? body.progress : job.progress,
        metricsJson: body.metrics ? (body.metrics as object) : undefined,
        error: body.error ?? undefined,
        leaseUntil,
      },
    });
    if (body.status === 'failed') {
      await prisma.asset.update({ where: { id: job.assetId }, data: { status: 'failed' } });
    }
    return { job: updated };
  });

  app.post('/api/fab3d/worker/jobs/:id/results', { preHandler: [requireWorker] }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const job = await prisma.job.findUnique({ where: { id }, include: { asset: true } });
    if (!job) return reply.code(404).send({ error: 'Job não encontrado' });

    const filesMap: Record<string, string> = {};
    let qaJson: Record<string, unknown> = {};

    const parts = req.parts();
    for await (const part of parts) {
      if (part.type === 'field' && part.fieldname === 'qa_json') {
        try { qaJson = JSON.parse(String(part.value || '{}')); } catch { qaJson = {}; }
      } else if (part.type === 'file') {
        const buf = await part.toBuffer();
        const fname = (part.filename || part.fieldname).replace(/[^a-zA-Z0-9._-]/g, '_');
        const key = `${job.asset.userId}/${job.assetId}/${job.id}/results/${fname}`;
        const mime = fname.endsWith('.png') ? 'image/png' : fname.endsWith('.json') ? 'application/json' : 'model/gltf-binary';
        await uploadBuffer(key, buf, mime);
        filesMap[part.fieldname] = key;
      }
    }

    const updated = await prisma.job.update({
      where: { id },
      data: {
        status: 'review',
        stage: 'qa',
        progress: 100,
        leaseUntil: null,
        resultsJson: { files: filesMap, qa: qaJson } as object,
      },
    });
    await prisma.asset.update({ where: { id: job.assetId }, data: { status: 'review' } });
    return { job: updated, files: filesMap };
  });

  app.post('/api/fab3d/worker/jobs/:id/chat_reply', { preHandler: [requireWorker] }, async (req, reply) => {
    const { id } = req.params as { id: string };
    const body = (req.body || {}) as {
      content?: string;
      plan?: Record<string, unknown>;
      artifacts?: Record<string, unknown>;
    };
    const job = await prisma.job.findUnique({ where: { id } });
    if (!job) return reply.code(404).send({ error: 'Job não encontrado' });

    const msg = await prisma.chatMessage.create({
      data: {
        assetId: job.assetId,
        jobId: job.id,
        role: 'agent',
        content: body.content || '',
        planJson: body.plan ? (body.plan as object) : undefined,
        artifactsJson: body.artifacts ? (body.artifacts as object) : undefined,
      },
    });
    return { message: msg };
  });

  const port = Number(process.env.PORT || 3100);
  await app.listen({ port, host: '0.0.0.0' });
}

start().catch((err) => {
  console.error(err);
  process.exit(1);
});

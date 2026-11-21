import { Queue } from 'bullmq';
import IORedis from 'ioredis';

const REDIS_HOST = process.env.REDIS_HOST || 'fab3d-redis';
const REDIS_PORT = Number(process.env.REDIS_PORT || 6379);

export const redis = new IORedis({
  host: REDIS_HOST,
  port: REDIS_PORT,
  maxRetriesPerRequest: null,
});

export const fab3dQueue = new Queue('fab3d-jobs', {
  connection: { host: REDIS_HOST, port: REDIS_PORT },
  defaultJobOptions: {
    attempts: 1,
    removeOnComplete: 200,
    removeOnFail: 200,
  },
});

const HB_KEY = 'fab3d:worker:heartbeat';

export interface WorkerHeartbeat {
  workerId: string;
  currentJobId: string | null;
  vramFreeMib: number;
  vramUsedMib: number;
  ts: string;
}

export async function setWorkerHeartbeat(hb: WorkerHeartbeat): Promise<void> {
  await redis.set(HB_KEY, JSON.stringify(hb), 'EX', 90);
}

export async function getWorkerHeartbeat(): Promise<(WorkerHeartbeat & { online: boolean }) | null> {
  const raw = await redis.get(HB_KEY);
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw) as WorkerHeartbeat;
    return { ...parsed, online: true };
  } catch {
    return null;
  }
}

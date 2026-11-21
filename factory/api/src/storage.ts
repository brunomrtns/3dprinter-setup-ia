import { Client } from 'minio';
import { Readable } from 'stream';

export const MINIO_BUCKET = process.env.MINIO_BUCKET || 'fab3d';

export const minio = new Client({
  endPoint: process.env.MINIO_ENDPOINT || 'fab3d-minio',
  port: Number(process.env.MINIO_PORT || 9000),
  useSSL: process.env.MINIO_USE_SSL === 'true',
  accessKey: process.env.MINIO_ROOT_USER || 'fab3dadmin',
  secretKey: process.env.MINIO_ROOT_PASSWORD || '',
});

export async function ensureBucket(): Promise<void> {
  const exists = await minio.bucketExists(MINIO_BUCKET);
  if (!exists) {
    await minio.makeBucket(MINIO_BUCKET, 'us-east-1');
  }
}

export async function uploadBuffer(
  key: string,
  buf: Buffer,
  contentType = 'application/octet-stream'
): Promise<void> {
  await minio.putObject(MINIO_BUCKET, key, buf, buf.length, {
    'Content-Type': contentType,
  });
}

export async function getObjectStream(key: string): Promise<Readable> {
  return minio.getObject(MINIO_BUCKET, key);
}

export async function presignedDownloadUrl(key: string, expirySec = 900): Promise<string> {
  return minio.presignedGetObject(MINIO_BUCKET, key, expirySec);
}

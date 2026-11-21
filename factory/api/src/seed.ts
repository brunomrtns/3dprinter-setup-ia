import { PrismaClient } from '@prisma/client';
import bcrypt from 'bcryptjs';

const prisma = new PrismaClient();

async function main() {
  const email = process.env.ADMIN_EMAIL || 'bruno@brunointegrations.com';
  const password = process.env.ADMIN_PASSWORD || '';
  const name = process.env.ADMIN_NAME || 'Bruno';

  if (!password) {
    console.error('[seed] ADMIN_PASSWORD not set; skipping admin seed.');
    return;
  }

  const hash = await bcrypt.hash(password, 10);
  await prisma.user.upsert({
    where: { email },
    update: { name, role: 'admin', passwordHash: hash },
    create: { email, name, role: 'admin', passwordHash: hash },
  });
  console.log(`[seed] Admin account ensured: ${email}`);
}

main()
  .catch((err) => {
    console.error('[seed] Failed:', err);
    process.exit(1);
  })
  .finally(async () => {
    await prisma.$disconnect();
  });

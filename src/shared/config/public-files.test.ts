import { createHash } from 'node:crypto';
import { readdir, readFile } from 'node:fs/promises';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { ATLAS_SHA256, PUBLIC_DIRECTORY, PUBLIC_FILE, PUBLIC_FILES } from './public-files';

const publicDirectory = join(process.cwd(), PUBLIC_DIRECTORY);

describe('public surface', () => {
  it('publishes exactly the seven legacy files, with no subdirectory or dotfile', async () => {
    const entries = await readdir(publicDirectory, { recursive: true });

    expect([...entries].sort()).toEqual([...PUBLIC_FILES].sort());
  });

  it('keeps the atlas byte-identical to the pinned checksum', async () => {
    const atlas = await readFile(join(publicDirectory, PUBLIC_FILE.ATLAS));

    expect(createHash('sha256').update(atlas).digest('hex')).toBe(ATLAS_SHA256);
  });
});

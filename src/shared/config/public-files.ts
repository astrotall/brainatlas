export const PUBLIC_DIRECTORY = 'public';

export const PUBLIC_FILE = {
  HOME: 'index.html',
  WORKBOOK: 'workbook.html',
  KIRA: 'kira.html',
  ATLAS: 'mozg-3d-atlas-2.html',
  ATLAS_PREVIEW: 'atlas-preview.jpg',
  FREESURFER_LICENSE: 'LICENSE-freesurfer.txt',
  ATLAS_DATA_LICENSE: 'LICENSE-atlas-data.txt',
} as const;

export type PublicFile = (typeof PUBLIC_FILE)[keyof typeof PUBLIC_FILE];

export const PUBLIC_FILES: readonly PublicFile[] = Object.values(PUBLIC_FILE);

export const ATLAS_SHA256 = 'f42576a03823b454aa56aa00c51a1c5915b3c28b63c521fe4b35c7784635bf4a';

export const toPublicPath = (file: PublicFile): string => `/${file}`;

import type { components } from './generated/schema';

export type { operations as ApiOperations, paths as ApiPaths } from './generated/schema';

export type ApiSchemas = components['schemas'];

import { describe, expectTypeOf, it } from 'vitest';
import type { ApiOperations, ApiPaths, ApiSchemas } from './index';

type ListQuery = ApiOperations['list_reviews']['parameters']['query'];

type CreatedBody =
  ApiPaths['/api/reviews']['post']['responses'][202]['content']['application/json'];

describe('generated API types', () => {
  it('describes a submission exactly', () => {
    expectTypeOf<ApiSchemas['CreateReviewRequest']>().toEqualTypeOf<{
      rating: number;
      text: string;
      lang: 'ru' | 'en';
      turnstileToken: string;
    }>();
    expectTypeOf<CreatedBody>().toEqualTypeOf<{ status: 'pending' }>();
  });

  it('describes the public list', () => {
    expectTypeOf<ListQuery>().toEqualTypeOf<{ lang: 'ru' | 'en'; limit?: number }>();
    expectTypeOf<ApiSchemas['ReviewList']['items'][number]>().toEqualTypeOf<{
      id: string;
      rating: number;
      text: string;
      lang: 'ru' | 'en';
      translated: boolean;
      createdAt: string;
    }>();
  });

  it('describes the visit counter', () => {
    expectTypeOf<ApiSchemas['VisitStats']>().toEqualTypeOf<{ today: number; total: number }>();
  });

  it('lists every error code and field reason the client has to translate', () => {
    expectTypeOf<ApiSchemas['ErrorCode']>().toEqualTypeOf<
      | 'validation_failed'
      | 'turnstile_failed'
      | 'rate_limited'
      | 'not_found'
      | 'method_not_allowed'
      | 'service_unavailable'
      | 'not_implemented'
      | 'internal'
    >();
    expectTypeOf<ApiSchemas['FieldReason']>().toEqualTypeOf<
      'missing' | 'invalid' | 'too_short' | 'too_long' | 'links_not_allowed' | 'unknown_field'
    >();
    expectTypeOf<ApiSchemas['ErrorDetail']['fields']>().toEqualTypeOf<
      ApiSchemas['FieldError'][] | undefined
    >();
  });
});

import { z } from "zod";

export const OrganizationSchema = z.object({
  name: z.string(),
  slug: z.string(),
});

export const SearchHitSchema = z.object({
  reference: z.string(),
  slug: z.string(),
  contract_type: z.string(),
  organization: OrganizationSchema,
});

export const PaginationSchema = z.object({
  page: z.number().int().min(1),
  page_count: z.number().int().min(0),
});

export const SearchResponseSchema = z.object({
  data: z.array(SearchHitSchema),
  metadata: PaginationSchema,
});

export const OfficeSchema = z.object({
  // WTTJ sends null for some offices.
  city: z.string().nullable(),
  country_code: z.string(),
});

export const JobDetailSchema = z.object({
  wttj_reference: z.string(),
  slug: z.string(),
  name: z.string(),
  contract_type: z.string(),
  status: z.string(),
  organization: OrganizationSchema,
  offices: z.array(OfficeSchema),
  published_at: z.string(),
  start_date: z.string().nullable().optional().default(null),
  salary_min: z.number().nullable().optional().default(null),
  salary_max: z.number().nullable().optional().default(null),
  salary_currency: z.string().nullable().optional().default(null),
  salary_period: z.string().nullable().optional().default(null),
  apply_url: z.string().nullable().optional().default(null),
});

export const DetailResponseSchema = z.object({
  job: JobDetailSchema,
});

export type Organization = z.infer<typeof OrganizationSchema>;
export type SearchHit = z.infer<typeof SearchHitSchema>;
export type SearchResponse = z.infer<typeof SearchResponseSchema>;
export type Office = z.infer<typeof OfficeSchema>;
export type JobDetail = z.infer<typeof JobDetailSchema>;
export type DetailResponse = z.infer<typeof DetailResponseSchema>;

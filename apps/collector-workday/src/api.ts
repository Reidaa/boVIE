import { z } from "zod";

const WorkdayUrlSchema = z.string().transform((value, ctx) => {
  let parsed: URL;
  try {
    parsed = new URL(value);
  } catch {
    ctx.addIssue({
      code: "custom",
      message: "Expected https://<tenant>.<wdN>.myworkdayjobs.com/<site>",
    });
    return z.NEVER;
  }
  const labels = parsed.hostname.split(".");
  const trimmedPath = parsed.pathname.replace(/^\/+|\/+$/g, "");
  if (
    parsed.protocol !== "https:" ||
    labels.length !== 4 ||
    labels[2] !== "myworkdayjobs" ||
    labels[3] !== "com" ||
    !trimmedPath
  ) {
    ctx.addIssue({
      code: "custom",
      message: "Expected https://<tenant>.<wdN>.myworkdayjobs.com/<site>",
    });
    return z.NEVER;
  }
  return parsed;
});

// The Python config also accepted snake_case filter keys. Rename them when the
// camelCase key is absent; when both are given, the strict schema rejects the extra key.
function acceptSnakeCase(input: unknown): unknown {
  if (input === null || typeof input !== "object" || Array.isArray(input)) {
    return input;
  }
  const board: Record<string, unknown> = { ...input };
  for (const [snake, camel] of [
    ["search_text", "searchText"],
    ["applied_facets", "appliedFacets"],
  ] as const) {
    if (snake in board && !(camel in board)) {
      board[camel] = board[snake];
      delete board[snake];
    }
  }
  return board;
}

const BoardRawSchema = z.preprocess(
  acceptSnakeCase,
  z.strictObject({
    url: WorkdayUrlSchema,
    company: z.string().min(1),
    searchText: z.string().default(""),
    appliedFacets: z.record(z.string(), z.array(z.string())).default({}),
  }),
);

export interface Board {
  readonly url: string;
  readonly company: string;
  readonly searchText: string;
  readonly appliedFacets: Record<string, string[]>;
  readonly origin: string;
  readonly tenant: string;
  readonly site: string;
  readonly name: string;
  readonly apiUrl: string;
}

export const BoardSchema = BoardRawSchema.transform((data): Board => {
  const origin = `https://${data.url.hostname}`;
  const tenant = data.url.hostname.split(".")[0] ?? "";
  // A locale may precede the site: /en-US/<site>.
  const pathSegments = data.url.pathname.replace(/\/+$/, "").split("/");
  const site = pathSegments[pathSegments.length - 1] ?? "";
  const name = `${tenant}/${site}`;
  return {
    url: data.url.toString(),
    company: data.company,
    searchText: data.searchText,
    appliedFacets: data.appliedFacets,
    origin,
    tenant,
    site,
    name,
    apiUrl: `${origin}/wday/cxs/${tenant}/${site}`,
  };
});

export function parseBoard(input: unknown): Board {
  return BoardSchema.parse(input);
}

const PostingRawSchema = z.object({
  title: z.string(),
  externalPath: z.string().refine((path) => path.startsWith("/job/") && !path.includes(".."), {
    message: "Unexpected Workday job path",
  }),
});

export interface Posting {
  readonly title: string;
  readonly externalPath: string;
  readonly jobId: string;
}

export const PostingSchema = PostingRawSchema.transform((data): Posting => {
  const segments = data.externalPath.split("/");
  return {
    title: data.title,
    externalPath: data.externalPath,
    jobId: segments[segments.length - 1] ?? "",
  };
});

export const SearchResponseSchema = z.object({
  // Set only on the first page; later pages return 0.
  total: z.number().int().min(0),
  jobPostings: z.array(PostingSchema),
});

export const JobDetailSchema = z.object({
  title: z.string(),
  jobPostingId: z.string(),
  posted: z.boolean(),
  location: z.string().nullable().optional().default(null),
  additionalLocations: z.array(z.string()).optional().default([]),
  startDate: z.string().nullable().optional().default(null),
  endDate: z.string().nullable().optional().default(null),
  timeType: z.string().nullable().optional().default(null),
  jobReqId: z.string().nullable().optional().default(null),
  jobRequisitionLocation: z
    .object({
      country: z
        .object({
          alpha2Code: z.string().nullable().optional().default(null),
        })
        .nullable()
        .optional()
        .default(null),
    })
    .nullable()
    .optional()
    .default(null),
});

export const DetailResponseSchema = z.object({
  jobPostingInfo: JobDetailSchema,
});

export type SearchResponse = z.infer<typeof SearchResponseSchema>;
export type JobDetail = z.infer<typeof JobDetailSchema>;
export type DetailResponse = z.infer<typeof DetailResponseSchema>;

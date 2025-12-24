import { z } from "zod";

const envSchema = z.object({
  apiBaseUrl: z.string().url().default("http://localhost:8000")
});

const parsed = envSchema.safeParse({
  apiBaseUrl: import.meta.env.VITE_API_BASE_URL
});

if (!parsed.success) {
  console.warn("Invalid environment configuration", parsed.error.flatten().fieldErrors);
}

export const env = parsed.success ? parsed.data : envSchema.parse({});

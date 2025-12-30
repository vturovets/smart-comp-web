import {
  ArtifactList,
  ConfigDefaults,
  CreateJobPayload,
  JobCreateResponse,
  JobResults,
  JobStatus,
  JobSummary
} from "./types";

export interface ApiClientOptions {
  baseUrl: string;
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  const contentType = response.headers.get("content-type");
  if (contentType && contentType.includes("application/json")) {
    return (await response.json()) as T;
  }

  // eslint-disable-next-line @typescript-eslint/consistent-type-assertions
  return (await response.text()) as T;
}

export class ApiClient {
  private readonly baseUrl: string;

  constructor(options: ApiClientOptions) {
    this.baseUrl = options.baseUrl.replace(/\/$/, "");
  }

  async getHealth(): Promise<{ status: string }> {
    const response = await fetch(`${this.baseUrl}/api/health`);
    return handleResponse(response);
  }

  async getConfigDefaults(): Promise<ConfigDefaults> {
    const response = await fetch(`${this.baseUrl}/api/config/defaults`);
    return handleResponse(response);
  }

  async createJob(payload: CreateJobPayload): Promise<JobCreateResponse> {
    const formData = new FormData();
    formData.append("jobType", payload.jobType);
    if (payload.config) {
      formData.append("config", JSON.stringify(payload.config));
    }
    payload.files?.forEach((file) => formData.append("files", file));

    const response = await fetch(`${this.baseUrl}/api/jobs`, {
      method: "POST",
      body: formData
    });

    return handleResponse(response);
  }

  async getJob(jobId: string): Promise<JobSummary> {
    const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}`);
    return handleResponse(response);
  }

  async cancelJob(jobId: string): Promise<void> {
    const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}/cancel`, {
      method: "POST"
    });
    await handleResponse(response);
  }

  async getResults(jobId: string): Promise<JobResults> {
    const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}/results`);
    return handleResponse(response);
  }

  async listArtifacts(jobId: string): Promise<ArtifactList> {
    const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}/artifacts`);
    return handleResponse(response);
  }

  async downloadArtifactWithInfo(
    jobId: string,
    name: string
  ): Promise<{ blob: Blob; contentType: string | null }> {
    const response = await fetch(`${this.baseUrl}/api/jobs/${jobId}/artifacts/${name}`);
    if (!response.ok) {
      throw new Error(`Failed to download artifact ${name}`);
    }
    const blob = await response.blob();
    return { blob, contentType: response.headers.get("content-type") };
  }

  async downloadArtifact(jobId: string, name: string): Promise<Blob> {
    const { blob } = await this.downloadArtifactWithInfo(jobId, name);
    return blob;
  }
}

export const buildApiClient = (baseUrl: string) => new ApiClient({ baseUrl });

import path from "node:path";
import { fileURLToPath } from "node:url";

import { PactV3, Matchers } from "@pact-foundation/pact";
import { describe, expect, it } from "vitest";

import { JobStatus, JobType, buildApiClient } from "../../src/api";

const pactDir = path.resolve(fileURLToPath(new URL(".", import.meta.url)), "../../pacts");

const provider = new PactV3({ dir: pactDir, consumer: "smart-comp-web", provider: "smart-comp-api" });

describe("PACT consumer contracts", () => {
  it("fetches config defaults", async () => {
    provider
      .given("config defaults available")
      .uponReceiving("a request for config defaults")
      .withRequest({
        method: "GET",
        path: "/api/config/defaults"
      })
      .willRespondWith({
        status: 200,
        headers: { "Content-Type": "application/json" },
        body: {
          alpha: 0.05,
          descriptiveEnabled: true,
          createLog: false,
          cleanAll: false,
          plots: {}
        }
      });

    await provider.executeTest(async (mockServer) => {
      const client = buildApiClient(mockServer.url);
      const defaults = await client.getConfigDefaults();
      expect(defaults.alpha).toBe(0.05);
      expect(defaults.descriptiveEnabled).toBe(true);
    });
  });

  it("creates a job and fetches lifecycle resources", async () => {
    const jobId = "pact-job-1";

    provider
      .given("ready to accept job creation")
      .uponReceiving("create job request")
      .withRequest({
        method: "POST",
        path: "/api/jobs"
      })
      .willRespondWith({
        status: 200,
        headers: { "Content-Type": "application/json" },
        body: { jobId }
      });

    provider
      .given("job is complete")
      .uponReceiving("job status request")
      .withRequest({ method: "GET", path: `/api/jobs/${jobId}` })
      .willRespondWith({
        status: 200,
        headers: { "Content-Type": "application/json" },
        body: {
          jobId,
          jobType: JobType.BOOTSTRAP_SINGLE,
          status: JobStatus.COMPLETED,
          createdAt: Matchers.regex({
            generate: "2023-01-01T00:00:00Z",
            matcher: ".+"
          }),
          progress: { percent: 100 }
        }
      });

    provider
      .given("results ready")
      .uponReceiving("job results request")
      .withRequest({ method: "GET", path: `/api/jobs/${jobId}/results` })
      .willRespondWith({
        status: 200,
        headers: { "Content-Type": "application/json" },
        body: {
          jobId,
          jobType: JobType.BOOTSTRAP_SINGLE,
          decision: { alpha: 0.05, pValue: 0.03, significant: true },
          metrics: { delta: 1.2 },
          descriptive: { mean: 1.5 },
          plots: [{ artifactName: "plot.json", kind: "histogram" }]
        }
      });

    provider
      .given("artifacts ready")
      .uponReceiving("artifact list request")
      .withRequest({ method: "GET", path: `/api/jobs/${jobId}/artifacts` })
      .willRespondWith({
        status: 200,
        headers: { "Content-Type": "application/json" },
        body: {
          jobId,
          artifacts: [
            {
              name: "plot.json",
              sizeBytes: 1024,
              createdAt: Matchers.regex({
                generate: "2023-01-01T00:00:00Z",
                matcher: ".+"
              }),
              contentType: "application/json"
            }
          ]
        }
      });

    provider
      .given("plot artifact available")
      .uponReceiving("artifact download")
      .withRequest({ method: "GET", path: `/api/jobs/${jobId}/artifacts/plot.json` })
      .willRespondWith({
        status: 200,
        headers: { "Content-Type": "application/json" },
        body: { data: [{ x: [1, 2], y: [3, 4], type: "bar" }] }
      });

    await provider.executeTest(async (mockServer) => {
      const client = buildApiClient(mockServer.url);
      const creation = await client.createJob({ jobType: JobType.BOOTSTRAP_SINGLE, file1: new File([], "a.csv") });
      expect(creation.jobId).toEqual(jobId);

      const status = await client.getJob(jobId);
      expect(status.status).toEqual(JobStatus.COMPLETED);

      const results = await client.getResults(jobId);
      expect(results.jobId).toEqual(jobId);

      const artifacts = await client.listArtifacts(jobId);
      expect(artifacts.artifacts.length).toBeGreaterThan(0);

      const blob = await client.downloadArtifact(jobId, "plot.json");
      expect(await blob.text()).toContain("data");
    });
  });
});

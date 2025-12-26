import { Publisher } from "@pact-foundation/pact";
import path from "node:path";

const brokerBaseUrl = process.env.PACT_BROKER_BASE_URL;
const brokerToken = process.env.PACT_BROKER_TOKEN;
const consumerVersion = process.env.PACT_CONSUMER_VERSION || process.env.GIT_COMMIT || "dev";
const tags = (process.env.PACT_TAGS || "dev").split(",").map((t) => t.trim());

if (!brokerBaseUrl) {
  console.error("PACT_BROKER_BASE_URL is required to publish contracts");
  process.exit(1);
}

const publisher = new Publisher({
  pactBroker: brokerBaseUrl,
  pactFilesOrDirs: [path.resolve(process.cwd(), "pacts")],
  pactBrokerToken: brokerToken,
  consumerVersion,
  tags
});

publisher
  .publishPacts()
  .then(() => {
    console.log("Pact contracts published");
  })
  .catch((error) => {
    console.error("Failed to publish pacts", error);
    process.exit(1);
  });

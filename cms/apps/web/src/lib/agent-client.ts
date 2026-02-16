/**
 * VTV Agent API Client
 *
 * Configured to connect to the FastAPI agent service.
 * Types are auto-generated from the OpenAPI spec via @vtv/sdk.
 *
 * Usage:
 *   import { chatWithAgent, listModels } from "@/lib/agent-client"
 */

const AGENT_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

export async function chatWithAgent(message: string) {
  const response = await fetch(`${AGENT_URL}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      messages: [{ role: "user", content: message }],
    }),
  });

  if (!response.ok) {
    throw new Error(`Agent API error: ${response.status}`);
  }

  return response.json();
}

export async function listModels() {
  const response = await fetch(`${AGENT_URL}/v1/models`);
  if (!response.ok) {
    throw new Error(`Agent API error: ${response.status}`);
  }
  return response.json();
}

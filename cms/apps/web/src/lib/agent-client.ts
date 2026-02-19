/**
 * VTV Agent API Client
 *
 * Configured to connect to the FastAPI agent service.
 * Supports multi-turn conversations with full message history.
 *
 * Usage:
 *   import { sendChatMessage, listModels } from "@/lib/agent-client"
 */

import type {
  ChatCompletionResponse,
  MessageRole,
} from "@/types/chat";

const AGENT_URL =
  process.env.NEXT_PUBLIC_AGENT_URL ?? "http://localhost:8123";

/** Error thrown when the agent API returns a non-OK response. */
export class AgentApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.name = "AgentApiError";
    this.status = status;
  }
}

/**
 * Send a message to the agent with full conversation history.
 *
 * @param messages - Array of {role, content} messages (full conversation).
 * @returns The parsed ChatCompletionResponse from the backend.
 * @throws AgentApiError if the API returns non-OK status.
 */
export async function sendChatMessage(
  messages: Array<{ role: MessageRole; content: string }>
): Promise<ChatCompletionResponse> {
  const response = await fetch(`${AGENT_URL}/v1/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ messages }),
  });

  if (!response.ok) {
    const detail = await response.text().catch(() => "Unknown error");
    throw new AgentApiError(response.status, detail);
  }

  return response.json() as Promise<ChatCompletionResponse>;
}

/** Legacy single-message wrapper for backwards compatibility. */
export async function chatWithAgent(
  message: string
): Promise<ChatCompletionResponse> {
  return sendChatMessage([{ role: "user", content: message }]);
}

export async function listModels(): Promise<unknown> {
  const response = await fetch(`${AGENT_URL}/v1/models`);
  if (!response.ok) {
    throw new AgentApiError(
      response.status,
      `Agent API error: ${response.status}`
    );
  }
  return response.json();
}

/**
 * Agent (Chat) API client powered by @vtv/sdk.
 *
 * Drop-in replacement for agent-client.ts — same function signatures,
 * backed by the generated SDK instead of hand-written fetch calls.
 */

import "@/lib/sdk";
import {
  chatCompletionsV1ChatCompletionsPost,
  listModelsV1ModelsGet,
} from "@vtv/sdk";
import type {
  ChatCompletionResponse,
  MessageRole,
} from "@/types/chat";

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
  messages: Array<{ role: MessageRole; content: string }>,
): Promise<ChatCompletionResponse> {
  const { data, error, response } =
    await chatCompletionsV1ChatCompletionsPost({
      body: { messages },
    });
  if (error || !data) {
    throw new AgentApiError(
      response.status,
      typeof error === "string" ? error : "Failed to send chat message",
    );
  }
  return data as unknown as ChatCompletionResponse;
}

/** Legacy single-message wrapper for backwards compatibility. */
export async function chatWithAgent(
  message: string,
): Promise<ChatCompletionResponse> {
  return sendChatMessage([{ role: "user", content: message }]);
}

/** List available models. */
export async function listModels(): Promise<unknown> {
  const { data, error, response } = await listModelsV1ModelsGet();
  if (error || !data) {
    throw new AgentApiError(
      response.status,
      typeof error === "string" ? error : "Failed to list models",
    );
  }
  return data;
}

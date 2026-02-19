/** Message roles matching the backend OpenAI-compatible schema. */
export type MessageRole = "user" | "assistant";

/** A single message in the chat conversation. */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
}

/** A single choice in the backend response. */
export interface ChatCompletionChoice {
  index: number;
  message: { role: string; content: string };
  finish_reason: string;
}

/** Backend response format (OpenAI-compatible). */
export interface ChatCompletionResponse {
  id: string;
  object: string;
  created: number;
  model: string;
  choices: ChatCompletionChoice[];
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

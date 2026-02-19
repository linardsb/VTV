"use client";

import { useCallback, useRef, useState } from "react";
import type { ChatMessage } from "@/types/chat";
import { AgentApiError, sendChatMessage } from "@/lib/agent-client";

interface UseChatAgentReturn {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  sendMessage: (content: string) => Promise<void>;
  clearMessages: () => void;
  retryLast: () => Promise<void>;
}

export function useChatAgent(): UseChatAgentReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (content: string) => {
      if (!content.trim() || isLoading) return;

      const userMessage: ChatMessage = {
        id: crypto.randomUUID(),
        role: "user",
        content: content.trim(),
        timestamp: Date.now(),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsLoading(true);
      setError(null);

      try {
        const allMessages = [...messages, userMessage];
        const apiMessages = allMessages.map((m) => ({
          role: m.role,
          content: m.content,
        }));

        const response = await sendChatMessage(apiMessages);

        const assistantContent =
          response.choices[0]?.message?.content ?? "...";

        const assistantMessage: ChatMessage = {
          id: response.id,
          role: "assistant",
          content: assistantContent,
          timestamp: Date.now(),
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } catch (err) {
        if (err instanceof AgentApiError && err.status === 429) {
          setError("rate_limit");
        } else {
          setError("generic");
        }
      } finally {
        setIsLoading(false);
      }
    },
    [messages, isLoading]
  );

  const clearMessages = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
    setIsLoading(false);
  }, []);

  const retryLast = useCallback(async () => {
    const lastUserIndex = messages.findLastIndex((m) => m.role === "user");
    if (lastUserIndex === -1) return;

    const lastUserContent = messages[lastUserIndex].content;
    const historyUpToUser = messages.slice(0, lastUserIndex);
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: lastUserContent,
      timestamp: Date.now(),
    };

    setMessages([...historyUpToUser, userMessage]);
    setIsLoading(true);
    setError(null);

    try {
      const apiMessages = [...historyUpToUser, userMessage].map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const response = await sendChatMessage(apiMessages);
      const assistantContent =
        response.choices[0]?.message?.content ?? "...";
      const assistantMessage: ChatMessage = {
        id: response.id,
        role: "assistant",
        content: assistantContent,
        timestamp: Date.now(),
      };
      setMessages((prev) => [...prev, assistantMessage]);
    } catch (err) {
      if (err instanceof AgentApiError && err.status === 429) {
        setError("rate_limit");
      } else {
        setError("generic");
      }
    } finally {
      setIsLoading(false);
    }
  }, [messages]);

  return {
    messages,
    isLoading,
    error,
    sendMessage,
    clearMessages,
    retryLast,
  };
}

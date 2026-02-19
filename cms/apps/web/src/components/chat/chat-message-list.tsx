"use client";

import { useEffect, useRef } from "react";
import { AlertCircle, Loader2, RotateCcw } from "lucide-react";
import { useTranslations } from "next-intl";
import type { ChatMessage } from "@/types/chat";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ChatMessageBubble } from "@/components/chat/chat-message-bubble";

interface ChatMessageListProps {
  messages: ChatMessage[];
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
}

export function ChatMessageList({
  messages,
  isLoading,
  error,
  onRetry,
}: ChatMessageListProps) {
  const t = useTranslations("chat");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages.length, isLoading]);

  return (
    <ScrollArea className="flex-1 overflow-hidden">
      <div className="flex flex-col gap-(--spacing-card) py-(--spacing-card)">
        {messages.map((message) => (
          <ChatMessageBubble key={message.id} message={message} />
        ))}

        {isLoading && (
          <div className="flex gap-(--spacing-sm) px-(--spacing-sm)">
            <div className="size-8 shrink-0" />
            <div className="space-y-(--spacing-tight) rounded-xl border border-border-subtle bg-surface-raised px-(--spacing-card) py-(--spacing-sm) shadow-(--shadow-sm)">
              <div className="flex items-center gap-(--spacing-sm) text-sm text-foreground-muted">
                <Loader2 className="size-4 animate-spin" />
                <span>{t("thinking")}</span>
              </div>
              <Skeleton className="mt-(--spacing-tight) h-4 w-48" />
              <Skeleton className="mt-(--spacing-tight) h-4 w-32" />
            </div>
          </div>
        )}

        {error && (
          <div className="mx-(--spacing-sm) flex items-center gap-(--spacing-sm) rounded-lg border border-red-200 bg-red-50 px-(--spacing-card) py-(--spacing-sm) text-sm text-red-700 dark:border-red-800 dark:bg-red-950 dark:text-red-300">
            <AlertCircle className="size-4 shrink-0" />
            <span className="flex-1">
              {error === "rate_limit" ? t("rateLimitError") : t("error")}
            </span>
            <Button
              variant="ghost"
              size="xs"
              className="cursor-pointer text-red-700 hover:text-red-900 dark:text-red-300 dark:hover:text-red-100"
              onClick={onRetry}
            >
              <RotateCcw className="mr-1 size-3" />
              {t("retry")}
            </Button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}

"use client";

import { Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import { TooltipProvider } from "@/components/ui/tooltip";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { useChatAgent } from "@/hooks/use-chat-agent";
import { ChatEmptyState } from "@/components/chat/chat-empty-state";
import { ChatMessageList } from "@/components/chat/chat-message-list";
import { ChatInput } from "@/components/chat/chat-input";

export default function ChatPage() {
  const t = useTranslations("chat");
  const { messages, isLoading, error, sendMessage, clearMessages, retryLast } =
    useChatAgent();

  const hasMessages = messages.length > 0;

  function handleSend(content: string) {
    void sendMessage(content);
  }

  function handleRetry() {
    void retryLast();
  }

  return (
    <TooltipProvider>
      <div className="flex flex-col md:h-[calc(100vh-var(--spacing-page)*2)]">
        {/* Header */}
        <div className="flex items-center justify-between pb-(--spacing-card)">
          <h1 className="font-heading text-heading font-semibold text-foreground">
            {t("title")}
          </h1>
          {hasMessages && (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="sm"
                  className="cursor-pointer text-foreground-muted hover:text-foreground"
                  onClick={clearMessages}
                >
                  <Trash2 className="mr-(--spacing-tight) size-4" />
                  {t("clear")}
                </Button>
              </TooltipTrigger>
              <TooltipContent>{t("clear")}</TooltipContent>
            </Tooltip>
          )}
        </div>

        {/* Messages area */}
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-lg border border-border bg-background">
          {hasMessages || isLoading ? (
            <ChatMessageList
              messages={messages}
              isLoading={isLoading}
              error={error}
              onRetry={handleRetry}
            />
          ) : (
            <ChatEmptyState onSuggestionClick={handleSend} />
          )}

          {/* Input */}
          <ChatInput onSend={handleSend} isLoading={isLoading} />
        </div>
      </div>
    </TooltipProvider>
  );
}

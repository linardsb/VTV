"use client";

import { Bot, Check, Copy, User } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";
import Markdown from "react-markdown";
import { cn } from "@/lib/utils";
import type { ChatMessage } from "@/types/chat";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ChatMessageBubbleProps {
  message: ChatMessage;
}

export function ChatMessageBubble({ message }: ChatMessageBubbleProps) {
  const t = useTranslations("chat");
  const [copied, setCopied] = useState(false);
  const isUser = message.role === "user";

  function handleCopy() {
    void navigator.clipboard.writeText(message.content);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div
      className={cn(
        "group flex gap-(--spacing-sm) px-(--spacing-sm)",
        isUser ? "flex-row-reverse" : "flex-row"
      )}
    >
      <Avatar className="size-8 shrink-0">
        <AvatarFallback
          className={cn(
            "text-xs font-medium",
            isUser
              ? "bg-interactive text-interactive-foreground"
              : "bg-surface text-foreground-muted border border-border"
          )}
        >
          {isUser ? <User className="size-4" /> : <Bot className="size-4" />}
        </AvatarFallback>
      </Avatar>

      <div
        className={cn(
          "relative max-w-[80%] rounded-xl px-(--spacing-card) py-(--spacing-sm) text-sm leading-relaxed",
          isUser
            ? "bg-interactive text-interactive-foreground rounded-br-sm"
            : "bg-surface-raised border border-border-subtle text-foreground rounded-bl-sm shadow-(--shadow-sm)"
        )}
      >
        {isUser ? (
          <div className="whitespace-pre-wrap break-words">
            {message.content}
          </div>
        ) : (
          <div className="prose prose-sm max-w-none break-words text-foreground [&_pre]:overflow-x-auto [&_pre]:rounded-md [&_pre]:bg-surface [&_pre]:p-3 [&_pre]:font-mono [&_pre]:text-xs [&_code]:rounded [&_code]:bg-surface [&_code]:px-1 [&_code]:py-0.5 [&_code]:font-mono [&_code]:text-xs [&_ul]:list-disc [&_ol]:list-decimal [&_li]:ml-4 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:text-sm [&_h2]:font-semibold [&_h3]:text-sm [&_h3]:font-medium [&_p]:leading-relaxed [&_a]:text-interactive [&_a]:underline [&_table]:w-full [&_th]:border [&_th]:border-border [&_th]:px-2 [&_th]:py-1 [&_th]:text-left [&_th]:font-medium [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1">
            <Markdown>{message.content}</Markdown>
          </div>
        )}

        {!isUser && (
          <div className="mt-(--spacing-tight) flex justify-end opacity-0 transition-opacity group-hover:opacity-100">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  className="cursor-pointer text-foreground-muted hover:text-foreground"
                  onClick={handleCopy}
                >
                  {copied ? (
                    <Check className="size-3" />
                  ) : (
                    <Copy className="size-3" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {copied ? t("copied") : t("copy")}
              </TooltipContent>
            </Tooltip>
          </div>
        )}
      </div>
    </div>
  );
}

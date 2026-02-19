"use client";

import { useRef, useState } from "react";
import { Send } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface ChatInputProps {
  onSend: (message: string) => void;
  isLoading: boolean;
}

export function ChatInput({ onSend, isLoading }: ChatInputProps) {
  const t = useTranslations("chat");
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  function handleSubmit() {
    if (!value.trim() || isLoading) return;
    onSend(value);
    setValue("");
    textareaRef.current?.focus();
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  return (
    <div className="flex items-end gap-(--spacing-sm) border-t border-border bg-background px-(--spacing-card) py-(--spacing-sm)">
      <Textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={t("placeholder")}
        disabled={isLoading}
        className="max-h-32 min-h-10 resize-none"
        rows={1}
        aria-label={t("placeholder")}
      />
      <Tooltip>
        <TooltipTrigger asChild>
          <Button
            size="icon"
            className="shrink-0 cursor-pointer"
            onClick={handleSubmit}
            disabled={!value.trim() || isLoading}
            aria-label={t("send")}
          >
            <Send className="size-4" />
          </Button>
        </TooltipTrigger>
        <TooltipContent>{t("send")}</TooltipContent>
      </Tooltip>
    </div>
  );
}

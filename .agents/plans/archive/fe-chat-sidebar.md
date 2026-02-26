# Plan: Chat UI - AI Assistant Page

## Feature Metadata
**Feature Type**: New Page + Components
**Estimated Complexity**: Medium
**Route**: `/[locale]/(dashboard)/chat`
**Auth Required**: Yes
**Allowed Roles**: admin, dispatcher

## Feature Description

An AI assistant chat page where dispatchers and admins interact with VTV's unified Pydantic AI agent (9 tools: 5 transit + 4 Obsidian vault). The page renders at `/{locale}/chat` inside the existing dashboard layout.

The chat interface follows a standard messaging pattern: a scrollable message history area with user/assistant message bubbles, and a fixed input area at the bottom with a text field and send button. Messages are sent to the FastAPI backend at `POST /v1/chat/completions` (OpenAI-compatible format) and the full conversation history is passed with each request so the agent has context.

The page is purely client-side (no server data fetching needed). The existing `agent-client.ts` will be extended to support multi-turn conversations with proper TypeScript types. The nav sidebar already has a disabled "chat" entry that just needs enabling. The middleware already has `/chat` in the RBAC matcher for admin and dispatcher roles.

## Design System

### Master Rules (from MASTER.md)
- Typography: Lexend headings, Source Sans 3 body, JetBrains Mono for code
- Colors: Navy primary, Blue CTA/accent, Slate backgrounds
- Spacing: Use `--spacing-*` tokens via Tailwind arbitrary values
- No hardcoded colors - all via semantic tokens
- Focus rings, cursor-pointer on clickable elements, transitions 150-300ms
- No emojis as icons - use Lucide React

### Page Override
- None exists - generate during execution using the design system page override pattern if needed

### Tokens Used
- `--spacing-page` (1rem) - main content padding (inherited from layout)
- `--spacing-section` (1rem) - gap between message groups
- `--spacing-card` (0.75rem) - message bubble padding
- `--spacing-inline` (0.375rem) - icon-to-text gaps
- `--spacing-tight` (0.25rem) - micro gaps
- `--spacing-grid` (0.75rem) - gap between input and messages
- `--color-surface` / `--color-surface-raised` - message bubble backgrounds
- `--color-foreground` / `--color-foreground-muted` - text colors
- `--color-border` / `--color-border-subtle` - borders
- `--color-interactive` / `--color-interactive-hover` - send button
- `--font-mono` - code block font
- `--shadow-sm` - subtle lift on message bubbles

## Components Needed

### Existing (shadcn/ui)
- `Button` - send button, clear conversation button
- `Textarea` - message input (auto-grows via `field-sizing-content`)
- `Avatar`, `AvatarFallback` - user/assistant avatars
- `Skeleton` - loading skeleton for assistant response
- `Tooltip`, `TooltipTrigger`, `TooltipContent`, `TooltipProvider` - button tooltips
- `Separator` - visual divider

### New shadcn/ui to Install
- `scroll-area` - `npx shadcn@latest add scroll-area` - smooth scrollable message container

### Custom Components to Create
- `ChatPage` at `cms/apps/web/src/app/[locale]/(dashboard)/chat/page.tsx` - page wrapper (client component)
- `ChatMessageList` at `cms/apps/web/src/components/chat/chat-message-list.tsx` - scrollable message history
- `ChatMessageBubble` at `cms/apps/web/src/components/chat/chat-message-bubble.tsx` - individual message bubble
- `ChatInput` at `cms/apps/web/src/components/chat/chat-input.tsx` - text input with send button
- `ChatEmptyState` at `cms/apps/web/src/components/chat/chat-empty-state.tsx` - initial empty state with suggestions

### Custom Hook to Create
- `useChatAgent` at `cms/apps/web/src/hooks/use-chat-agent.ts` - manages conversation state, API calls, loading/error

### Types to Create
- `ChatMessage` type at `cms/apps/web/src/types/chat.ts`

### Lib to Modify
- `agent-client.ts` at `cms/apps/web/src/lib/agent-client.ts` - add typed multi-turn conversation support

## i18n Keys

### Latvian (`lv.json`)
```json
{
  "chat": {
    "title": "AI palidziba",
    "placeholder": "Jautajiet par marsrutiem, grafikiem, transportlidzekliem...",
    "send": "Nosutit",
    "clear": "Notirit sarunu",
    "thinking": "Domaju...",
    "error": "Radas kluda. Ludzu, meginiet velreiz.",
    "emptyTitle": "Ka es varu palidzet?",
    "emptyDescription": "Jautajiet par autobusu marsrutiem, kavesanos, vaditaju grafikiem vai transporta operacijam.",
    "suggestion1": "Kuri marsruti sodiena kave?",
    "suggestion2": "Paradiet 22. marsruta grafiku",
    "suggestion3": "Cik autobusu ir aktivie?",
    "suggestion4": "Atrast pieturas netalu no centra",
    "you": "Jus",
    "assistant": "VTV asistents",
    "retry": "Meginat velreiz",
    "copied": "Nokopets",
    "copy": "Kopet"
  }
}
```

### English (`en.json`)
```json
{
  "chat": {
    "title": "AI Assistant",
    "placeholder": "Ask about routes, schedules, vehicles...",
    "send": "Send",
    "clear": "Clear conversation",
    "thinking": "Thinking...",
    "error": "Something went wrong. Please try again.",
    "emptyTitle": "How can I help?",
    "emptyDescription": "Ask about bus routes, live delays, driver schedules, or transit operations.",
    "suggestion1": "Which routes are delayed today?",
    "suggestion2": "Show schedule for route 22",
    "suggestion3": "How many buses are active?",
    "suggestion4": "Find stops near the center",
    "you": "You",
    "assistant": "VTV Assistant",
    "retry": "Try again",
    "copied": "Copied",
    "copy": "Copy"
  }
}
```

## Data Fetching

- **API endpoint**: `POST /v1/chat/completions` (FastAPI backend, OpenAI-compatible)
- **Request format**: `{ messages: [{ role: "user"|"assistant", content: string }] }`
- **Response format**: `{ id, object, created, model, choices: [{ index, message: { role, content }, finish_reason }], usage }`
- **Constraints**: Max 20 messages per request, max 4000 chars per message content
- **Rate limit**: 10 requests/minute, 50 queries/day per IP
- **Server vs Client**: 100% client-side - no server data fetching needed
- **Loading states**: Skeleton pulse animation in assistant message bubble while waiting

## RBAC Integration

- **Middleware matcher**: Already configured - `/chat` is in the matcher regex `/(lv|en)/(routes|stops|schedules|gtfs|users|chat)/:path*`
- **Role permissions**: Already configured - `admin` and `dispatcher` have `/chat` access. `editor` and `viewer` do NOT.
- **No changes needed** in `middleware.ts`

## Sidebar Navigation

- **Label key**: `nav.chat` (already exists: LV="AI palidziba", EN="AI Assistant")
- **Position**: Last item in nav list (already exists)
- **Change needed**: Flip `enabled: false` to `enabled: true` in `app-sidebar.tsx` navItems array
- **Role visibility**: Middleware handles access - disabled users get redirected to `/unauthorized`

## Relevant Files

The executing agent MUST read these files before starting implementation.

### Core Files
- `CLAUDE.md` - Architecture rules, frontend conventions
- `cms/design-system/vtv/MASTER.md` - Design system master rules
- `cms/apps/web/CLAUDE.md` - React 19 anti-patterns, zero-warning policy

### Pattern Files (Examples to Follow)
- `cms/apps/web/src/app/[locale]/(dashboard)/routes/page.tsx` - Client component page with hooks, loading states, mobile responsive
- `cms/apps/web/src/hooks/use-vehicle-positions.ts` - Hook pattern for async data fetching with useCallback + useEffect + useRef
- `cms/apps/web/src/components/app-sidebar.tsx` - Nav structure to modify

### Files to Modify
- `cms/apps/web/messages/lv.json` - Add `chat` i18n keys
- `cms/apps/web/messages/en.json` - Add `chat` i18n keys
- `cms/apps/web/src/components/app-sidebar.tsx` - Enable chat nav item
- `cms/apps/web/src/lib/agent-client.ts` - Add typed multi-turn API

### Files to Create
- `cms/apps/web/src/types/chat.ts`
- `cms/apps/web/src/lib/agent-client.ts` (modify existing)
- `cms/apps/web/src/hooks/use-chat-agent.ts`
- `cms/apps/web/src/components/chat/chat-empty-state.tsx`
- `cms/apps/web/src/components/chat/chat-message-bubble.tsx`
- `cms/apps/web/src/components/chat/chat-message-list.tsx`
- `cms/apps/web/src/components/chat/chat-input.tsx`
- `cms/apps/web/src/app/[locale]/(dashboard)/chat/page.tsx`

## React 19 Coding Rules

The executor MUST follow these rules to avoid lint/type errors on first pass:
- **No `setState` in `useEffect`** - use `key` prop on the component to force remount with new initial state
- **No component definitions inside components** - extract all sub-components to module scope or separate files
- **No `Math.random()` in render** - use `useId()` or generate IDs outside render (e.g., `crypto.randomUUID()` in event handlers)
- **Const placeholders for runtime values** (e.g. `const ROLE = "admin"`) must be annotated as `string` to avoid TS2367
- **Hook ordering: `useMemo`/`useCallback` MUST come AFTER their dependencies** - If a memo depends on `typeFilter` from `useState`, the `useState` line must appear first in the component body
- **All clickable elements need `cursor-pointer`** - Tailwind class required on buttons, links
- **All text via `useTranslations()`** - never hardcode user-visible strings

## Step by Step Tasks

IMPORTANT: Execute every step in order, top to bottom. Do not skip steps.

---

### Task 1: Install scroll-area component
**Action:** RUN

```bash
cd cms && npx shadcn@latest add scroll-area --yes
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 2: Add chat types
**File:** `cms/apps/web/src/types/chat.ts` (create)
**Action:** CREATE

```typescript
/** Message roles matching the backend OpenAI-compatible schema. */
export type MessageRole = "user" | "assistant";

/** A single message in the chat conversation. */
export interface ChatMessage {
  id: string;
  role: MessageRole;
  content: string;
  timestamp: number;
}

/** Backend request format (OpenAI-compatible). */
export interface ChatCompletionRequest {
  messages: Array<{ role: string; content: string }>;
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
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 3: Extend agent-client with typed multi-turn support
**File:** `cms/apps/web/src/lib/agent-client.ts` (modify)
**Action:** UPDATE

Replace the entire file content with:

```typescript
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
    throw new AgentApiError(response.status, `Agent API error: ${response.status}`);
  }
  return response.json();
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 4: Create useChatAgent hook
**File:** `cms/apps/web/src/hooks/use-chat-agent.ts` (create)
**Action:** CREATE

This hook manages the full chat lifecycle: message state, API calls, loading, errors.

```typescript
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

  const sendMessage = useCallback(async (content: string) => {
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
      // Build the full history for the API (role + content only)
      const allMessages = [...messages, userMessage];
      const apiMessages = allMessages.map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const response = await sendChatMessage(apiMessages);

      const assistantContent =
        response.choices[0]?.message?.content ?? "No response received.";

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
  }, [messages, isLoading]);

  const clearMessages = useCallback(() => {
    abortRef.current?.abort();
    setMessages([]);
    setError(null);
    setIsLoading(false);
  }, []);

  const retryLast = useCallback(async () => {
    // Find the last user message and re-send from that point
    const lastUserIndex = messages.findLastIndex((m) => m.role === "user");
    if (lastUserIndex === -1) return;

    const lastUserContent = messages[lastUserIndex].content;
    // Remove the failed assistant response (if any) and re-send
    setMessages((prev) => prev.slice(0, lastUserIndex));
    setError(null);

    // Wait for state update then re-send
    // We need to call sendMessage with the rebuilt state
    const historyUpToUser = messages.slice(0, lastUserIndex);
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: lastUserContent,
      timestamp: Date.now(),
    };

    setMessages([...historyUpToUser, userMessage]);
    setIsLoading(true);

    try {
      const apiMessages = [...historyUpToUser, userMessage].map((m) => ({
        role: m.role,
        content: m.content,
      }));
      const response = await sendChatMessage(apiMessages);
      const assistantContent =
        response.choices[0]?.message?.content ?? "No response received.";
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

  return { messages, isLoading, error, sendMessage, clearMessages, retryLast };
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 5: Add i18n keys - Latvian
**File:** `cms/apps/web/messages/lv.json` (modify)
**Action:** UPDATE

Add a top-level `"chat"` key AFTER the existing `"routes"` key:

```json
"chat": {
  "title": "AI palidziba",
  "placeholder": "Jautajiet par marsrutiem, grafikiem, transportlidzekliem...",
  "send": "Nosutit",
  "clear": "Notirit sarunu",
  "thinking": "Domaju...",
  "error": "Radas kluda. Ludzu, meginiet velreiz.",
  "rateLimitError": "Vaicajumu limits sasniegts. Meginiet velreiz velak.",
  "emptyTitle": "Ka es varu palidzet?",
  "emptyDescription": "Jautajiet par autobusu marsrutiem, kavesanos, vaditaju grafikiem vai transporta operacijam.",
  "suggestion1": "Kuri marsruti sodiena kave?",
  "suggestion2": "Paradiet 22. marsruta grafiku",
  "suggestion3": "Cik autobusu ir aktivie?",
  "suggestion4": "Atrast pieturas netalu no centra",
  "you": "Jus",
  "assistant": "VTV asistents",
  "retry": "Meginat velreiz",
  "copied": "Nokopets",
  "copy": "Kopet"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 6: Add i18n keys - English
**File:** `cms/apps/web/messages/en.json` (modify)
**Action:** UPDATE

Add a top-level `"chat"` key AFTER the existing `"routes"` key:

```json
"chat": {
  "title": "AI Assistant",
  "placeholder": "Ask about routes, schedules, vehicles...",
  "send": "Send",
  "clear": "Clear conversation",
  "thinking": "Thinking...",
  "error": "Something went wrong. Please try again.",
  "rateLimitError": "Query limit reached. Please try again later.",
  "emptyTitle": "How can I help?",
  "emptyDescription": "Ask about bus routes, live delays, driver schedules, or transit operations.",
  "suggestion1": "Which routes are delayed today?",
  "suggestion2": "Show schedule for route 22",
  "suggestion3": "How many buses are active?",
  "suggestion4": "Find stops near the center",
  "you": "You",
  "assistant": "VTV Assistant",
  "retry": "Try again",
  "copied": "Copied",
  "copy": "Copy"
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes

---

### Task 7: Create ChatEmptyState component
**File:** `cms/apps/web/src/components/chat/chat-empty-state.tsx` (create)
**Action:** CREATE

This component shows when there are no messages yet. It displays a title, description, and 4 clickable suggestion chips.

```typescript
"use client";

import { Bot } from "lucide-react";
import { useTranslations } from "next-intl";
import { Button } from "@/components/ui/button";

interface ChatEmptyStateProps {
  onSuggestionClick: (text: string) => void;
}

export function ChatEmptyState({ onSuggestionClick }: ChatEmptyStateProps) {
  const t = useTranslations("chat");

  const suggestions = [
    t("suggestion1"),
    t("suggestion2"),
    t("suggestion3"),
    t("suggestion4"),
  ];

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-(--spacing-lg) px-(--spacing-page) text-center">
      <div className="flex size-16 items-center justify-center rounded-2xl bg-interactive/10">
        <Bot className="size-8 text-interactive" />
      </div>
      <div className="space-y-(--spacing-tight)">
        <h2 className="font-heading text-lg font-semibold text-foreground">
          {t("emptyTitle")}
        </h2>
        <p className="max-w-md text-sm text-foreground-muted">
          {t("emptyDescription")}
        </p>
      </div>
      <div className="flex flex-wrap justify-center gap-(--spacing-sm)">
        {suggestions.map((suggestion) => (
          <Button
            key={suggestion}
            variant="outline"
            size="sm"
            className="cursor-pointer text-sm"
            onClick={() => onSuggestionClick(suggestion)}
          >
            {suggestion}
          </Button>
        ))}
      </div>
    </div>
  );
}
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 8: Create ChatMessageBubble component
**File:** `cms/apps/web/src/components/chat/chat-message-bubble.tsx` (create)
**Action:** CREATE

Renders a single message bubble. User messages are right-aligned with brand color. Assistant messages are left-aligned with surface color.

```typescript
"use client";

import { Bot, Copy, Check, User } from "lucide-react";
import { useState } from "react";
import { useTranslations } from "next-intl";
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
              ? "bg-interactive text-white"
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
            ? "bg-interactive text-white rounded-br-sm"
            : "bg-surface-raised border border-border-subtle text-foreground rounded-bl-sm shadow-(--shadow-sm)"
        )}
      >
        <div className="whitespace-pre-wrap break-words">{message.content}</div>

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
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 9: Create ChatMessageList component
**File:** `cms/apps/web/src/components/chat/chat-message-list.tsx` (create)
**Action:** CREATE

Scrollable container for messages. Auto-scrolls to bottom on new messages. Shows a thinking skeleton while loading. Shows error banner on failure.

```typescript
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
    <ScrollArea className="flex-1">
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
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 10: Create ChatInput component
**File:** `cms/apps/web/src/components/chat/chat-input.tsx` (create)
**Action:** CREATE

Input area with auto-growing textarea and send button. Enter submits, Shift+Enter adds newline.

```typescript
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
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes

---

### Task 11: Create Chat page
**File:** `cms/apps/web/src/app/[locale]/(dashboard)/chat/page.tsx` (create)
**Action:** CREATE

The main chat page component. Client component that composes ChatEmptyState, ChatMessageList, and ChatInput.

```typescript
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
      <div className="flex h-[calc(100vh-var(--spacing-page)*2)] flex-col">
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
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web lint` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 12: Enable chat nav item in sidebar
**File:** `cms/apps/web/src/components/app-sidebar.tsx` (modify)
**Action:** UPDATE

Change line 26 from:
```typescript
  { key: "chat", href: "/chat", enabled: false },
```
to:
```typescript
  { key: "chat", href: "/chat", enabled: true },
```

**Per-task validation:**
- `pnpm --filter @vtv/web type-check` passes
- `pnpm --filter @vtv/web build` passes

---

### Task 13: Mobile viewport adjustment
**Action:** VERIFY

On mobile (< 768px), the layout stacks vertically with a header bar. Verify that the chat page's `h-[calc(100vh-var(--spacing-page)*2)]` works correctly when the mobile header is present. The mobile header in `app-sidebar.tsx` adds approximately 48px of height.

If the chat is clipped on mobile, adjust the page container height calculation to account for the mobile header:
- Mobile: `h-[calc(100vh-4rem)]` (subtracting header height)
- Desktop: `h-[calc(100vh-var(--spacing-page)*2)]`

Use the existing `useIsMobile()` hook if a conditional class is needed. But first test with the current calculation - it may work fine since `<main>` already has `overflow-auto`.

**Per-task validation:**
- `pnpm --filter @vtv/web build` passes
- Visual: Open at `http://localhost:3000/en/chat` and test both mobile and desktop viewports

---

## Final Validation (3-Level Pyramid)

Run each level in order - every one must pass with 0 errors:

**Level 1: TypeScript**
```bash
cd cms && pnpm --filter @vtv/web type-check
```

**Level 2: Lint**
```bash
cd cms && pnpm --filter @vtv/web lint
```

**Level 3: Build**
```bash
cd cms && pnpm --filter @vtv/web build
```

**Success definition:** All 3 levels exit code 0, zero errors.

## Post-Implementation Checks

- [ ] Page renders at `/en/chat` and `/lv/chat`
- [ ] Empty state shows with 4 clickable suggestion chips
- [ ] Clicking a suggestion sends it as a message
- [ ] User messages appear right-aligned with blue background
- [ ] Assistant messages appear left-aligned with surface background
- [ ] Thinking indicator shows while waiting for response
- [ ] Error banner shows on API failure with retry button
- [ ] Clear button removes all messages and resets to empty state
- [ ] Enter sends message, Shift+Enter adds newline
- [ ] Copy button on assistant messages copies text
- [ ] Auto-scroll to bottom on new messages
- [ ] i18n keys present in both lv.json and en.json
- [ ] Sidebar nav link shows "AI Assistant" / "AI palidziba" and highlights when active
- [ ] No hardcoded colors - all styling uses semantic tokens
- [ ] Accessibility: all interactive elements have labels, focus states visible
- [ ] Mobile: full-height layout, input pinned to bottom

## Acceptance Criteria

This feature is complete when:
- [ ] Page accessible at `/{locale}/chat` for admin and dispatcher roles
- [ ] RBAC enforced - editor/viewer redirected to `/unauthorized`
- [ ] Both languages have complete translations (17 keys each)
- [ ] Multi-turn conversation works (agent receives full history)
- [ ] Design system rules followed (MASTER.md tokens and patterns)
- [ ] All validation levels pass (type-check, lint, build)
- [ ] No regressions in existing pages
- [ ] Ready for `/commit`

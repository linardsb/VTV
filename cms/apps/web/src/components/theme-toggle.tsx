"use client";

import { useSyncExternalStore } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon, Monitor } from "lucide-react";
import { useTranslations } from "next-intl";
import { cn } from "@/lib/utils";

const themes = [
  { key: "light", icon: Sun },
  { key: "dark", icon: Moon },
  { key: "system", icon: Monitor },
] as const;

const emptySubscribe = () => () => {};

export function ThemeToggle() {
  // next-themes cannot resolve theme on the server — use useSyncExternalStore
  // to safely detect client rendering without setState-in-useEffect.
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);
  const { theme, setTheme } = useTheme();
  const t = useTranslations("theme");

  return (
    <div
      className="flex items-center gap-(--spacing-tight)"
      role="radiogroup"
      aria-label={t("toggle")}
    >
      {themes.map((item, i) => {
        const Icon = item.icon;
        const isActive = mounted && theme === item.key;

        return (
          <span
            key={item.key}
            className="flex items-center gap-(--spacing-tight)"
          >
            {i > 0 && (
              <span
                className="text-xs text-foreground-muted"
                aria-hidden="true"
              >
                |
              </span>
            )}
            <button
              type="button"
              role="radio"
              aria-checked={isActive}
              aria-label={t(item.key)}
              onClick={() => setTheme(item.key)}
              className={cn(
                "cursor-pointer transition-colors duration-200",
                isActive
                  ? "text-foreground"
                  : "text-foreground-muted hover:text-foreground"
              )}
            >
              <Icon className="size-3.5" />
            </button>
          </span>
        );
      })}
    </div>
  );
}

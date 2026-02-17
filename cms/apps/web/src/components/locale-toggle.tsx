"use client";

import { useCallback } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useLocale } from "next-intl";
import { cn } from "@/lib/utils";

const locales = ["lv", "en"] as const;

function setCookie(name: string, value: string, maxAge: number) {
  document.cookie = `${name}=${value};path=/;max-age=${maxAge}`;
}

export function LocaleToggle() {
  const pathname = usePathname();
  const router = useRouter();
  const currentLocale = useLocale();

  const switchLocale = useCallback(
    (newLocale: string) => {
      if (newLocale === currentLocale) return;

      // Set cookie for next-intl server-side resolution
      setCookie("locale", newLocale, 31536000);

      // Replace locale prefix in current path: /lv/dashboard → /en/dashboard
      const segments = pathname.split("/");
      segments[1] = newLocale;
      const newPath = segments.join("/");

      router.push(newPath);
    },
    [currentLocale, pathname, router]
  );

  return (
    <div
      className="flex items-center gap-(--spacing-tight)"
      role="radiogroup"
      aria-label="Language"
    >
      {locales.map((locale, i) => (
        <span
          key={locale}
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
            aria-checked={locale === currentLocale}
            onClick={() => switchLocale(locale)}
            className={cn(
              "cursor-pointer text-xs font-medium uppercase transition-colors duration-200",
              locale === currentLocale
                ? "font-semibold text-foreground"
                : "text-foreground-muted hover:text-foreground"
            )}
          >
            {locale.toUpperCase()}
          </button>
        </span>
      ))}
    </div>
  );
}

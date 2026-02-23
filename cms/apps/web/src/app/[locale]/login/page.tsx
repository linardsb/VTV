"use client";

import { signIn } from "next-auth/react";
import { useTranslations } from "next-intl";
import { useLocale } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const t = useTranslations("common");
  const locale = useLocale();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await signIn("credentials", {
      email,
      password,
      callbackUrl: `/${locale}`,
    });
  }

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        minHeight: "100vh",
        padding: "1rem",
        backgroundColor: "var(--color-background)",
      }}
    >
      <form
        onSubmit={handleSubmit}
        style={{ width: "100%", maxWidth: "400px" }}
        className="space-y-4"
      >
        <h1 className="font-heading text-2xl font-semibold text-foreground">
          {t("appName")}
        </h1>
        <p className="text-sm text-foreground-muted">
          {t("login")}
        </p>
        <div>
          <label htmlFor="email" className="block text-sm font-medium text-foreground">
            {t("email")}
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ width: "100%", display: "block", padding: "8px 12px", borderRadius: "6px", border: "1px solid var(--color-border)", fontSize: "14px", marginTop: "4px" }}
            required
          />
        </div>
        <div>
          <label htmlFor="password" className="block text-sm font-medium text-foreground">
            {t("password")}
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: "100%", display: "block", padding: "8px 12px", borderRadius: "6px", border: "1px solid var(--color-border)", fontSize: "14px", marginTop: "4px" }}
            required
          />
        </div>
        <Button type="submit" className="w-full cursor-pointer">
          {t("login")}
        </Button>
      </form>
    </div>
  );
}

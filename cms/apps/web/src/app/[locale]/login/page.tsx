"use client";

import { signIn } from "next-auth/react";
import { useTranslations } from "next-intl";
import { useState } from "react";
import { Button } from "@/components/ui/button";

export default function LoginPage() {
  const t = useTranslations("common");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    await signIn("credentials", {
      email,
      password,
      callbackUrl: "/lv",
    });
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <form onSubmit={handleSubmit} className="w-full max-w-sm space-y-4">
        <h1 className="font-heading text-heading font-semibold">
          {t("appName")}
        </h1>
        <div>
          <label htmlFor="email" className="text-sm font-medium">
            Email
          </label>
          <input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="mt-1 block w-full rounded-md border border-border bg-background px-3 py-2"
            required
          />
        </div>
        <div>
          <label htmlFor="password" className="text-sm font-medium">
            Password
          </label>
          <input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="mt-1 block w-full rounded-md border border-border bg-background px-3 py-2"
            required
          />
        </div>
        <Button type="submit" className="w-full">
          {t("login")}
        </Button>
      </form>
    </div>
  );
}

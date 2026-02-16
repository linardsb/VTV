import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";

import lv from "../../messages/lv.json";
import en from "../../messages/en.json";

const locales = ["lv", "en"] as const;
type Locale = (typeof locales)[number];
const defaultLocale: Locale = "lv";

const messagesByLocale: Record<Locale, typeof lv> = { lv, en };

export default getRequestConfig(async () => {
  const store = await cookies();
  const locale = (store.get("locale")?.value ?? defaultLocale) as Locale;

  return {
    locale,
    messages: messagesByLocale[locale],
  };
});

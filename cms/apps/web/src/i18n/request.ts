import { getRequestConfig } from "next-intl/server";
import { cookies } from "next/headers";

import lv from "../../messages/lv.json";
import en from "../../messages/en.json";
import ru from "../../messages/ru.json";

type Locale = "lv" | "en" | "ru";
const defaultLocale: Locale = "lv";

const messagesByLocale: Record<Locale, typeof lv> = { lv, en, ru };

export default getRequestConfig(async () => {
  const store = await cookies();
  const locale = (store.get("locale")?.value ?? defaultLocale) as Locale;

  return {
    locale,
    messages: messagesByLocale[locale],
  };
});

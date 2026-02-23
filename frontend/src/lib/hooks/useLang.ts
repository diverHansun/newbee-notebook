"use client";

import { useContext } from "react";

import { LanguageContext, type Lang } from "@/lib/i18n/language-context";
import type { LocalizedString } from "@/lib/i18n/strings";

type TranslateFn = (text: LocalizedString) => string;
type TranslateInterpolateFn = (text: LocalizedString, vars: Record<string, string | number>) => string;

function interpolate(template: string, vars: Record<string, string | number>): string {
  return Object.entries(vars).reduce((acc, [key, value]) => {
    return acc.replaceAll(`{${key}}`, String(value));
  }, template);
}

export function useLang(): {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: TranslateFn;
  ti: TranslateInterpolateFn;
} {
  const ctx = useContext(LanguageContext);
  const lang = ctx?.lang ?? "zh";
  const setLang = ctx?.setLang ?? (() => {});

  const t: TranslateFn = (text) => (lang === "en" ? text.en : text.zh);
  const ti: TranslateInterpolateFn = (text, vars) => interpolate(t(text), vars);

  return { lang, setLang, t, ti };
}


import i18n from "i18next";
import { initReactI18next } from "react-i18next";
import he from "./locales/he.json";
import en from "./locales/en.json";

function detectLanguage(): string {
  const stored = localStorage.getItem("language");
  if (stored === "he" || stored === "en") return stored;
  try {
    const code = (window as any).Telegram?.WebApp?.initDataUnsafe?.user?.language_code ?? "";
    if (code === "iw" || code.startsWith("he")) return "he";
    if (code.startsWith("en")) return "en";
  } catch {}
  return "he";
}

const lng = detectLanguage();

i18n.use(initReactI18next).init({
  resources: { he: { translation: he }, en: { translation: en } },
  lng,
  fallbackLng: "he",
  interpolation: { escapeValue: false },
});

document.documentElement.lang = lng;
document.documentElement.dir = lng === "he" ? "rtl" : "ltr";

export default i18n;
export function setLanguage(lang: "he" | "en") {
  i18n.changeLanguage(lang);
  localStorage.setItem("language", lang);
  document.documentElement.lang = lang;
  document.documentElement.dir = lang === "he" ? "rtl" : "ltr";
}

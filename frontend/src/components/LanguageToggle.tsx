import { useTranslation } from "react-i18next";
import { setLanguage } from "../i18n";

export default function LanguageToggle() {
  const { i18n } = useTranslation();
  const isHe = i18n.language === "he";
  return (
    <button onClick={() => setLanguage(isHe ? "en" : "he")} className="lang-toggle">
      {isHe ? "EN" : "עב"}
    </button>
  );
}

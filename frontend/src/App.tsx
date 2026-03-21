import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
// setLanguage is used in LanguageToggle component
import "./i18n";
import History from "./pages/History";
import Predictions from "./pages/Predictions";
import Personal from "./pages/Personal";
import Admin from "./pages/Admin";
import LanguageToggle from "./components/LanguageToggle";
import "./App.css";

type Tab = "history" | "predictions" | "personal" | "admin";

export default function App() {
  const { t, i18n } = useTranslation();
  const [tab, setTab] = useState<Tab>("history");
  const [isAdmin, setIsAdmin] = useState(false);

  useEffect(() => {
    (window as any).Telegram?.WebApp?.ready();
    import("./api/client").then(({ api }) => {
      api.get("/api/admin/stats")
        .then(() => setIsAdmin(true))
        .catch(() => setIsAdmin(false));
    });
  }, []);

  return (
    <div className="app">
      <header className="app-header">
        <h1>🚨 {i18n.language === "he" ? "פיקוד העורף" : "Pikud HaOref"}</h1>
        <LanguageToggle />
      </header>
      <nav className="tab-bar">
        {(["history", "predictions", "personal"] as Tab[]).map((t_) => (
          <button key={t_} onClick={() => setTab(t_)} className={tab === t_ ? "active" : ""}>
            {t(`nav.${t_}`)}
          </button>
        ))}
        {isAdmin && (
          <button onClick={() => setTab("admin")} className={tab === "admin" ? "active" : ""}>
            {t("nav.admin")}
          </button>
        )}
      </nav>
      <main>
        {tab === "history" && <History />}
        {tab === "predictions" && <Predictions />}
        {tab === "personal" && <Personal />}
        {tab === "admin" && isAdmin && <Admin />}
      </main>
    </div>
  );
}

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

export default function LiveBanner() {
  const { t } = useTranslation();
  const [alert, setAlert] = useState<any>(null);

  useEffect(() => {
    const poll = async () => {
      try {
        const { data } = await api.get("/api/alerts/live");
        setAlert(data);
      } catch {}
    };
    poll();
    const id = setInterval(poll, 3000);
    return () => clearInterval(id);
  }, []);

  if (!alert) return null;
  return (
    <div className="live-banner">
      🚨 <strong>{t("history.live")}:</strong> {alert.areas?.join(", ")}
    </div>
  );
}

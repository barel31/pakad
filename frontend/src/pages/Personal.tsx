import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

export default function Personal() {
  const { t } = useTranslation();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/analytics/personal")
      .then(({ data }) => setData(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>{t("common.loading")}</p>;
  if (!data || data.error) return <p>{t("common.error")}</p>;

  return (
    <div className="page">
      <h2>{t("personal.title")}</h2>
      <div className="stat-card">
        <div className="stat-label">{t("personal.totalAlerts")}</div>
        <div className="stat-value">{data.total_alerts}</div>
      </div>
      <div className="stat-card">
        <div className="stat-label">{t("personal.matchedAlerts")}</div>
        <div className="stat-value">{data.matched_alerts}</div>
      </div>
      <div className="filters-list">
        <h3>{t("personal.filters")}</h3>
        {data.filters.length === 0
          ? <p>{t("common.noData")}</p>
          : data.filters.map((f: string) => <div key={f} className="filter-chip">• {f}</div>)
        }
      </div>
      <div className="sub-history">
        <h3>{t("personal.subscriptionHistory")}</h3>
        {data.subscription_history.map((e: any, i: number) => (
          <div key={i} className="event-row">
            {e.event === "subscribed" ? "✅" : "❌"} {new Date(e.occurred_at).toLocaleDateString()}
          </div>
        ))}
      </div>
    </div>
  );
}

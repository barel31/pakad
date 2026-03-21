import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import EmptyState from "../components/EmptyState";

export default function Predictions() {
  const { t } = useTranslation();
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.get("/api/predictions")
      .then(({ data }) => setData(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p>{t("common.loading")}</p>;
  if (!data || data.insufficient_data) {
    return <EmptyState message={t("predictions.insufficientData", { min: data?.minimum ?? 10 })} />;
  }

  return (
    <div className="page">
      <h2>{t("predictions.title")}</h2>
      {data.peak_hour && (
        <div className="stat-card">
          <div className="stat-label">{t("predictions.peakHour")}</div>
          <div className="stat-value">{data.peak_hour.hour}:00</div>
        </div>
      )}
      {data.peak_day && (
        <div className="stat-card">
          <div className="stat-label">{t("predictions.peakDay")}</div>
          <div className="stat-value">{data.peak_day.day_name}</div>
        </div>
      )}
      {data.most_targeted_area && (
        <div className="stat-card">
          <div className="stat-label">{t("predictions.mostTargeted")}</div>
          <div className="stat-value">{data.most_targeted_area.area}</div>
        </div>
      )}
    </div>
  );
}

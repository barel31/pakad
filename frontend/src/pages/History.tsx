import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";
import AlertCard from "../components/AlertCard";
import LiveBanner from "../components/LiveBanner";
import EmptyState from "../components/EmptyState";

export default function History() {
  const { t } = useTranslation();
  const [alerts, setAlerts] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  useEffect(() => {
    setLoading(true);
    api.get("/api/alerts", { params: { page } })
      .then(({ data }) => setAlerts(data))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [page]);

  return (
    <div className="page">
      <h2>{t("history.title")}</h2>
      <LiveBanner />
      {loading && <p>{t("common.loading")}</p>}
      {!loading && alerts.length === 0 && <EmptyState message={t("history.noAlerts")} />}
      {alerts.map((a) => (
        <AlertCard key={a.id} {...a} />
      ))}
      <div className="pagination">
        <button disabled={page === 1} onClick={() => setPage(p => p - 1)}>←</button>
        <span>{page}</span>
        <button disabled={alerts.length < 50} onClick={() => setPage(p => p + 1)}>→</button>
      </div>
    </div>
  );
}

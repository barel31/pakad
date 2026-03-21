import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { api } from "../api/client";

type AdminTab = "dashboard" | "subscribers" | "broadcast" | "settings" | "admins";

export default function Admin() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<AdminTab>("dashboard");
  return (
    <div className="page admin-page">
      <h2>{t("admin.title")}</h2>
      <nav className="admin-tabs">
        {(["dashboard", "subscribers", "broadcast", "settings", "admins"] as AdminTab[]).map(tab_ => (
          <button key={tab_} onClick={() => setTab(tab_)} className={tab === tab_ ? "active" : ""}>
            {t(`admin.${tab_}`)}
          </button>
        ))}
      </nav>
      {tab === "dashboard" && <AdminDashboard />}
      {tab === "subscribers" && <AdminSubscribers />}
      {tab === "broadcast" && <AdminBroadcast />}
      {tab === "settings" && <AdminSettings />}
      {tab === "admins" && <AdminAdmins />}
    </div>
  );
}

function AdminDashboard() {
  const [stats, setStats] = useState<any>(null);
  useEffect(() => {
    api.get("/api/admin/stats").then(({ data }) => setStats(data)).catch(() => {});
  }, []);
  if (!stats) return <p>Loading...</p>;
  return (
    <div className="dashboard">
      <div className="stat-card">Active: {stats.subscribers.active}</div>
      <div className="stat-card">Blocked: {stats.subscribers.blocked}</div>
      <div className="stat-card">Alerts today: {stats.alerts_today}</div>
      <div className="stat-card">Bot: {stats.bot_enabled ? "🟢 ON" : "🔴 OFF"}</div>
      <div className="stat-card">Poll interval: {stats.poll_interval_seconds}s</div>
    </div>
  );
}

function AdminSubscribers() {
  const [subs, setSubs] = useState<any[]>([]);
  useEffect(() => { api.get("/api/admin/subscribers").then(({ data }) => setSubs(data)); }, []);
  const block = (id: number) => api.post(`/api/admin/subscribers/${id}/block`).then(() => setSubs(s => s.map(x => x.chat_id === id ? {...x, blocked: true} : x)));
  const unblock = (id: number) => api.post(`/api/admin/subscribers/${id}/unblock`).then(() => setSubs(s => s.map(x => x.chat_id === id ? {...x, blocked: false} : x)));
  return (
    <div>
      {subs.map(s => (
        <div key={s.chat_id} className="subscriber-row">
          <span>{s.chat_id}</span>
          <span>{s.language}</span>
          <button onClick={() => s.blocked ? unblock(s.chat_id) : block(s.chat_id)}>
            {s.blocked ? "Unblock" : "Block"}
          </button>
        </div>
      ))}
    </div>
  );
}

function AdminBroadcast() {
  const [msg, setMsg] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [sent, setSent] = useState<number | null>(null);
  const send = () => {
    api.post("/api/admin/broadcast", { message: msg })
      .then(({ data }) => { setSent(data.recipients); setConfirm(false); setMsg(""); })
      .catch(() => {});
  };
  return (
    <div>
      <textarea value={msg} onChange={e => setMsg(e.target.value)} maxLength={4096} rows={5} style={{width:"100%"}} />
      <p>{msg.length}/4096</p>
      {!confirm && <button onClick={() => setConfirm(true)} disabled={!msg}>Send</button>}
      {confirm && (
        <div>
          <p>Send to all active subscribers?</p>
          <button onClick={send}>Confirm</button>
          <button onClick={() => setConfirm(false)}>Cancel</button>
        </div>
      )}
      {sent !== null && <p>Sent to {sent} subscribers</p>}
    </div>
  );
}

function AdminSettings() {
  const [settings, setSettings] = useState<any>(null);
  useEffect(() => { api.get("/api/admin/settings").then(({ data }) => setSettings(data)); }, []);
  if (!settings) return <p>Loading...</p>;
  const save = () => api.put("/api/admin/settings", settings).catch(() => {});
  return (
    <div>
      <label>Poll interval (1.0–10.0s):
        <input type="number" min={1} max={10} step={0.5}
          value={settings.poll_interval_seconds}
          onChange={e => setSettings({ ...settings, poll_interval_seconds: parseFloat(e.target.value) })} />
      </label>
      <label>Bot enabled:
        <input type="checkbox" checked={settings.bot_enabled}
          onChange={e => setSettings({ ...settings, bot_enabled: e.target.checked })} />
      </label>
      <button onClick={save}>Save</button>
    </div>
  );
}

function AdminAdmins() {
  const [admins, setAdmins] = useState<any[]>([]);
  const [newId, setNewId] = useState("");
  useEffect(() => { api.get("/api/admin/admins").then(({ data }) => setAdmins(data)); }, []);
  const add = () => api.post("/api/admin/admins", { chat_id: parseInt(newId) }).then(() => { setNewId(""); api.get("/api/admin/admins").then(({ data }) => setAdmins(data)); });
  const remove = (id: number) => api.delete(`/api/admin/admins/${id}`).then(() => setAdmins(a => a.filter(x => x.chat_id !== id)));
  return (
    <div>
      {admins.map(a => (
        <div key={a.chat_id} className="admin-row">
          <span>{a.chat_id}</span>
          <button onClick={() => remove(a.chat_id)}>Remove</button>
        </div>
      ))}
      <input value={newId} onChange={e => setNewId(e.target.value)} placeholder="Telegram user ID" />
      <button onClick={add} disabled={!newId}>Add Admin</button>
    </div>
  );
}

import axios from "axios";

const BASE_URL = (import.meta as any).env?.VITE_API_URL ?? "";

function getInitData(): string {
  return (window as any).Telegram?.WebApp?.initData ?? "";
}

export const api = axios.create({ baseURL: BASE_URL });

api.interceptors.request.use((config) => {
  const initData = getInitData();
  if (initData) {
    config.headers.Authorization = `tma ${initData}`;
  }
  config.headers["ngrok-skip-browser-warning"] = "true";
  return config;
});

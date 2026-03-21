import "@testing-library/jest-dom";
(window as any).Telegram = {
  WebApp: {
    ready: () => {},
    initData: "",
    initDataUnsafe: { user: { id: 1, language_code: "en" } },
  },
};

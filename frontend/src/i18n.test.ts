import { describe, it, expect } from "vitest";
import i18n from "./i18n";

describe("i18n", () => {
  it("has Hebrew translations", () => {
    i18n.changeLanguage("he");
    expect(i18n.t("nav.history")).toBe("היסטוריה");
  });
  it("has English translations", () => {
    i18n.changeLanguage("en");
    expect(i18n.t("nav.history")).toBe("History");
  });
});

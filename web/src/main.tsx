import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { flightdeckMarkUrl } from "./branding";
import "./index.css";
import { applyDocumentTheme, readStoredThemePreference, resolveEffectiveTheme } from "./themeStorage";

function syncFaviconLinks(mark: string) {
  for (const rel of ["icon", "apple-touch-icon"] as const) {
    let el = document.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
    if (!el) {
      el = document.createElement("link");
      el.rel = rel;
      document.head.appendChild(el);
    }
    el.href = mark;
    if (rel === "icon") {
      el.type = "image/png";
    }
  }
}

syncFaviconLinks(flightdeckMarkUrl);
applyDocumentTheme(resolveEffectiveTheme(readStoredThemePreference()));

const el = document.getElementById("root");
if (!el) {
  throw new Error("Missing #root");
}

createRoot(el).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

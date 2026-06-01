import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ThemePreferenceProvider } from "./context/ThemePreferenceContext";
import { UI_READ_ONLY } from "./uiConfig";
import { OverviewPage } from "./pages/OverviewPage";
import { DiffPage } from "./pages/DiffPage";
import { RunsPage } from "./pages/RunsPage";
import { ActionsPage } from "./pages/ActionsPage";

export function App() {
  return (
    <ThemePreferenceProvider>
      <HashRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<OverviewPage />} />
            <Route path="diff" element={<DiffPage />} />
            <Route path="runs" element={<RunsPage />} />
            <Route path="settings" element={<Navigate to="/" replace />} />
            <Route path="actions" element={UI_READ_ONLY ? <Navigate to="/" replace /> : <ActionsPage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </HashRouter>
    </ThemePreferenceProvider>
  );
}

import { HashRouter, Navigate, Route, Routes } from "react-router-dom";
import { AppShell } from "./components/AppShell";
import { ActionsPage } from "./pages/ActionsPage";
import { DiffPage } from "./pages/DiffPage";
import { OverviewPage } from "./pages/OverviewPage";

export function App() {
  return (
    <HashRouter>
      <Routes>
        <Route element={<AppShell />}>
          <Route index element={<OverviewPage />} />
          <Route path="diff" element={<DiffPage />} />
          <Route path="actions" element={<ActionsPage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </HashRouter>
  );
}

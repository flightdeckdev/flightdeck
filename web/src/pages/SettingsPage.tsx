import { ThemeToggle } from "../components/ThemeToggle";

export function SettingsPage() {
  return (
    <>
      <header className="fd-page-head">
        <div>
          <h2 className="fd-page-title fd-page-title--brand">Settings</h2>
          <p className="fd-page-sub fd-page-sub--tight">
            <strong>What changed?</strong> Theme preference only for now. <strong>Is it safe?</strong> Stored locally in this
            browser. <strong>Can I ship?</strong> Unrelated to promotion — use <strong>Actions</strong> for ledger writes.
          </p>
          <p className="fd-page-sub fd-page-sub--meta">Appearance and workspace preferences (more options later).</p>
        </div>
      </header>

      <section className="fd-card" aria-labelledby="settings-color-h">
        <div className="fd-card__head">
          <h3 className="fd-card__title" id="settings-color-h">
            Color theme
          </h3>
          <p className="fd-card__desc">Light, dark, or match the OS. Saved in this browser only.</p>
        </div>
        <div className="fd-settings-appearance">
          <ThemeToggle variant="settings" />
        </div>
      </section>
    </>
  );
}

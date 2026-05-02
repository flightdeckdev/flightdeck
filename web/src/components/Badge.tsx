type Tone = "pass" | "fail" | "neutral";

const toneClass: Record<Tone, string> = {
  pass: "fd-badge fd-badge--pass",
  fail: "fd-badge fd-badge--fail",
  neutral: "fd-badge fd-badge--neutral",
};

export function Badge({ tone, children }: { tone: Tone; children: string }) {
  return <span className={toneClass[tone]}>{children}</span>;
}

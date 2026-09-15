const TONES: Record<string, string> = {
  muted: "bg-slate-400",
  amber: "bg-amber-500",
  green: "bg-emerald-500",
};

export default function StatusBadge({
  label,
  tone = "muted",
  title,
}: {
  label: string;
  tone?: "muted" | "amber" | "green";
  title?: string;
}) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-white px-2.5 py-1 text-xs font-medium text-slate-600"
      title={title}
    >
      <span
        aria-hidden="true"
        className={`h-1.5 w-1.5 rounded-full ${TONES[tone]}`}
      />
      {label}
    </span>
  );
}

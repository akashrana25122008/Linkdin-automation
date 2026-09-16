import { useEffect, useMemo, useState } from "react";
import { Link, useBlocker } from "react-router-dom";
import {
  CONTENT_TYPE_LABELS,
  fetchStrategy,
  saveStrategy,
  type ContentType,
  type Strategy,
} from "../api";
import { COMMON_TIMEZONES, browserTimeZone } from "../time";

function isSessionError(err: unknown): boolean {
  return err instanceof Error && err.message.startsWith("Session expired");
}

const DETAIL_MESSAGES: Record<string, string> = {
  invalid_timezone: "That timezone is not recognized.",
  invalid_frequency: "Choose a valid posting frequency.",
  invalid_day: "Posting days contain an invalid value.",
  invalid_time: "Preferred times must look like 09:00.",
  invalid_content_type: "A selected content type is not supported.",
};

const DAYS = [
  { value: "mon", label: "Mon" },
  { value: "tue", label: "Tue" },
  { value: "wed", label: "Wed" },
  { value: "thu", label: "Thu" },
  { value: "fri", label: "Fri" },
  { value: "sat", label: "Sat" },
  { value: "sun", label: "Sun" },
];

const FREQUENCIES = [
  { value: "", label: "Not set" },
  { value: "daily", label: "Daily" },
  { value: "3x_week", label: "3 times a week" },
  { value: "weekly", label: "Weekly" },
  { value: "2x_month", label: "2 times a month" },
  { value: "custom", label: "Custom" },
];

const SECTIONS = [
  { id: "profile", label: "Profile" },
  { id: "identity", label: "Identity" },
  { id: "audience", label: "Audience" },
  { id: "topics", label: "Topics" },
  { id: "writing", label: "Writing" },
  { id: "publishing", label: "Publishing" },
];

const inputClass =
  "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition-colors placeholder:text-slate-400 hover:border-slate-300 focus:border-slate-400";

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <section id={id} aria-label={title} className="scroll-mt-20">
      <h2 className="text-[13px] font-semibold tracking-wide text-slate-500 uppercase">
        {title}
      </h2>
      <p className="mt-0.5 text-[13px] text-slate-400">{description}</p>
      <div className="mt-3 flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4">
        {children}
      </div>
    </section>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label
        htmlFor={htmlFor}
        className="mb-1 block text-xs font-medium text-slate-600"
      >
        {label}
      </label>
      {children}
    </div>
  );
}

function ChipInput({
  id,
  label,
  values,
  onChange,
  placeholder,
  type = "text",
}: {
  id: string;
  label: string;
  values: string[];
  onChange: (next: string[]) => void;
  placeholder: string;
  type?: string;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const value = draft.trim();
    if (!value || values.includes(value)) {
      setDraft("");
      return;
    }
    onChange([...values, value]);
    setDraft("");
  };
  return (
    <div>
      <label
        htmlFor={id}
        className="mb-1 block text-xs font-medium text-slate-600"
      >
        {label}
      </label>
      {values.length > 0 && (
        <ul className="mb-2 flex flex-wrap gap-1.5" aria-label={`${label} added`}>
          {values.map((value) => (
            <li
              key={value}
              className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-50 py-1 pr-1.5 pl-3 text-xs text-slate-700"
            >
              {value}
              <button
                type="button"
                onClick={() => onChange(values.filter((v) => v !== value))}
                aria-label={`Remove ${value}`}
                className="rounded-full px-1 text-slate-400 transition-colors hover:bg-slate-200 hover:text-slate-700"
              >
                ×
              </button>
            </li>
          ))}
        </ul>
      )}
      <div className="flex gap-2">
        <input
          id={id}
          type={type}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              add();
            }
          }}
          placeholder={placeholder}
          maxLength={120}
          className={`${inputClass} min-w-0 flex-1`}
        />
        <button
          type="button"
          onClick={add}
          disabled={!draft.trim()}
          className="shrink-0 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 disabled:opacity-50"
        >
          Add
        </button>
      </div>
    </div>
  );
}

const EMPTY: Strategy = {
  display_name: "",
  headline: "",
  bio: "",
  skills: [],
  projects: [],
  technologies: [],
  interests: [],
  target_audience: "",
  professional_goals: [],
  content_goals: [],
  preferred_topics: [],
  forbidden_topics: [],
  writing_style: "",
  content_types: [],
  posting_frequency: "",
  preferred_days: [],
  preferred_times: [],
  timezone: "",
};

export default function StrategyPage() {
  const [form, setForm] = useState<Strategy>(EMPTY);
  const [snapshot, setSnapshot] = useState("");
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedNote, setSavedNote] = useState(false);
  const [isFirstTime, setIsFirstTime] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);

  const fingerprint = useMemo(() => JSON.stringify(form), [form]);
  const dirty = fingerprint !== snapshot;

  useBlocker(
    ({ currentLocation, nextLocation }) =>
      dirty && currentLocation.pathname !== nextLocation.pathname,
  );

  useEffect(() => {
    if (!dirty) return;
    const onUnload = (e: BeforeUnloadEvent) => e.preventDefault();
    window.addEventListener("beforeunload", onUnload);
    return () => window.removeEventListener("beforeunload", onUnload);
  }, [dirty]);

  useEffect(() => {
    const controller = new AbortController();
    fetchStrategy()
      .then((data) => {
        setForm({ ...EMPTY, ...data });
        setSnapshot(JSON.stringify({ ...EMPTY, ...data }));
        setIsFirstTime(
          Object.values(data).every((v) =>
            Array.isArray(v) ? v.length === 0 : v === "",
          ),
        );
      })
      .catch((err: unknown) => {
        if ((err as Error).name === "AbortError") return;
        if (isSessionError(err)) setSessionExpired(true);
        else setLoadError(err instanceof Error ? err.message : "Failed to load");
      })
      .finally(() => setLoading(false));
    return () => controller.abort();
  }, []);

  const set = <K extends keyof Strategy>(key: K, value: Strategy[K]) => {
    setForm((f) => ({ ...f, [key]: value }));
    setSavedNote(false);
  };

  const toggleDay = (day: string) =>
    set(
      "preferred_days",
      form.preferred_days.includes(day)
        ? form.preferred_days.filter((d) => d !== day)
        : [...form.preferred_days, day],
    );

  const toggleContentType = (ct: string) =>
    set(
      "content_types",
      form.content_types.includes(ct)
        ? form.content_types.filter((c) => c !== ct)
        : [...form.content_types, ct],
    );

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await saveStrategy(form);
      setForm(saved);
      setSnapshot(JSON.stringify(saved));
      setIsFirstTime(false);
      setSavedNote(true);
    } catch (err) {
      if (isSessionError(err)) setSessionExpired(true);
      else {
        const code = err instanceof Error ? err.message : "";
        setSaveError(DETAIL_MESSAGES[code] ?? code ?? "Save failed.");
      }
    } finally {
      setSaving(false);
    }
  };

  const browserTz = browserTimeZone();
  const tzOptions = COMMON_TIMEZONES.includes(browserTz)
    ? COMMON_TIMEZONES
    : [browserTz, ...COMMON_TIMEZONES];

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-3xl" role="status" aria-label="Loading strategy">
        <div className="skeleton h-7 w-56 rounded-lg" />
        <div className="skeleton mt-4 h-48 rounded-xl" />
        <div className="skeleton mt-4 h-48 rounded-xl" />
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="mx-auto w-full max-w-xl" role="alert">
        <h1 className="text-xl font-semibold tracking-tight">Strategy</h1>
        <p className="mt-4 text-sm text-red-600">
          Couldn&apos;t load your strategy: {loadError}
        </p>
        <button
          onClick={() => window.location.reload()}
          className="mt-4 rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700"
        >
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-3xl">
      {sessionExpired && (
        <p className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700" role="alert">
          Session expired —{" "}
          <Link to="/login" className="font-medium underline">
            please log in again
          </Link>
          .
        </p>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm text-slate-500">
            Define the context your AI uses to build your personal brand.
          </p>
        </div>
        <span aria-live="polite" className="text-xs text-slate-500">
          {saving ? "Saving…" : savedNote ? "Strategy saved" : dirty ? "Unsaved changes" : ""}
        </span>
        <button
          onClick={() => void save()}
          disabled={!dirty || saving}
          className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>

      {isFirstTime && (
        <div className="mt-4 rounded-xl border border-slate-200 bg-white px-5 py-4">
          <p className="text-sm font-medium text-slate-800">Set up your personal brand</p>
          <p className="mt-1 text-[13px] text-slate-500">
            Fill in what you can — every field is optional. Saved strategy
            becomes the user-scoped context future AI features will use.
          </p>
        </div>
      )}

      <nav aria-label="Strategy sections" className="mt-4 flex flex-wrap gap-1.5">
        {SECTIONS.map((s) => (
          <a
            key={s.id}
            href={`#${s.id}`}
            className="rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 transition-colors hover:border-slate-300 hover:text-slate-900"
          >
            {s.label}
          </a>
        ))}
      </nav>

      {saveError && (
        <p className="mt-4 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700" role="alert">
          {saveError}
        </p>
      )}

      <div className="mt-6 flex flex-col gap-8">
        <Section id="profile" title="Personal Profile" description="How you are represented professionally. Separate from your Google sign-in identity.">
          <Field label="Name" htmlFor="strat-name">
            <input id="strat-name" value={form.display_name} onChange={(e) => set("display_name", e.target.value)} placeholder="Your professional name" maxLength={255} className={inputClass} />
          </Field>
          <Field label="Headline" htmlFor="strat-headline">
            <input id="strat-headline" value={form.headline} onChange={(e) => set("headline", e.target.value)} placeholder="Backend engineer · AI practitioner" maxLength={255} className={inputClass} />
          </Field>
          <Field label="About / Bio" htmlFor="strat-bio">
            <textarea id="strat-bio" value={form.bio} onChange={(e) => set("bio", e.target.value)} placeholder="A few sentences about your work and interests…" rows={4} maxLength={2000} className={`${inputClass} resize-y`} />
          </Field>
        </Section>

        <Section id="identity" title="Professional Identity" description="Skills, projects, and technologies the AI should know about.">
          <ChipInput id="strat-skills" label="Skills" values={form.skills} onChange={(v) => set("skills", v)} placeholder="Add a skill, e.g. Python" />
          <ChipInput id="strat-projects" label="Projects" values={form.projects} onChange={(v) => set("projects", v)} placeholder="Add a project, e.g. LinkedIn AI" />
          <ChipInput id="strat-tech" label="Technologies" values={form.technologies} onChange={(v) => set("technologies", v)} placeholder="Add a technology, e.g. FastAPI" />
          <ChipInput id="strat-interests" label="Interests" values={form.interests} onChange={(v) => set("interests", v)} placeholder="Add an interest, e.g. Developer Tools" />
        </Section>

        <Section id="audience" title="Audience & Goals" description="Who you want to reach and what you want to achieve.">
          <Field label="Target audience" htmlFor="strat-audience">
            <input id="strat-audience" value={form.target_audience} onChange={(e) => set("target_audience", e.target.value)} placeholder="software developers, students learning AI…" maxLength={2000} className={inputClass} />
          </Field>
          <ChipInput id="strat-pgoals" label="Professional goals" values={form.professional_goals} onChange={(v) => set("professional_goals", v)} placeholder="Add a goal, e.g. build technical credibility" />
          <ChipInput id="strat-cgoals" label="Content goals" values={form.content_goals} onChange={(v) => set("content_goals", v)} placeholder="Add a goal, e.g. educate" />
        </Section>

        <Section id="topics" title="Topics" description="What the AI should talk about — and avoid.">
          <ChipInput id="strat-preferred" label="Preferred topics" values={form.preferred_topics} onChange={(v) => set("preferred_topics", v)} placeholder="Add a topic, e.g. APIs" />
          <ChipInput id="strat-forbidden" label="Forbidden topics" values={form.forbidden_topics} onChange={(v) => set("forbidden_topics", v)} placeholder="Add a topic to avoid, e.g. politics" />
        </Section>

        <Section id="writing" title="Writing Style" description="How your content should sound. Free-form beats presets.">
          <Field label="Writing style description" htmlFor="strat-style">
            <textarea id="strat-style" value={form.writing_style} onChange={(e) => set("writing_style", e.target.value)} placeholder="Explain technical concepts clearly, use practical examples, avoid corporate buzzwords…" rows={4} maxLength={2000} className={`${inputClass} resize-y`} />
          </Field>
          <div>
            <span className="mb-1.5 block text-xs font-medium text-slate-600" id="strat-ctypes-label">
              Preferred content types
            </span>
            <div className="flex flex-wrap gap-1.5" role="group" aria-labelledby="strat-ctypes-label">
              {(Object.keys(CONTENT_TYPE_LABELS) as ContentType[]).map((ct) => {
                const on = form.content_types.includes(ct);
                return (
                  <button
                    key={ct}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleContentType(ct)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                      on
                        ? "border-slate-900 bg-slate-900 text-white"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
                    }`}
                  >
                    {CONTENT_TYPE_LABELS[ct]}
                  </button>
                );
              })}
            </div>
          </div>
        </Section>

        <Section id="publishing" title="Publishing Preferences" description="When you prefer to publish. Nothing is scheduled automatically.">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field label="Posting frequency" htmlFor="strat-freq">
              <select id="strat-freq" value={form.posting_frequency} onChange={(e) => set("posting_frequency", e.target.value)} className={inputClass}>
                {FREQUENCIES.map((f) => (
                  <option key={f.value} value={f.value}>
                    {f.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Timezone" htmlFor="strat-tz">
              <select id="strat-tz" value={form.timezone} onChange={(e) => set("timezone", e.target.value)} className={inputClass}>
                <option value="">Not set</option>
                {tzOptions.map((z) => (
                  <option key={z} value={z}>
                    {z}
                    {z === browserTz ? " (browser)" : ""}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <div>
            <span className="mb-1.5 block text-xs font-medium text-slate-600" id="strat-days-label">
              Preferred days
            </span>
            <div className="flex flex-wrap gap-1.5" role="group" aria-labelledby="strat-days-label">
              {DAYS.map((d) => {
                const on = form.preferred_days.includes(d.value);
                return (
                  <button
                    key={d.value}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggleDay(d.value)}
                    className={`w-11 rounded-lg border py-1.5 text-xs font-medium transition-colors ${
                      on
                        ? "border-slate-900 bg-slate-900 text-white"
                        : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:text-slate-900"
                    }`}
                  >
                    {d.label}
                  </button>
                );
              })}
            </div>
          </div>
          <ChipInput id="strat-times" label="Preferred times" values={form.preferred_times} onChange={(v) => set("preferred_times", v)} placeholder="Add a time, e.g. 09:00" type="time" />
        </Section>
      </div>

      <div className="mt-8 flex items-center gap-3 border-t border-slate-200 pt-4">
        <span aria-live="polite" className="text-xs text-slate-500">
          {saving ? "Saving…" : savedNote ? "Strategy saved" : dirty ? "Unsaved changes" : "All changes saved"}
        </span>
        <button
          onClick={() => void save()}
          disabled={!dirty || saving}
          className="ml-auto rounded-lg bg-slate-900 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          {saving ? "Saving…" : "Save changes"}
        </button>
      </div>
    </div>
  );
}

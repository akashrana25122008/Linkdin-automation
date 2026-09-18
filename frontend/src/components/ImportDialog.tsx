import { useEffect, useRef, useState } from "react";
import {
  fetchImportArticle,
  fetchImportRepo,
  fetchStrategy,
  fetchVideoStatus,
  saveStrategy,
  uploadImportFile,
  uploadVideo,
  type ImportArticle,
  type ImportRepo,
  type ImportUpload,
  type VideoStatus,
  type VideoUpload,
} from "../api";

export interface ImportResult {
  topic: string;
  notes: string;
  body?: string;
  title?: string;
}

type SourceId =
  | "scratch"
  | "thought"
  | "achievement"
  | "certificate"
  | "screenshot"
  | "resume"
  | "article"
  | "github"
  | "voice"
  | "video";

const SOURCES: { id: SourceId; label: string; hint: string }[] = [
  { id: "scratch", label: "Blank post", hint: "Start from an empty editor" },
  { id: "thought", label: "Rough thought", hint: "Polish messy notes" },
  { id: "achievement", label: "Achievement", hint: "Structured win â†’ post" },
  { id: "certificate", label: "Certificate", hint: "Image, PDF, or document" },
  { id: "screenshot", label: "Screenshot", hint: "Project image + context" },
  { id: "resume", label: "Resume", hint: "Fill your brand profile" },
  { id: "article", label: "Article / URL", hint: "React with your own angle" },
  { id: "github", label: "GitHub repo", hint: "Showcase verified facts" },
  { id: "voice", label: "Voice note", hint: "Speak, then polish" },
  { id: "video", label: "Video", hint: "Transcribe & post" },
];

const inputClass =
  "w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-900 outline-none transition-colors placeholder:text-slate-400 hover:border-slate-300 focus:border-slate-400 disabled:cursor-not-allowed disabled:bg-slate-50 disabled:text-slate-400";

const btnPrimary =
  "rounded-lg bg-slate-900 px-3.5 py-2 text-sm font-medium text-white transition-colors hover:bg-slate-700 active:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300";

const btnSecondary =
  "rounded-lg border border-slate-200 bg-white px-3.5 py-2 text-sm font-medium text-slate-700 transition-colors hover:border-slate-300 hover:bg-slate-50 active:bg-slate-100 disabled:cursor-not-allowed disabled:opacity-50";

const MAX_CLIENT_BYTES = 5 * 1024 * 1024;

function ErrorNote({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700" role="alert">
      {message}
    </p>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
    </label>
  );
}

interface SpeechRecognitionLike {
  start: () => void;
  stop: () => void;
  onresult: ((event: { results: ArrayLike<ArrayLike<{ transcript: string }>> }) => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
  onend: (() => void) | null;
}

function getSpeechRecognition(): (new () => SpeechRecognitionLike) | null {
  const w = window as unknown as Record<string, unknown>;
  const ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  return typeof ctor === "function" ? (ctor as new () => SpeechRecognitionLike) : null;
}

export default function ImportDialog({
  onClose,
  onApply,
}: {
  onClose: () => void;
  onApply: (result: ImportResult) => void;
}) {
  const [source, setSource] = useState<SourceId>("thought");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  const fail = (err: unknown, fallback: string) => {
    if (err === null || err === undefined) {
      setError(null);
      return;
    }
    setError(err instanceof Error ? err.message : fallback);
    setBusy(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <button
        aria-label="Close import dialog"
        className="absolute inset-0 cursor-default bg-slate-900/20"
        onClick={onClose}
      />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Create post from source"
        className="float-enter relative flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-xl"
      >
        <div className="border-b border-slate-100 px-5 py-4">
          <h2 className="text-base font-semibold tracking-tight">Create post</h2>
          <p className="mt-0.5 text-[13px] text-slate-500">
            Start from anything you already have. Only confirmed facts are used.
          </p>
        </div>
        <div className="grid shrink-0 grid-cols-3 gap-1.5 overflow-x-auto border-b border-slate-100 p-3 sm:grid-cols-5">
          {SOURCES.map((s) => (
            <button
              key={s.id}
              onClick={() => {
                setSource(s.id);
                setError(null);
              }}
              aria-pressed={source === s.id}
              title={s.hint}
              className={`rounded-lg border px-2 py-2 text-left transition-colors ${
                source === s.id
                  ? "border-slate-900 bg-slate-900 text-white"
                  : "border-slate-200 bg-white text-slate-600 hover:border-slate-300 hover:bg-slate-50"
              }`}
            >
              <span className="block text-xs font-medium">{s.label}</span>
              <span className={`mt-0.5 hidden truncate text-[11px] sm:block ${source === s.id ? "text-slate-300" : "text-slate-400"}`}>
                {s.hint}
              </span>
            </button>
          ))}
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto p-5">
          <ErrorNote message={error} />
          <div className={error ? "mt-4" : ""}>
            {source === "scratch" && (
              <ScratchBody onApply={onApply} />
            )}
            {source === "thought" && (
              <ThoughtBody busy={busy} setBusy={setBusy} onError={(e) => fail(e, "Could not use these notes.")} onApply={onApply} />
            )}
            {source === "achievement" && (
              <AchievementBody onApply={onApply} />
            )}
            {(source === "certificate" || source === "screenshot") && (
              <FileBody
                kind={source}
                busy={busy}
                setBusy={setBusy}
                onError={(e) => fail(e, "Upload failed.")}
                onApply={onApply}
              />
            )}
            {source === "resume" && (
              <ResumeBody
                busy={busy}
                setBusy={setBusy}
                onError={(e) => fail(e, "Resume import failed.")}
                onClose={onClose}
              />
            )}
            {source === "article" && (
              <ArticleBody
                busy={busy}
                setBusy={setBusy}
                onError={(e) => fail(e, "Article fetch failed.")}
                onApply={onApply}
              />
            )}
            {source === "github" && (
              <GithubBody
                busy={busy}
                setBusy={setBusy}
                onError={(e) => fail(e, "GitHub lookup failed.")}
                onApply={onApply}
              />
            )}
            {source === "voice" && (
              <VoiceBody onApply={onApply} />
            )}
            {source === "video" && (
              <VideoBody
                busy={busy}
                setBusy={setBusy}
                onError={(e) => fail(e, "Video processing failed.")}
                onApply={onApply}
              />
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

function ScratchBody({ onApply }: { onApply: (r: ImportResult) => void }) {
  return (
    <div className="text-center">
      <p className="text-sm text-slate-600">A blank editor with your usual topic, type, and notes fields.</p>
      <button onClick={() => onApply({ topic: "", notes: "" })} className={`${btnSecondary} mt-4`}>
        Open blank editor
      </button>
    </div>
  );
}

function ThoughtBody({
  busy,
  setBusy,
  onError,
  onApply,
}: {
  busy: boolean;
  setBusy: (b: boolean) => void;
  onError: (e: unknown) => void;
  onApply: (r: ImportResult) => void;
}) {
  const [text, setText] = useState("");
  return (
    <div className="flex flex-col gap-3">
      <Field label="Rough thought">
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder={"I worked on OAuth today.\nState handling finally made senseâ€¦"}
          rows={5}
          className={`${inputClass} resize-y`}
        />
      </Field>
      <p className="text-xs text-slate-400">
        Your wording is preserved as context. Nothing is added â€” no metrics, dates, or results.
      </p>
      <div>
        <button
          disabled={!text.trim() || busy}
          onClick={() => {
            try {
              setBusy(true);
              onApply({ topic: "", notes: text.trim() });
            } catch (err) {
              onError(err);
            } finally {
              setBusy(false);
            }
          }}
          className={btnPrimary}
        >
          Use as writing context
        </button>
      </div>
    </div>
  );
}

function AchievementBody({ onApply }: { onApply: (r: ImportResult) => void }) {
  const [what, setWhat] = useState("");
  const [achieved, setAchieved] = useState("");
  const [context, setContext] = useState("");
  const [result, setResult] = useState("");
  const [lesson, setLesson] = useState("");
  const ready = what.trim().length > 0;
  return (
    <div className="flex flex-col gap-3">
      <Field label="What happened?">
        <input value={what} onChange={(e) => setWhat(e.target.value)} placeholder="e.g. Shipped our onboarding checklist" className={inputClass} />
      </Field>
      <Field label="What did you achieve? (only what actually happened)">
        <input value={achieved} onChange={(e) => setAchieved(e.target.value)} placeholder="e.g. Cut setup time for new teammates" className={inputClass} />
      </Field>
      <Field label="Context (optional)">
        <input value={context} onChange={(e) => setContext(e.target.value)} placeholder="e.g. Solo project over two weekends" className={inputClass} />
      </Field>
      <Field label="Result (optional, only real outcomes)">
        <input value={result} onChange={(e) => setResult(e.target.value)} placeholder="e.g. Support tickets dropped" className={inputClass} />
      </Field>
      <Field label="Lesson (optional)">
        <input value={lesson} onChange={(e) => setLesson(e.target.value)} placeholder="e.g. Small checklists beat big docs" className={inputClass} />
      </Field>
      <div>
        <button
          disabled={!ready}
          onClick={() =>
            onApply({
              topic: what.trim(),
              notes: [
                achieved.trim() && `Achievement: ${achieved.trim()}`,
                context.trim() && `Context: ${context.trim()}`,
                result.trim() && `Result: ${result.trim()}`,
                lesson.trim() && `Lesson: ${lesson.trim()}`,
              ]
                .filter(Boolean)
                .join("\n"),
            })
          }
          className={btnPrimary}
        >
          Use in Studio
        </button>
      </div>
    </div>
  );
}

function FileBody({
  kind,
  busy,
  setBusy,
  onError,
  onApply,
}: {
  kind: "certificate" | "screenshot";
  busy: boolean;
  setBusy: (b: boolean) => void;
  onError: (e: unknown) => void;
  onApply: (r: ImportResult) => void;
}) {
  const [upload, setUpload] = useState<ImportUpload | null>(null);
  const [facts, setFacts] = useState("");
  const [topic, setTopic] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  const accept = kind === "certificate" ? ".png,.jpg,.jpeg,.webp,.gif,.pdf,.docx,.txt,.md" : ".png,.jpg,.jpeg,.webp,.gif";

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_CLIENT_BYTES) {
      onError(new Error("That file is larger than 5 MB."));
      return;
    }
    setBusy(true);
    try {
      const result = await uploadImportFile(file);
      setUpload(result);
      setFacts(result.text);
      onError(null);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <input
        ref={fileRef}
        type="file"
        accept={accept}
        aria-label={kind === "certificate" ? "Certificate file" : "Screenshot file"}
        disabled={busy}
        onChange={(e) => void handleFile(e.target.files?.[0])}
        className="text-sm text-slate-600 file:mr-3 file:rounded-lg file:border file:border-slate-200 file:bg-white file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-slate-700 hover:file:bg-slate-50"
      />
      {busy && (
        <p className="text-[13px] text-slate-500" role="status">Reading fileâ€¦</p>
      )}
      {upload && (
        <>
          <p className="text-xs text-slate-500">
            {upload.filename} Â· {(upload.size / 1024).toFixed(1)} KB Â· {upload.mime}
            {upload.truncated ? " Â· truncated" : ""}
          </p>
          {upload.needs_user_input ? (
            <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
              {upload.note} Describe exactly what is shown â€” nothing is assumed.
            </p>
          ) : (
            <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs leading-relaxed text-slate-500">
              {upload.note}
            </p>
          )}
          <Field label={upload.needs_user_input ? "Confirmed facts (required)" : "Confirmed facts (edit freely)"}>
            <textarea
              value={facts}
              onChange={(e) => setFacts(e.target.value)}
              placeholder="Only facts you can verify from the fileâ€¦"
              rows={5}
              className={`${inputClass} resize-y`}
            />
          </Field>
          <Field label="Suggested topic (optional)">
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Earning my cloud certification"
              className={inputClass}
            />
          </Field>
          <div>
            <button
              disabled={!facts.trim()}
              onClick={() => onApply({ topic: topic.trim(), notes: facts.trim() })}
              className={btnPrimary}
            >
              Use in Studio
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function ResumeBody({
  busy,
  setBusy,
  onError,
  onClose,
}: {
  busy: boolean;
  setBusy: (b: boolean) => void;
  onError: (e: unknown) => void;
  onClose: () => void;
}) {
  const [upload, setUpload] = useState<ImportUpload | null>(null);
  const [name, setName] = useState("");
  const [headline, setHeadline] = useState("");
  const [bio, setBio] = useState("");
  const [skills, setSkills] = useState("");
  const [saved, setSaved] = useState(false);

  const suggestFromText = (text: string) => {
    const lines = text.split("\n").map((l) => l.trim()).filter(Boolean);
    if (lines.length > 0 && !name) setName(lines[0].slice(0, 120));
    const skillLine = lines.find((l) => /skills|technologies|stack|tools/i.test(l));
    if (skillLine && !skills) {
      const items = skillLine
        .split(/[:|â€¢Â·,]/)
        .map((s) => s.trim())
        .filter((s) => s && !/skills|technologies|stack|tools/i.test(s))
        .slice(0, 12);
      if (items.length > 0) setSkills(items.join(", "));
    }
  };

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > MAX_CLIENT_BYTES) {
      onError(new Error("That file is larger than 5 MB."));
      return;
    }
    setBusy(true);
    setSaved(false);
    try {
      const result = await uploadImportFile(file);
      if (result.needs_user_input) {
        onError(new Error("Resume images cannot be read. Use a PDF, DOCX, TXT, or Markdown resume."));
        return;
      }
      setUpload(result);
      onError(null);
      suggestFromText(result.text);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  };

  const saveProfile = async () => {
    setBusy(true);
    try {
      const current = await fetchStrategy();
      const listOf = (s: string) =>
        s.split(",").map((x) => x.trim()).filter(Boolean).slice(0, 30);
      await saveStrategy({
        ...current,
        display_name: name.trim() || current.display_name,
        headline: headline.trim() || current.headline,
        bio: bio.trim() || current.bio,
        skills: skills.trim() ? listOf(skills) : current.skills,
      });
      setSaved(true);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <input
        type="file"
        accept=".pdf,.docx,.txt,.md"
        aria-label="Resume file"
        disabled={busy}
        onChange={(e) => void handleFile(e.target.files?.[0])}
        className="text-sm text-slate-600 file:mr-3 file:rounded-lg file:border file:border-slate-200 file:bg-white file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-slate-700 hover:file:bg-slate-50"
      />
      {busy && (
        <p className="text-[13px] text-slate-500" role="status">Reading resumeâ€¦</p>
      )}
      {upload && (
        <>
          <p className="text-xs text-slate-500">
            Extracted {upload.text.length.toLocaleString()} characters
            {upload.truncated ? " (truncated)" : ""} from {upload.filename}.
            Confirm every field â€” nothing is saved until you approve.
          </p>
          <Field label="Name">
            <input value={name} onChange={(e) => setName(e.target.value)} className={inputClass} maxLength={120} />
          </Field>
          <Field label="Headline">
            <input value={headline} onChange={(e) => setHeadline(e.target.value)} placeholder="e.g. Backend engineer" className={inputClass} maxLength={160} />
          </Field>
          <Field label="About">
            <textarea value={bio} onChange={(e) => setBio(e.target.value)} rows={3} className={`${inputClass} resize-y`} maxLength={2000} />
          </Field>
          <Field label="Skills (comma separated)">
            <input value={skills} onChange={(e) => setSkills(e.target.value)} placeholder="Python, FastAPI, â€¦" className={inputClass} />
          </Field>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => void saveProfile()} disabled={busy} className={btnPrimary}>
              {saved ? "Saved to profile" : "Save to profile"}
            </button>
            <button onClick={onClose} className={btnSecondary}>
              Done
            </button>
          </div>
          {saved && (
            <p className="text-xs text-emerald-700" role="status">
              Profile updated. Only the confirmed fields above were saved.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function ArticleBody({
  busy,
  setBusy,
  onError,
  onApply,
}: {
  busy: boolean;
  setBusy: (b: boolean) => void;
  onError: (e: unknown) => void;
  onApply: (r: ImportResult) => void;
}) {
  const [url, setUrl] = useState("");
  const [article, setArticle] = useState<ImportArticle | null>(null);
  const [topic, setTopic] = useState("");

  const fetchIt = async () => {
    if (!url.trim()) return;
    setBusy(true);
    try {
      const result = await fetchImportArticle(url.trim());
      setArticle(result);
      onError(null);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void fetchIt();
          }}
          placeholder="https://example.com/article"
          aria-label="Article URL"
          inputMode="url"
          className={`${inputClass} min-w-0 flex-1`}
        />
        <button onClick={() => void fetchIt()} disabled={!url.trim() || busy} className={btnPrimary}>
          {busy ? "Fetchingâ€¦" : "Fetch"}
        </button>
      </div>
      {article && (
        <>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
            <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">
              Source Â· {article.host}
            </p>
            {article.title && (
              <p className="mt-1 text-sm font-medium text-slate-900">{article.title}</p>
            )}
            {article.description && (
              <p className="mt-1 text-[13px] text-slate-600">{article.description}</p>
            )}
            {article.excerpts.slice(0, 2).map((ex, i) => (
              <p key={i} className="mt-1.5 line-clamp-3 text-[13px] leading-relaxed text-slate-500">
                {ex}
              </p>
            ))}
            <a
              href={article.url}
              target="_blank"
              rel="noreferrer"
              className="mt-1.5 inline-block text-xs font-medium text-slate-700 underline underline-offset-2 hover:text-slate-900"
            >
              View source
            </a>
          </div>
          <Field label="Your angle (required â€” commentary must be yours)">
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Why this matters for backend teams"
              className={inputClass}
            />
          </Field>
          <div>
            <button
              disabled={!topic.trim()}
              onClick={() =>
                onApply({
                  topic: topic.trim(),
                  notes: [
                    `Source: ${article.title || article.host} (${article.url})`,
                    ...article.excerpts.slice(0, 3),
                  ].join("\n"),
                })
              }
              className={btnPrimary}
            >
              Use as context
            </button>
          </div>
          <p className="text-xs text-slate-400">
            Source facts stay attributed. Your post must add an original angle â€” never present source text as your experience.
          </p>
        </>
      )}
    </div>
  );
}

function GithubBody({
  busy,
  setBusy,
  onError,
  onApply,
}: {
  busy: boolean;
  setBusy: (b: boolean) => void;
  onError: (e: unknown) => void;
  onApply: (r: ImportResult) => void;
}) {
  const [url, setUrl] = useState("");
  const [repo, setRepo] = useState<ImportRepo | null>(null);
  const [topic, setTopic] = useState("");

  const fetchIt = async () => {
    if (!url.trim()) return;
    setBusy(true);
    try {
      const result = await fetchImportRepo(url.trim());
      setRepo(result);
      onError(null);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div className="flex gap-2">
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void fetchIt();
          }}
          placeholder="https://github.com/owner/repo"
          aria-label="GitHub repository URL"
          inputMode="url"
          className={`${inputClass} min-w-0 flex-1`}
        />
        <button onClick={() => void fetchIt()} disabled={!url.trim() || busy} className={btnPrimary}>
          {busy ? "Loadingâ€¦" : "Inspect"}
        </button>
      </div>
      {repo && (
        <>
          <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2.5">
            <p className="text-sm font-medium text-slate-900">{repo.full_name}</p>
            {repo.description && (
              <p className="mt-1 text-[13px] text-slate-600">{repo.description}</p>
            )}
            <p className="mt-1.5 text-xs text-slate-500">
              {[repo.language, repo.license, `${repo.stars} stars`].filter(Boolean).join(" Â· ")}
              {repo.topics.length > 0 && ` Â· ${repo.topics.slice(0, 5).join(", ")}`}
            </p>
            <p className="mt-1 text-[11px] text-slate-400">Verified via the GitHub API â€” only shown facts will be used.</p>
          </div>
          <Field label="Post focus (optional)">
            <input
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Lessons from building this in public"
              className={inputClass}
            />
          </Field>
          <div>
            <button
              onClick={() =>
                onApply({
                  topic: topic.trim() || `Showcasing ${repo.full_name}`,
                  notes: [
                    `Project: ${repo.full_name}`,
                    repo.description && `About: ${repo.description}`,
                    repo.language && `Main language: ${repo.language}`,
                    repo.readme_excerpt && `README excerpt: ${repo.readme_excerpt.slice(0, 600)}`,
                  ]
                    .filter(Boolean)
                    .join("\n"),
                })
              }
              className={btnPrimary}
            >
              Use in Studio
            </button>
          </div>
        </>
      )}
    </div>
  );
}

function VoiceBody({ onApply }: { onApply: (r: ImportResult) => void }) {
  const [supported] = useState(() => getSpeechRecognition() !== null);
  const [listening, setListening] = useState(false);
  const [transcript, setTranscript] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recRef = useRef<SpeechRecognitionLike | null>(null);

  useEffect(() => {
    return () => {
      try {
        recRef.current?.stop();
      } catch {
        /* already stopped */
      }
    };
  }, []);

  if (!supported) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 px-5 py-8 text-center">
        <p className="text-sm font-medium text-slate-700">Voice input isn&apos;t supported here</p>
        <p className="mx-auto mt-1 max-w-sm text-[13px] text-slate-500">
          This browser has no built-in speech recognition. Type your thought
          instead â€” nothing is recorded or uploaded.
        </p>
      </div>
    );
  }

  const toggle = () => {
    if (listening) {
      try {
        recRef.current?.stop();
      } finally {
        setListening(false);
      }
      return;
    }
    const Ctor = getSpeechRecognition();
    if (!Ctor) return;
    const rec = new Ctor();
    recRef.current = rec;
    setError(null);
    rec.onresult = (event) => {
      let text = "";
      for (let i = 0; i < event.results.length; i++) {
        const alt = event.results[i]?.[0];
        if (alt) text += alt.transcript;
      }
      setTranscript((prev) => (prev ? `${prev} ${text}` : text).trim());
    };
    rec.onerror = (event) => {
      setError(
        event.error === "not-allowed"
          ? "Microphone access was blocked. Allow it in the browser to continue."
          : "Voice capture failed. Type your thought instead.",
      );
      setListening(false);
    };
    rec.onend = () => setListening(false);
    try {
      rec.start();
      setListening(true);
    } catch {
      setError("Voice capture failed. Type your thought instead.");
    }
  };

  return (
    <div className="flex flex-col gap-3">
      <div>
        <button onClick={toggle} className={listening ? btnSecondary : btnPrimary} aria-pressed={listening}>
          {listening ? "Stop recording" : "Start recording"}
        </button>
      </div>
      {listening && (
        <p className="text-[13px] text-slate-500" role="status">Listeningâ€¦ speak naturally.</p>
      )}
      {error && (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-[13px] text-red-700" role="alert">
          {error}
        </p>
      )}
      <Field label="Transcript (edit before using)">
        <textarea
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          placeholder="Your words will appear here for reviewâ€¦"
          rows={5}
          className={`${inputClass} resize-y`}
        />
      </Field>
      <div>
        <button
          disabled={!transcript.trim()}
          onClick={() => onApply({ topic: "", notes: transcript.trim() })}
          className={btnPrimary}
        >
          Use transcript as context
        </button>
      </div>
      <p className="text-xs text-slate-400">
        Transcription runs in your browser. Nothing is published automatically.
      </p>
    </div>
  );
}

function VideoBody({
  busy,
  setBusy,
  onError,
  onApply,
}: {
  busy: boolean;
  setBusy: (b: boolean) => void;
  onError: (e: unknown) => void;
  onApply: (r: ImportResult) => void;
}) {
  const [status, setStatus] = useState<VideoStatus | null>(null);
  const [result, setResult] = useState<VideoUpload | null>(null);
  const [confirmed, setConfirmed] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchVideoStatus()
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    if (file.size > 50 * 1024 * 1024) {
      onError(new Error("That video is larger than 50 MB."));
      return;
    }
    setBusy(true);
    try {
      const uploaded = await uploadVideo(file);
      setResult(uploaded);
      setConfirmed(uploaded.transcript);
      onError(null);
    } catch (err) {
      onError(err);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-3">
      {status && !status.real_transcription_available && (
        <p className="rounded-lg bg-amber-50 px-3 py-2 text-xs leading-relaxed text-amber-800">
          Server transcription isn&apos;t configured â€” you&apos;ll get a
          clearly-labeled development transcript for UI testing.
        </p>
      )}
      <input
        ref={fileRef}
        type="file"
        accept=".mp4,.webm,.mov"
        aria-label="Video file"
        disabled={busy}
        onChange={(e) => void handleFile(e.target.files?.[0])}
        className="text-sm text-slate-600 file:mr-3 file:rounded-lg file:border file:border-slate-200 file:bg-white file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-slate-700 hover:file:bg-slate-50"
      />
      {busy && (
        <p className="text-[13px] text-slate-500" role="status">
          Processing videoâ€¦ transcription can take a minute.
        </p>
      )}
      {result && (
        <>
          <p className="text-xs text-slate-500">
            {result.filename} Â· {(result.size / 1048576).toFixed(1)} MB Â·{" "}
            {result.duration_seconds}s
            {result.transcript_mock && (
              <span className="ml-2 rounded border border-amber-200 bg-amber-50 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-amber-700">
                MOCK TRANSCRIPT
              </span>
            )}
          </p>
          <p className="text-xs text-slate-400">{result.transcript_note}</p>
          {result.key_points.length > 0 && (
            <div className="rounded-lg bg-slate-50 px-3 py-2.5">
              <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">
                Key points (heuristic)
              </p>
              <ul className="mt-1 flex list-disc flex-col gap-1 pl-4 text-[13px] text-slate-600">
                {result.key_points.map((point, i) => (
                  <li key={i}>{point}</li>
                ))}
              </ul>
            </div>
          )}
          <Field label="Transcript â€” confirm or edit before using">
            <textarea
              value={confirmed}
              onChange={(e) => setConfirmed(e.target.value)}
              rows={6}
              className={`${inputClass} resize-y`}
            />
          </Field>
          <div>
            <button
              disabled={!confirmed.trim()}
              onClick={() =>
                onApply({
                  topic: "",
                  notes: `Video transcript (confirmed by me):\n${confirmed.trim()}`,
                })
              }
              className={btnPrimary}
            >
              Use transcript as context
            </button>
          </div>
          <p className="text-xs text-slate-400">
            Only the confirmed transcript above is used â€” nothing is invented
            from the video, and nothing is published automatically.
          </p>
        </>
      )}
    </div>
  );
}

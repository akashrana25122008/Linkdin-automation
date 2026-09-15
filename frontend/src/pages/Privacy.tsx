import { Link } from "react-router-dom";

export default function Privacy() {
  return (
    <div className="mx-auto max-w-xl p-8">
      <h1 className="text-xl font-semibold tracking-tight">Privacy</h1>
      <p className="mt-4 text-sm leading-relaxed text-slate-600">
        Your profile, content, and integrations are stored only to operate
        your workspace and are never shared between users. Authentication uses
        a secure HTTP-only session cookie; no credentials or tokens are kept
        in browser storage.
      </p>
      <p className="mt-3 text-sm leading-relaxed text-slate-600">
        Google sign-in shares your name, email address, and profile picture
        with this application so it can identify your account.
      </p>
      <Link to="/login" className="mt-6 inline-block text-sm underline">
        Back to login
      </Link>
    </div>
  );
}

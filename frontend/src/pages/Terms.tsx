import { Link } from "react-router-dom";

export default function Terms() {
  return (
    <div className="mx-auto max-w-xl p-8">
      <h1 className="text-xl font-semibold tracking-tight">Terms</h1>
      <p className="mt-4 text-sm leading-relaxed text-slate-600">
        LinkedIn AI is a personal content workspace. You own your content:
        nothing is published to LinkedIn without your explicit approval, and
        AI-generated suggestions must be reviewed before use.
      </p>
      <p className="mt-3 text-sm leading-relaxed text-slate-600">
        Sign-in is provided by Google. By using this application you agree to
        use it only for lawful, professional purposes.
      </p>
      <Link to="/login" className="mt-6 inline-block text-sm underline">
        Back to login
      </Link>
    </div>
  );
}

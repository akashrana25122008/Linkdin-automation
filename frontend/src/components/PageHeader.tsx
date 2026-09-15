export default function PageHeader({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="mb-6">
      <h1 className="text-xl font-semibold tracking-tight text-slate-900">
        {title}
      </h1>
      <p className="mt-1 text-sm text-slate-500">{description}</p>
    </div>
  );
}

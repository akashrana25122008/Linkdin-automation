import PageHeader from "./PageHeader";

export default function ComingSoon({
  title,
  description,
  milestone,
}: {
  title: string;
  description: string;
  milestone: string;
}) {
  return (
    <div className="mx-auto max-w-xl py-16 text-center">
      <PageHeader title={title} description={description} />
      <div className="mx-auto mt-2 max-w-sm rounded-xl border border-dashed border-slate-300 bg-white px-6 py-8">
        <p className="text-sm font-medium text-slate-700">
          Coming in {milestone}
        </p>
        <p className="mt-1 text-sm text-slate-500">
          This workspace area is not built yet. Nothing here is functional —
          check back when the milestone lands.
        </p>
      </div>
    </div>
  );
}

import { clsx } from "clsx";
export function Card({ className, children }: { className?: string; children: React.ReactNode }) {
  return <section className={clsx("rounded-2xl border border-line bg-white p-5 md:p-6", className)}>{children}</section>;
}
export function PageTitle({ title, description }: { title: string; description: string }) {
  return <div className="page-heading"><span className="page-heading-eyebrow">让每一步更清楚</span><h1>{title}</h1><p>{description}</p></div>;
}
export function PrimaryButton({ children, className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={clsx("primary-button inline-flex items-center justify-center gap-2 rounded-xl bg-accent px-4 py-2.5 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50", className)} {...props}>{children}</button>;
}
export function GhostButton({ children, className, ...props }: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={clsx("w-full rounded-xl border border-line bg-white px-3 py-2.5 text-left text-sm text-slate-700 transition hover:border-teal-300 hover:bg-teal-50", className)} {...props}>{children}</button>;
}

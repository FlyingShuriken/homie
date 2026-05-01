import { cn } from "@/lib/utils";

export function Progress({
  value,
  className,
}: {
  value: number;
  className?: string;
}) {
  return (
    <div
      className={cn(
        "h-3 w-full overflow-hidden rounded-full bg-stone-200",
        className,
      )}
    >
      <div
        className="h-full rounded-full bg-orange-500 transition-all duration-500 ease-out"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

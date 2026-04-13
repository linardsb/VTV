interface ChartCardProps {
  title: string;
  currentValue?: string;
  children: React.ReactNode;
}

export function ChartCard({ title, currentValue, children }: ChartCardProps) {
  return (
    <div className="border border-card-border bg-card-bg p-(--spacing-card)">
      <div className="mb-(--spacing-card) flex items-start justify-between">
        <p className="text-xs font-medium uppercase tracking-wide text-foreground-muted">
          {title}
        </p>
        {currentValue && (
          <p className="font-heading text-lg font-semibold text-foreground">
            {currentValue}
          </p>
        )}
      </div>
      <div className="h-[220px]">{children}</div>
    </div>
  );
}

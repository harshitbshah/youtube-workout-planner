interface BadgeProps {
  label: string;
  className?: string;
}

export default function Badge({ label, className = "bg-zinc-800 border border-zinc-700 text-zinc-400" }: BadgeProps) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${className}`}>
      {label}
    </span>
  );
}

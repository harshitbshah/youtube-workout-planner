type TooltipProps = {
  text: string;
  children: React.ReactNode;
  position?: "top" | "bottom";
};

export function Tooltip({ text, children, position = "top" }: TooltipProps) {
  const posClass = position === "top"
    ? "bottom-full left-1/2 -translate-x-1/2 mb-1.5"
    : "top-full left-1/2 -translate-x-1/2 mt-1.5";

  return (
    <span className="relative group/tip inline-flex">
      {children}
      <span
        className={`pointer-events-none absolute ${posClass} w-max max-w-[220px] rounded-md border border-zinc-200 dark:border-zinc-700/60 bg-white dark:bg-zinc-900 px-2 py-1 text-[11px] leading-snug text-zinc-600 dark:text-zinc-400 opacity-0 shadow-md transition-opacity delay-300 group-hover/tip:opacity-100 z-50 whitespace-normal`}
      >
        {text}
      </span>
    </span>
  );
}

type TooltipProps = {
  text: string;
  children: React.ReactNode;
  position?: "top" | "bottom";
};

export function Tooltip({ text, children, position = "top" }: TooltipProps) {
  const posClass = position === "top"
    ? "bottom-full left-1/2 -translate-x-1/2 mb-2"
    : "top-full left-1/2 -translate-x-1/2 mt-2";

  return (
    <span className="relative group/tip inline-flex">
      {children}
      <span
        className={`pointer-events-none absolute ${posClass} w-max max-w-xs rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-1.5 text-xs text-zinc-300 opacity-0 shadow-lg transition-opacity group-hover/tip:opacity-100 z-50 text-center whitespace-normal`}
      >
        {text}
      </span>
    </span>
  );
}

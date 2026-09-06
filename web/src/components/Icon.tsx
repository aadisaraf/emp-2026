import type { SVGProps } from "react";

/* Line icons, one stroke weight, drawn here so nothing is fetched. */

const PATHS: Record<string, string> = {
  home: "M3 10.5 12 3l9 7.5M5 9.5V21h5v-6h4v6h5V9.5",
  sheet: "M8 6h13M8 12h13M8 18h13M3 6h.01M3 12h.01M3 18h.01",
  history: "M3 12a9 9 0 1 0 3-6.7M3 4v5h5M12 7v5l3 2",
  impact: "M12 2v20M17 6.5c0-1.9-2.2-3-5-3s-5 1.1-5 3 2.2 3 5 3 5 1.1 5 3-2.2 3-5 3-5-1.1-5-3",
  search: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14Zm9 16-4-4",
  plus: "M12 5v14M5 12h14",
  back: "M15 5l-7 7 7 7",
  print: "M6 9V3h12v6M6 18H4V9h16v9h-2M6 14h12v7H6z",
  refresh: "M20 12a8 8 0 1 1-2.3-5.7M20 4v5h-5",
  close: "M6 6l12 12M18 6 6 18",
  check: "M5 12.5 10 17.5 19 7",
  clock: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18Zm0 4v5l3 2",
  more: "M6 12h.01M12 12h.01M18 12h.01",
  open: "M7 17 17 7M9 7h8v8",
  flag: "M5 21V4h11l-1.5 3.5L16 11H5",
};

export interface IconProps extends SVGProps<SVGSVGElement> {
  name: keyof typeof PATHS | string;
  size?: number;
}

export function Icon({ name, size = 18, ...rest }: IconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d={PATHS[name] ?? ""} />
    </svg>
  );
}

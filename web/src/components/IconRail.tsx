"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Icon } from "./Icon";
import { cx } from "@/lib/cx";
import styles from "./IconRail.module.css";

/* Four places to go, as icons. Sources and adding inventory are one press away
   in the bar above; the artifacts live on Today as documents. */
const ITEMS = [
  { href: "/", label: "Today", icon: "home" },
  { href: "/sheet", label: "Pull sheet", icon: "sheet" },
  { href: "/runs", label: "Run history", icon: "history" },
  { href: "/impact", label: "Impact", icon: "impact" },
] as const;

function isActive(pathname: string, href: string): boolean {
  if (href === "/") return pathname === "/";
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function IconRail() {
  const pathname = usePathname();
  return (
    <nav className={cx(styles.rail, "no-print")} aria-label="Sections">
      <ul className={styles.list}>
        {ITEMS.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                className={cx(styles.item, active && styles.active)}
                aria-label={item.label}
                title={item.label}
                aria-current={active ? "page" : undefined}
              >
                <Icon name={item.icon} />
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ARTIFACTS_LABEL, ARTIFACT_NAV, PRIMARY_NAV, isActive, type NavItem } from "@/lib/nav";
import { cx } from "@/lib/cx";
import styles from "./SideNav.module.css";

export interface SideNavProps {
  /**
    The state report is a USDA child-nutrition artifact and exists only where
    the location runs a meal program.
  */
  servesMealProgram: boolean;
}

/**
  One flat vertical list of the routes that exist. No icons, no accordions, no
  collapse toggle, and no locations item.
*/
export function SideNav({ servesMealProgram }: SideNavProps) {
  const pathname = usePathname();
  const artifacts = ARTIFACT_NAV.filter(
    (item) => !item.mealProgramOnly || servesMealProgram,
  );

  const link = (item: NavItem) => {
    const active = isActive(pathname, item.href);
    return (
      <li key={item.href}>
        <Link
          href={item.href}
          className={cx(styles.item, active && styles.active)}
          aria-current={active ? "page" : undefined}
        >
          {item.label}
        </Link>
      </li>
    );
  };

  return (
    <nav className={styles.nav} data-role="nav" aria-label="Sections">
      <ul>{PRIMARY_NAV.map(link)}</ul>
      <p className={styles.group}>{ARTIFACTS_LABEL}</p>
      <ul>{artifacts.map(link)}</ul>
    </nav>
  );
}

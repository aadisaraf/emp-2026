"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ARTIFACTS_LABEL, ARTIFACT_NAV, PRIMARY_NAV, isActive } from "@/lib/nav";
import { cx } from "@/lib/cx";
import styles from "./SideNav.module.css";

export interface SideNavProps {
  /**
   * The state report is a USDA child-nutrition artifact and exists only where
   * the location runs a meal program. Defaults to showing it: a route that
   * answers 404 not_a_meal_program is honest, an invisible one is not.
   */
  servesMealProgram?: boolean;
}

/**
 * One flat vertical list of the routes that exist. No icons, no accordions, no
 * collapse toggle, and no locations item.
 *
 * The active row carries a 3px left marker, which is the one place in this
 * design a coloured left strip is allowed: on a nav item it marks position,
 * not status, and status strips are what the tell is about.
 */
export function SideNav({ servesMealProgram = true }: SideNavProps) {
  const pathname = usePathname();
  const artifacts = ARTIFACT_NAV.filter(
    (item) => !item.mealProgramOnly || servesMealProgram,
  );

  return (
    <nav className={styles.nav} data-role="nav" aria-label="Sections">
      <ul>
        {PRIMARY_NAV.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={cx(styles.item, isActive(pathname, item.href) && styles.active)}
              aria-current={isActive(pathname, item.href) ? "page" : undefined}
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
      <p className={styles.group}>{ARTIFACTS_LABEL}</p>
      <ul>
        {artifacts.map((item) => (
          <li key={item.href}>
            <Link
              href={item.href}
              className={cx(styles.item, isActive(pathname, item.href) && styles.active)}
              aria-current={isActive(pathname, item.href) ? "page" : undefined}
            >
              {item.label}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}

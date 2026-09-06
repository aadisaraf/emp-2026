# PullSheet Dashboard — Committed Visual Direction (web-v2)

**Aesthetic: instrument / print-ledger.** Not "dashboard product".
Anti-slop is achieved by *deliberate variation*, never decoration.
Every visual task in waves 1–6 reads this file first.

## Levers (the only ones that move dogwater → instrument)

1. **Hierarchy by scale, then weight, then rules.** Size jump (11→13→15→20)
   is the strongest signal; weight-strong and rules come second.
2. **Border-weight hierarchy.** Hairline (1px `--border-hairline`) for row
   rules and inner hairlines; `--border` for panel edges/column rules;
   `--border-strong` for section boundaries. Rules, not boxes — panels are
   bordered sections, never shadowed cards. No card grid of three, no
   colored left-stripes.
3. **Alignment is the ornament.** `tabular-nums` on every numeric column,
   right-aligned measures, mono identifiers left-aligned, uppercase tracked
   11px labels on a shared baseline.
4. **Color as signal ink only.** Green chrome (masthead, active nav, primary
   CTA, focus ring) exactly as today; red = action, ochre = unresolved,
   neutral = recorded. One accent per surface at most.
5. **Microcopy and states.** Hover = invert/type-only change; every
   interactive element keeps a visible `:focus-visible` ring; no motion
   beyond the existing 100ms row hover.

## Per-surface anatomy goals

- **Masthead:** solid tokens only (no opacity); brand baseline, fact/rule
  separators as fixed border tokens; flattens to a rule in print.
- **StatRail:** label/value on one baseline, clocks aligned, hairline
  separators; total chrome (masthead + rail) must leave ≥25 sheet rows at
  1440×900.
- **SideNav:** group labels, item inset/active-marker grammar, hover fill;
  44px targets on the ≤720px horizontal strip.
- **PageHeader:** title/context baseline, action slot alignment.
- **Panel:** border + heading band anatomy (rules, not boxes).
- **DataTable header:** micro labels on baseline, sort mark inline, sticky
  header keeps its single permitted hairline shadow; 28px rows hold.
- **Buttons/CTA:** two grammars only — primary (green-800 fill) and
  secondary (1px `--border`, `surface-page` bg). The `/` secondary CTA and
  `/ingest` action link are the proof surfaces.
- **Chips:** PULL = filled `--alert-fill` with white label
  (`print-color-adjust: exact`); HELD = hollow `--attend-outline`.
  Tier stays uncoloured. Fill vs outline must survive grayscale + mono print.
- **Statements/counts rail:** status word in `--fs-page`, reason in
  secondary, stale gains `--attend-tint` + age; numbers tabular.

## Anti-slop gate (enforced by `node scripts/check-styles.mjs`)

No translucency/opacity, no glow, no glass, no centered marketing hero, no
decorative numbers, no cream/serif/sage substitutions, no gradient (besides
the documented `RunDayStrip` hatch), no emoji, no one-treatment-fits-all
rows, no new hue/size/weight/font/radius role, no web fonts, no new
dependencies. The two documented exceptions stay exactly as-is:
`RunDayStrip` hatch and the `DataTable` sticky-header hairline shadow.

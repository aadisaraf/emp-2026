/**
 * The `?run=` query parameter the three artifact endpoints accept.
 *
 * Absent means the latest ok run, which is what somebody who clicked the nav
 * item wants. A present but unreadable value is deliberately passed through as
 * undefined rather than guessed at: printing today's custody record when the
 * address asked for run 7 would be a quiet substitution on a signed document.
 * An unknown but well formed id reaches the API and comes back 404 no_run,
 * which the page states.
 */
export type ArtifactSearchParams = { run?: string | string[] };

export function runParam(params: ArtifactSearchParams | undefined): number | undefined {
  const raw = Array.isArray(params?.run) ? params?.run[0] : params?.run;
  if (raw === undefined || raw === "") return undefined;
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0) return undefined;
  return parsed;
}

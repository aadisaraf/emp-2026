/** The `?run=` query parameter the three artifact endpoints accept. */
export type ArtifactSearchParams = { run?: string | string[] };

export function runParam(params: ArtifactSearchParams | undefined): number | undefined {
  const raw = Array.isArray(params?.run) ? params?.run[0] : params?.run;
  if (raw === undefined || raw === "") return undefined;
  const parsed = Number(raw);
  if (!Number.isInteger(parsed) || parsed <= 0) return undefined;
  return parsed;
}

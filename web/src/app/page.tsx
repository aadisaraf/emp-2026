import { ErrorState } from "@/components";
import { attempt, getStatus } from "@/lib/api";
import { TodayBoard } from "./_dashboard/TodayBoard";

/* Today. */

export const dynamic = "force-dynamic";

export default async function TodayPage() {
  const result = await attempt(getStatus());

  if (!result.ok) {
    return <ErrorState failure={result.error} />;
  }

  return <TodayBoard initial={result.data} />;
}

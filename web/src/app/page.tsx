import { ErrorState } from "@/components";
import { attempt, getStatus } from "@/lib/api";
import { TodayBoard } from "./_dashboard/TodayBoard";

/*
  Today.

  The screen a kitchen manager opens at 06:40 to find out what comes off the
  shelf before service, and the first thing a demo audience sees.

  This file does exactly two things: fetch GET /api/v1/status on the server, so
  the first paint is real data rather than a skeleton, and hand it to the client
  island that keeps it current. Every number on the page comes from that one
  payload. When the API does not answer, the page says so and renders no
  figures at all: a placeholder count on a recall screen is worse than an empty
  one, because a placeholder gets believed.

  Live behaviour lives in _dashboard/useStatusFeed.ts. A file lands in
  data/watched/, the poller sees a new run id two seconds later, and this open
  tab becomes today's sheet with nobody touching it.
*/

export const dynamic = "force-dynamic";

export default async function TodayPage() {
  const result = await attempt(getStatus());

  if (!result.ok) {
    return <ErrorState failure={result.error} />;
  }

  return <TodayBoard initial={result.data} />;
}

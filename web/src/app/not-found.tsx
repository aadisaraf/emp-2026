import Link from "next/link";
import { EmptyState } from "@/components";

export default function NotFound() {
  return (
    <EmptyState
      heading="There is no page at this address."
      body="Nothing was read and nothing is claimed here. The routes that exist are in the nav on the left."
      action={<Link href="/">Go to Today</Link>}
    />
  );
}

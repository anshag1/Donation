import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export default function EventNotFound() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>We couldn&apos;t find that event</CardTitle>
        <CardDescription>
          This link may have expired, or the event may no longer be active.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link href="/donate">Make a general donation instead</Link>
        </Button>
      </CardContent>
    </Card>
  );
}

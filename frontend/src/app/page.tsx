"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useMe } from "@/lib/api/hooks";
import { LoadingState, ErrorState } from "@/components/ui/states";

export default function HomePage() {
  const router = useRouter();
  const { data: me, isLoading, error } = useMe();

  useEffect(() => {
    if (!me) return;
    router.replace(me.role === "admin" ? "/admin" : "/evaluations");
  }, [me, router]);

  return (
    <main className="container py-20">
      {isLoading || me ? (
        <LoadingState label="Signing you in…" />
      ) : error ? (
        <ErrorState message={(error as Error).message} />
      ) : null}
    </main>
  );
}

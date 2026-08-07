"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppHeader } from "@/components/app-header";
import { LoadingState } from "@/components/ui/states";
import { useMe } from "@/lib/api/hooks";

const NAV = [
  { href: "/admin/contents", label: "Courses" },
  { href: "/admin/generators", label: "Generators" },
  { href: "/admin/briefs", label: "Briefs" },
  { href: "/admin/instruments", label: "Instruments" },
  { href: "/admin/profiles", label: "Profiles" },
  { href: "/admin/studies", label: "Studies" },
  { href: "/admin/campaigns", label: "Campaigns" },
  { href: "/admin/reports", label: "Reports" },
];

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const { data: me, isLoading } = useMe();

  useEffect(() => {
    if (me && me.role !== "admin") router.replace("/evaluations");
  }, [me, router]);

  if (isLoading || !me) {
    return (
      <>
        <AppHeader subtitle="Admin" />
        <LoadingState />
      </>
    );
  }

  if (me.role !== "admin") {
    return (
      <>
        <AppHeader subtitle="Admin" />
        <LoadingState label="Redirecting…" />
      </>
    );
  }

  return (
    <>
      <AppHeader
        subtitle="Admin"
        nav={NAV.map((item) => ({ ...item, active: pathname.startsWith(item.href) }))}
      />
      <main className="container py-8">{children}</main>
    </>
  );
}

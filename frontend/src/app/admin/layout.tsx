"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { AppHeader } from "@/components/app-header";
import { LoadingState } from "@/components/ui/states";
import { useMe } from "@/lib/api/hooks";
import { IS_LOCAL_AUTH } from "@/lib/auth";
import { cn } from "@/lib/utils";

/**
 * The console's destinations, grouped by how often anyone needs them.
 *
 * They used to be ten flat links in the header, in the order they were built — which is the
 * order of the backend's modules, and says nothing about the work. Three groups say it:
 * what the daily loop runs on, what gets set up once at the start of a project, and the
 * human-evaluation path, which is a different job with a different cadence.
 *
 * `Profiles` keeps its name. `ContentProfile` is a term of the GLOSSARY, and renaming what a
 * page is called is a decision of its own, not something to slip into a reshuffle. The group
 * headings are new, but they name no concept — they organize.
 */
const NAV = [
  {
    group: "Measure",
    items: [
      // First: it is the errand the other two exist to serve. Local only, and behind a
      // build-time constant, so it leaves a deployed bundle entirely — the scan endpoints
      // it needs do not exist outside AUTH_MODE=local (ADR-0035).
      ...(IS_LOCAL_AUTH ? [{ href: "/admin/measure", label: "Import & measure" }] : []),
      { href: "/admin/contents", label: "Courses" },
      { href: "/admin/studies", label: "Studies" },
    ],
  },
  {
    group: "Definitions",
    items: [
      { href: "/admin/instruments", label: "Instruments" },
      { href: "/admin/assessors", label: "Assessors" },
      { href: "/admin/generators", label: "Generators" },
      { href: "/admin/briefs", label: "Briefs" },
      { href: "/admin/profiles", label: "Profiles" },
    ],
  },
  {
    group: "Human evaluation",
    items: [
      { href: "/admin/campaigns", label: "Campaigns" },
      { href: "/admin/calibration", label: "Calibration" },
      { href: "/admin/reports", label: "Reports" },
    ],
  },
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
      <AppHeader subtitle="Admin" />
      <div className="container flex flex-col gap-6 py-8 lg:flex-row lg:gap-10">
        <SideNav pathname={pathname} />
        <main className="min-w-0 flex-1">{children}</main>
      </div>
    </>
  );
}

/**
 * Wide: a rail beside the content, sticky under the header. Narrow: the same groups above
 * it, wrapping. No drawer and no popover — the whole point of a rail is that the structure
 * is legible without opening anything, and a menu would put it back behind a click.
 */
function SideNav({ pathname }: { pathname: string }) {
  return (
    <nav
      aria-label="Admin sections"
      className="shrink-0 lg:sticky lg:top-16 lg:h-fit lg:w-44 lg:self-start"
    >
      <div className="flex flex-wrap gap-x-8 gap-y-4 lg:flex-col lg:gap-6">
        {NAV.map((section) => (
          <div key={section.group} className="min-w-0">
            <p className="px-2 pb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
              {section.group}
            </p>
            <div className="flex flex-wrap items-center gap-1 lg:flex-col lg:items-stretch">
              {section.items.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  // `startsWith` on purpose, so a page's own sub-routes keep its entry lit.
                  // No destination's href is a prefix of another's.
                  aria-current={pathname.startsWith(item.href) ? "page" : undefined}
                  className={cn(
                    "rounded-md px-2 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                    pathname.startsWith(item.href) && "bg-accent text-foreground",
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </nav>
  );
}

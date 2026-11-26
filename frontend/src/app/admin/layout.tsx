"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { AppHeader } from "@/components/app-header";
import { LoadingState } from "@/components/ui/states";
import { useMe } from "@/lib/api/hooks";
import { IS_LOCAL_AUTH } from "@/lib/auth";
import { cn } from "@/lib/utils";

type NavItem = { href: string; label: string; exact?: boolean };
type NavGroup = { group: string; items: NavItem[]; collapsed?: boolean };

/**
 * The console's destinations, grouped by the task somebody arrives with.
 *
 * The previous grouping was by how often each page is needed, which is a maintainer's view:
 * half the rail was definitions that a set-up workbench already holds, ahead of the two
 * pages a newcomer can learn from. Now the rail reads as the work: evaluate, ask experts,
 * understand what is measured, and, folded away, the setup that `task setup` already did.
 * Every page keeps its route and its acts; only where it sits in the rail changes.
 */
const NAV: NavGroup[] = [
  {
    group: "Evaluate",
    items: [
      // Exact, because every admin route starts with `/admin`.
      { href: "/admin", label: "Home", exact: true },
      // Local only, and behind a build-time constant, so it leaves a deployed bundle
      // entirely: the scan endpoints it needs do not exist outside local mode (ADR-0035).
      ...(IS_LOCAL_AUTH ? [{ href: "/admin/measure", label: "Evaluate courses" }] : []),
      { href: "/admin/contents", label: "Courses" },
      { href: "/admin/studies", label: "Studies" },
    ],
  },
  {
    group: "Experts",
    items: [
      { href: "/admin/campaigns", label: "Campaigns" },
      // Not "Reports": a result belongs to the campaign that produced it and is read there
      // (ADR-0060). What is left here is the one cross-campaign question, who is carrying
      // what, and it is about people, not about measurements.
      { href: "/admin/workload", label: "Evaluator workload" },
    ],
  },
  {
    group: "Understand",
    items: [
      { href: "/admin/how-it-works", label: "How evaluation works" },
      { href: "/admin/instruments", label: "Instruments" },
      { href: "/admin/assessors", label: "Assessors" },
    ],
  },
  {
    // Folded: `task setup` did all of this, and a newcomer needs none of it to start.
    // `Profiles` keeps its name: `ContentProfile` is a GLOSSARY term (ADR-0069).
    group: "Setup",
    collapsed: true,
    items: [
      { href: "/admin/generators", label: "Generators" },
      { href: "/admin/briefs", label: "Briefs" },
      { href: "/admin/datasets", label: "Datasets" },
      { href: "/admin/profiles", label: "Profiles" },
      // The reference instrument the experts answer, beside the rest of what is set up once.
      { href: "/admin/rubrics", label: "Rubrics" },
      // Where an instrument is tuned: a dry run with every LLM call shown, and the reading
      // against a campaign (ADR-0064).
      { href: "/admin/calibration", label: "Calibration" },
    ],
  },
];

function isCurrent(pathname: string, item: NavItem): boolean {
  // `startsWith` otherwise, so a page's own sub-routes keep its entry lit. No destination's
  // href is a prefix of another's, apart from `/admin` itself, which is why it is exact.
  return item.exact ? pathname === item.href : pathname.startsWith(item.href);
}

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
 * it, wrapping. No drawer and no popover: the point of a rail is that the structure is legible
 * without opening anything. The one exception is Setup, folded on purpose because it is the
 * part a reader should not have to read to start.
 */
function SideNav({ pathname }: { pathname: string }) {
  return (
    <nav
      aria-label="Admin sections"
      className="shrink-0 lg:sticky lg:top-16 lg:h-fit lg:w-44 lg:self-start"
    >
      <div className="flex flex-wrap gap-x-8 gap-y-4 lg:flex-col lg:gap-6">
        {NAV.map((section) => {
          const links = (
            <div className="flex flex-wrap items-center gap-1 lg:flex-col lg:items-stretch">
              {section.items.map((item) => {
                const current = isCurrent(pathname, item);
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    aria-current={current ? "page" : undefined}
                    className={cn(
                      "rounded-md px-2 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                      current && "bg-accent text-foreground",
                    )}
                  >
                    {item.label}
                  </Link>
                );
              })}
            </div>
          );
          const heading =
            "px-2 pb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground";
          if (section.collapsed) {
            return (
              <FoldedGroup
                key={section.group}
                title={section.group}
                headingClassName={heading}
                holdsCurrent={section.items.some((item) => isCurrent(pathname, item))}
                pathname={pathname}
              >
                {links}
              </FoldedGroup>
            );
          }
          return (
            <div key={section.group} className="min-w-0">
              <p className={heading}>{section.group}</p>
              {links}
            </div>
          );
        })}
      </div>
    </nav>
  );
}

/**
 * A group the rail folds away, which opens by itself whenever the current page is inside it,
 * so the reader is never on a page the rail hides. The reader can still fold it again; the
 * next navigation into it opens it once more.
 */
function FoldedGroup({
  title,
  headingClassName,
  holdsCurrent,
  pathname,
  children,
}: {
  title: string;
  headingClassName: string;
  holdsCurrent: boolean;
  pathname: string;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(holdsCurrent);
  useEffect(() => {
    if (holdsCurrent) setOpen(true);
  }, [holdsCurrent, pathname]);

  return (
    <details
      className="min-w-0"
      open={open}
      onToggle={(event) => setOpen((event.currentTarget as HTMLDetailsElement).open)}
    >
      <summary className={cn(headingClassName, "cursor-pointer select-none hover:text-foreground")}>
        {title}
      </summary>
      {children}
    </details>
  );
}

"use client";

import Link from "next/link";
import { UserMenu } from "@/lib/auth";
import { cn } from "@/lib/utils";

export function AppHeader({
  subtitle,
  nav,
}: {
  subtitle?: string;
  nav?: { href: string; label: string; active?: boolean }[];
}) {
  return (
    <header className="sticky top-0 z-10 border-b bg-background/80 backdrop-blur">
      <div className="container flex h-16 items-center justify-between gap-4">
        <div className="flex items-center gap-6">
          <Link href="/" className="flex items-baseline gap-2">
            <span className="text-base font-semibold tracking-tight">LearnPack Evals</span>
            {subtitle ? (
              <span className="hidden text-sm text-muted-foreground sm:inline">{subtitle}</span>
            ) : null}
          </Link>
          {nav ? (
            <nav className="flex items-center gap-1">
              {nav.map((item) => (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent hover:text-foreground",
                    item.active && "bg-accent text-foreground",
                  )}
                >
                  {item.label}
                </Link>
              ))}
            </nav>
          ) : null}
        </div>
        <UserMenu />
      </div>
    </header>
  );
}

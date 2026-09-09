"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun, type LucideIcon } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

/**
 * The three states of the theme, in the order the button walks through them.
 *
 * `system` last on purpose: it is where everybody starts, so the first click has to lead
 * somewhere, and the way back to "let the device decide" is one more click rather than a menu.
 */
const ORDER = ["light", "dark", "system"] as const;

type Choice = (typeof ORDER)[number];

const LABEL: Record<Choice, string> = {
  light: "Light",
  dark: "Dark",
  system: "System",
};

const ICON: Record<Choice, LucideIcon> = {
  light: Sun,
  dark: Moon,
  system: Monitor,
};

/**
 * One button that cycles the theme, and it shows the state it is **in**, not the one it moves
 * to — an icon that means "click me for dark" and an icon that means "you are in dark" cannot
 * both be the moon. What it moves to is in the label, which is where a sentence fits.
 *
 * **It renders nothing until it has mounted.** The chosen theme lives in the browser, so the
 * server cannot know it; drawing a sun that turns into a moon on hydration is a mismatch React
 * complains about and a reader sees. The placeholder keeps the header from shifting.
 */
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) return <div className="h-10 w-10" aria-hidden />;

  const current = (ORDER as readonly string[]).includes(theme ?? "")
    ? (theme as Choice)
    : "system";
  const next = ORDER[(ORDER.indexOf(current) + 1) % ORDER.length];
  const Icon = ICON[current];
  const description = `Theme: ${LABEL[current].toLowerCase()}. Switch to ${LABEL[next].toLowerCase()}.`;

  return (
    <Button
      variant="ghost"
      size="icon"
      type="button"
      onClick={() => setTheme(next)}
      title={description}
      aria-label={description}
    >
      <Icon className="h-4 w-4" />
    </Button>
  );
}

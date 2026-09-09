"use client";

import { ThemeProvider as NextThemes, useTheme } from "next-themes";
import { Toaster } from "sonner";

/**
 * Light, dark, and the one the device is already in.
 *
 * The palette has always had two halves (`globals.css`), and Tailwind has always been told to
 * switch on a class (`darkMode: ["class"]`) — what was missing was somebody to put the class on
 * the document. That is all this is.
 *
 * **Three states, not two.** `system` is the default because it is the only one that is right
 * without being asked: whoever arrives at night gets the dark screen their machine already
 * decided on. Choosing light or dark is choosing *against* the device, so it is remembered
 * (localStorage, `next-themes`) and it wins from then on.
 *
 * The library is here for the one part that cannot be written in React: a blocking script that
 * sets the class **before the first paint**. Without it every load of a dark session flashes
 * white, which is worse than not offering the theme at all.
 */
export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemes
      attribute="class"
      defaultTheme="system"
      enableSystem
      // Nothing on this screen should animate its way into the new theme: with hundreds of
      // elements carrying `transition-colors`, the switch becomes a slow wash instead of a
      // change of state.
      disableTransitionOnChange
    >
      {children}
    </NextThemes>
  );
}

/**
 * The toaster, told which theme it is in.
 *
 * Sonner paints itself rather than through our tokens, and its default is light — on a dark
 * screen it would be the one white thing left. It is handed `resolvedTheme` rather than its own
 * `"system"`, because the two disagree exactly when somebody has chosen against their device,
 * and the choice is what should be honoured.
 */
export function ThemedToaster() {
  const { resolvedTheme } = useTheme();
  return (
    <Toaster
      richColors
      position="top-right"
      theme={resolvedTheme === "dark" ? "dark" : "light"}
    />
  );
}

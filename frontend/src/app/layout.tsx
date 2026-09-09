import type { Metadata } from "next";
import { AuthProvider } from "@/lib/auth";
import { QueryProvider } from "@/lib/query-provider";
import { ThemeProvider, ThemedToaster } from "@/components/theme";
import "./globals.css";

export const metadata: Metadata = {
  title: "LearnPack Evals",
  description: "Pedagogical quality evaluation of AI-generated educational content.",
};

/**
 * `AuthProvider` stays outside `<html>`: under Clerk it is `<ClerkProvider>`, which wants to be
 * the outermost thing there is. The theme goes **inside** the body instead — it needs no
 * provider above it to work (it writes the class straight onto the document), and the things
 * that have to read it, Clerk's own widgets among them, are all below this point.
 */
export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <AuthProvider>
      {/* `suppressHydrationWarning` because the theme class is written onto this element before
          React runs, which is the whole point of it being written before React runs. */}
      <html lang="en" suppressHydrationWarning>
        <body className="min-h-screen antialiased">
          <ThemeProvider>
            <QueryProvider>{children}</QueryProvider>
            <ThemedToaster />
          </ThemeProvider>
        </body>
      </html>
    </AuthProvider>
  );
}

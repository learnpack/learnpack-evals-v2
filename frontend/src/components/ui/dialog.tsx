"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

/** The open modals, innermost last. A form can open a dialog of its own — registering a
 *  generator version from inside the course form is the ordinary case — and without a stack
 *  both would answer the same Escape, and the inner one closing would give the page back its
 *  scroll while the outer one is still up. */
const openDialogs: object[] = [];

/** Minimal controlled modal — enough for the admin forms, no Radix dependency. */
export function Dialog({
  open,
  onClose,
  title,
  description,
  children,
  className,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  // Held in a ref so the effect depends on `open` alone: an inline `onClose` would otherwise
  // re-register on every render, and with it re-order the stack under an inner dialog.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    const token = {};
    openDialogs.push(token);
    document.body.style.overflow = "hidden";

    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (openDialogs[openDialogs.length - 1] !== token) return;
      onCloseRef.current();
    };
    document.addEventListener("keydown", onKey);

    return () => {
      document.removeEventListener("keydown", onKey);
      const at = openDialogs.indexOf(token);
      if (at !== -1) openDialogs.splice(at, 1);
      if (openDialogs.length === 0) document.body.style.overflow = "";
    };
  }, [open]);

  // Rendered into the body, not where it is written. A modal is written wherever it is
  // opened from — and that is often inside a form, which would make its own fields
  // descendants of that form: invalid HTML, and a hydration error. Portalling also keeps it
  // clear of any ancestor's overflow or stacking context.
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);

  if (!open || !mounted) return null;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4 sm:items-center">
      <div
        role="dialog"
        aria-modal="true"
        className={cn(
          "relative w-full max-w-lg rounded-xl border bg-card p-6 shadow-lg",
          className,
        )}
      >
        <button
          type="button"
          onClick={onClose}
          className="absolute right-4 top-4 rounded-md p-1 text-muted-foreground hover:bg-accent"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </button>
        <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
        {description ? <p className="mt-1 text-sm text-muted-foreground">{description}</p> : null}
        <div className="mt-4">{children}</div>
      </div>
    </div>,
    document.body,
  );
}

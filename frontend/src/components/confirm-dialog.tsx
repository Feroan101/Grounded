"use client";

import { useEffect, useRef } from "react";

interface ConfirmDialogProps {
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title,
  message,
  confirmLabel = "Delete",
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    cancelRef.current?.focus();

    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onCancel();
      }
    }

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      onClick={onCancel}
    >
      <div className="absolute inset-0 bg-black/40 backdrop-blur-sm" />
      <div
        ref={dialogRef}
        className="relative w-full max-w-sm rounded-2xl bg-marble p-6 shadow-xl animate-fade-in"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="confirm-dialog-title" className="text-lg font-semibold text-espresso">
          {title}
        </h3>
        <p className="mt-2 text-sm leading-relaxed text-latte">{message}</p>
        <div className="mt-6 flex justify-end gap-3">
          <button
            ref={cancelRef}
            onClick={onCancel}
            className="rounded-xl border border-stone/60 bg-ivory px-4 py-2 text-sm font-medium text-bean transition-all hover:bg-cream/50 focus:outline-none focus:ring-2 focus:ring-espresso/20 focus:ring-offset-2 focus:ring-offset-marble"
          >
            {cancelLabel}
          </button>
          <button
            onClick={onConfirm}
            className="rounded-xl bg-espresso px-4 py-2 text-sm font-medium text-ivory transition-all hover:bg-espresso/90 focus:outline-none focus:ring-2 focus:ring-espresso/30 focus:ring-offset-2 focus:ring-offset-marble"
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}

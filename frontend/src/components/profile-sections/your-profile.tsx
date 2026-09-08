"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth-context";

const DISPLAY_NAME_COOKIE = "grounded_display_name";
const CONSENT_COOKIE = "grounded_cookie_consent";

function setCookie(name: string, value: string) {
  const expires = new Date();
  expires.setFullYear(expires.getFullYear() + 1);
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
}

function getConsentValue(): "accepted" | "declined" | null {
  if (typeof document === "undefined") return null;
  const val = document.cookie.split("; ").find((c) => c.startsWith(`${CONSENT_COOKIE}=`));
  if (!val) return null;
  const v = val.split("=")[1];
  if (v === "accepted") return "accepted";
  if (v === "declined") return "declined";
  return null;
}

function getCustomName(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${DISPLAY_NAME_COOKIE}=`));
  return match ? decodeURIComponent(match.split("=")[1]) : "";
}

export function YourProfileSection() {
  const { user } = useAuth();
  const [customName, setCustomName] = useState(getCustomName);
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [consentState] = useState<"accepted" | "declined" | null>(getConsentValue);

  const displayName = customName || user?.displayName || "Grounded User";

  function handleSave() {
    const trimmed = editValue.trim();
    if (trimmed && consentState === "accepted") {
      setCookie(DISPLAY_NAME_COOKIE, trimmed);
      setCustomName(trimmed);
    } else if (trimmed) {
      setCustomName(trimmed);
    }
    setIsEditing(false);
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Profile card */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-6">
        <div className="flex flex-col items-center text-center sm:flex-row sm:items-start sm:text-left">
          {user?.photoURL ? (
            <img
              src={user.photoURL}
              alt=""
              className="h-20 w-20 rounded-full ring-4 ring-stone/50"
            />
          ) : (
            <div className="flex h-20 w-20 items-center justify-center rounded-full bg-espresso/10 text-3xl font-semibold text-espresso">
              {displayName[0] || "?"}
            </div>
          )}

          <div className="mt-4 sm:ml-6 sm:mt-0">
            <h2 className="text-xl font-semibold text-espresso">{displayName}</h2>
            <p className="mt-1 text-sm text-latte">{user?.email}</p>
          </div>
        </div>
      </div>

      {/* Display name */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-4 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Display Name
        </h3>

        {isEditing ? (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSave();
            }}
            className="flex flex-col gap-3 sm:flex-row sm:items-center"
          >
            <input
              autoFocus
              value={editValue}
              onChange={(e) => setEditValue(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Escape") setIsEditing(false);
              }}
              className="w-full rounded-lg border border-espresso/40 bg-marble px-3 py-2 text-sm text-bean focus:outline-none focus:ring-1 focus:ring-espresso/30 sm:w-64"
              aria-label="Display name"
            />
            <div className="flex gap-2">
              <button
                type="submit"
                className="rounded-lg bg-espresso px-3 py-1.5 text-xs font-medium text-ivory hover:bg-espresso/90"
              >
                Save
              </button>
              <button
                type="button"
                onClick={() => setIsEditing(false)}
                className="rounded-lg border border-stone/50 px-3 py-1.5 text-xs font-medium text-bean hover:bg-cream/50"
              >
                Cancel
              </button>
            </div>
          </form>
        ) : (
          <div className="flex items-center justify-between">
            <span className="text-sm text-bean">{displayName}</span>
            <button
              onClick={() => {
                setEditValue(customName || user?.displayName || "");
                setIsEditing(true);
              }}
              className="rounded-lg border border-stone/50 px-3 py-1.5 text-xs font-medium text-bean transition-all hover:bg-cream/50"
            >
              Edit
            </button>
          </div>
        )}

        <p className="mt-3 text-xs text-latte/70">
          This is the name Grounded uses to address you. It is stored locally in your browser.
        </p>
      </div>

      {/* Email */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-4 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Email
        </h3>
        <div className="flex items-center justify-between">
          <span className="text-sm text-bean">{user?.email || "Not available"}</span>
          <span className="text-xs text-latte/70">From Google account</span>
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { signOut } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";

const DISPLAY_NAME_COOKIE = "grounded_display_name";
const CONSENT_COOKIE = "grounded_cookie_consent";

function setCookie(name: string, value: string) {
  const expires = new Date();
  expires.setFullYear(expires.getFullYear() + 1);
  document.cookie = `${name}=${encodeURIComponent(value)}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
}

function deleteCookie(name: string) {
  document.cookie = `${name}=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/; SameSite=Lax`;
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

export function ProfileView() {
  const { user } = useAuth();
  const [customName, setCustomName] = useState(() => {
    if (typeof document === "undefined") return "";
    const match = document.cookie.split("; ").find((c) => c.startsWith(`${DISPLAY_NAME_COOKIE}=`));
    return match ? decodeURIComponent(match.split("=")[1]) : "";
  });
  const [isEditing, setIsEditing] = useState(false);
  const [editValue, setEditValue] = useState("");
  const [consentState, setConsentState] = useState<"accepted" | "declined" | null>(getConsentValue);
  const [showCookieSettings, setShowCookieSettings] = useState(false);

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

  function handleAcceptCookies() {
    setCookie(CONSENT_COOKIE, "accepted");
    setConsentState("accepted");
    if (customName) {
      setCookie(DISPLAY_NAME_COOKIE, customName);
    }
    setShowCookieSettings(false);
  }

  function handleDeclineCookies() {
    setCookie(CONSENT_COOKIE, "declined");
    setConsentState("declined");
    deleteCookie(DISPLAY_NAME_COOKIE);
    setShowCookieSettings(false);
  }

  const handleSignOut = useCallback(async () => {
    await signOut(getFirebaseAuth());
  }, []);

  return (
    <div className="mx-auto max-w-lg px-4 py-8 sm:px-6">
      <div className="flex flex-col items-center text-center">
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

        <h2 className="mt-4 text-xl font-semibold text-espresso">
          {displayName}
        </h2>
        <p className="mt-1 text-sm text-latte">
          {user?.email}
        </p>
      </div>

      <div className="mt-8 rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-4 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Account
        </h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-bean">Name</span>
            {isEditing ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  handleSave();
                }}
                className="flex items-center gap-2"
              >
                <input
                  autoFocus
                  value={editValue}
                  onChange={(e) => setEditValue(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") setIsEditing(false);
                  }}
                  className="w-40 rounded-lg border border-espresso/40 bg-marble px-2 py-1 text-sm text-bean focus:outline-none focus:ring-1 focus:ring-espresso/30"
                  aria-label="Display name"
                />
                <button
                  type="submit"
                  className="rounded-lg bg-espresso px-2.5 py-1 text-xs font-medium text-ivory hover:bg-espresso/90"
                >
                  Save
                </button>
                <button
                  type="button"
                  onClick={() => setIsEditing(false)}
                  className="rounded-lg border border-stone/50 px-2.5 py-1 text-xs font-medium text-bean hover:bg-cream/50"
                >
                  Cancel
                </button>
              </form>
            ) : (
              <button
                onClick={() => {
                  setEditValue(customName || user?.displayName || "");
                  setIsEditing(true);
                }}
                className="group flex items-center gap-2 text-latte hover:text-espresso"
              >
                <span>{displayName}</span>
                <svg className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                </svg>
              </button>
            )}
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-bean">Email</span>
            <span className="text-latte">{user?.email || "—"}</span>
          </div>
        </div>
      </div>

      <div className="mt-4 rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-4 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Preferences
        </h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <div>
              <span className="text-bean">Cookies</span>
              <p className="mt-0.5 text-[11px] text-latte/70">
                {consentState === "accepted"
                  ? "Accepting cookies allows saving your display name."
                  : consentState === "declined"
                    ? "Declined — only essential cookies are used."
                    : "Not yet decided."}
              </p>
            </div>
            <button
              onClick={() => setShowCookieSettings(!showCookieSettings)}
              className="rounded-lg border border-stone/50 px-3 py-1.5 text-xs font-medium text-bean transition-all hover:bg-cream/50"
            >
              {consentState ? "Change" : "Set preferences"}
            </button>
          </div>

          {showCookieSettings && (
            <div className="rounded-lg border border-cafe/15 bg-marble p-4 animate-fade-in">
              <p className="mb-3 text-xs leading-relaxed text-latte">
                Choose whether to accept non-essential cookies for local preferences like your display name.
              </p>
              <div className="flex gap-2">
                <button
                  onClick={handleAcceptCookies}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                    consentState === "accepted"
                      ? "bg-espresso text-ivory"
                      : "border border-stone/50 text-bean hover:bg-cream/50"
                  }`}
                >
                  Accept
                </button>
                <button
                  onClick={handleDeclineCookies}
                  className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
                    consentState === "declined"
                      ? "bg-espresso text-ivory"
                      : "border border-stone/50 text-bean hover:bg-cream/50"
                  }`}
                >
                  Decline
                </button>
              </div>
            </div>
          )}
        </div>
      </div>

      <button
        onClick={handleSignOut}
        className="mt-6 w-full rounded-xl border border-stone/50 bg-ivory px-4 py-3 text-sm font-medium text-bean transition-all hover:border-espresso/40 hover:bg-cream/50"
      >
        Sign out
      </button>
    </div>
  );
}

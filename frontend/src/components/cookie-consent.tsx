"use client";

import { useState } from "react";

const CONSENT_COOKIE = "grounded_cookie_consent";

function setConsentCookie(value: "accepted" | "declined") {
  const expires = new Date();
  expires.setFullYear(expires.getFullYear() + 1);
  document.cookie = `${CONSENT_COOKIE}=${value}; expires=${expires.toUTCString()}; path=/; SameSite=Lax`;
}

function CookieSvg() {
  return (
    <svg width="40" height="40" viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg" className="flex-shrink-0">
      {/* Cookie body */}
      <circle cx="20" cy="20" r="16" fill="#D2A679" />
      <circle cx="20" cy="20" r="16" fill="url(#cookieGrad)" />
      {/* Chocolate chips */}
      <circle cx="14" cy="14" r="2.2" fill="#5C3D2E" />
      <circle cx="24" cy="12" r="1.8" fill="#5C3D2E" />
      <circle cx="18" cy="22" r="2" fill="#5C3D2E" />
      <circle cx="26" cy="22" r="1.6" fill="#5C3D2E" />
      <circle cx="12" cy="24" r="1.4" fill="#5C3D2E" />
      {/* Cookie bite */}
      <path d="M30 8 Q36 12 34 18 Q32 14 28 10 Z" fill="var(--marble, #F7F6F2)" />
      {/* Crumbs */}
      <circle cx="8" cy="34" r="1.2" fill="#D2A679" opacity="0.7" />
      <circle cx="32" cy="32" r="1" fill="#D2A679" opacity="0.6" />
      <circle cx="6" cy="30" r="0.8" fill="#D2A679" opacity="0.5" />
      <defs>
        <radialGradient id="cookieGrad" cx="0.35" cy="0.35" r="0.65">
          <stop offset="0%" stopColor="#E8C9A0" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#C49A6C" stopOpacity="0.3" />
        </radialGradient>
      </defs>
    </svg>
  );
}

export function CookieConsent() {
  const [visible, setVisible] = useState(() => {
    if (typeof document === "undefined") return false;
    const val = document.cookie.split("; ").find((c) => c.startsWith(`${CONSENT_COOKIE}=`));
    return !val;
  });

  function handleAccept() {
    setConsentCookie("accepted");
    setVisible(false);
  }

  function handleDecline() {
    setConsentCookie("declined");
    setVisible(false);
  }

  if (!visible) return null;

  return (
    <div className="fixed bottom-0 inset-x-0 z-50 flex justify-center px-4 pb-4 md:pb-6">
      <div className="flex w-full max-w-lg items-start gap-3 rounded-xl border border-espresso/15 bg-marble p-4 shadow-lg md:max-w-md">
        <CookieSvg />
        <div className="flex-1 min-w-0">
          <p className="text-xs leading-relaxed text-latte">
            Grounded uses cookies for local preferences such as your display name and cookie consent.
          </p>
          <div className="mt-3 flex items-center gap-2">
            <button
              onClick={handleAccept}
              className="rounded-lg bg-espresso px-3.5 py-1.5 text-xs font-medium text-ivory transition-all hover:bg-bean"
            >
              Accept Cookies
            </button>
            <button
              onClick={handleDecline}
              className="rounded-lg border border-stone/50 px-3.5 py-1.5 text-xs font-medium text-bean transition-all hover:bg-cream/50"
            >
              Decline
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

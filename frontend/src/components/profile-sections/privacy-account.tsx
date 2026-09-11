"use client";

import { useState, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { useProfile } from "@/lib/profile-context";
import { signOut, deleteUser } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { LogOutIcon, Trash2Icon, AlertTriangleIcon } from "@/components/profile-icons";

const CONSENT_COOKIE = "grounded_cookie_consent";
const DISPLAY_NAME_COOKIE = "grounded_display_name";

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

function Toggle({
  enabled,
  onChange,
  label,
}: {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-espresso/30 focus:ring-offset-2 focus:ring-offset-marble ${
        enabled ? "bg-espresso" : "bg-stone"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          enabled ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

export function PrivacyAccountSection() {
  const { user } = useAuth();
  const {
    conversationHistoryEnabled,
    updateConversationHistory,
    clearConversationHistory,
    loading: profileLoading,
    saving,
  } = useProfile();
  const [consentState, setConsentState] = useState<"accepted" | "declined" | null>(getConsentValue);
  const [showCookieSettings, setShowCookieSettings] = useState(false);
  const [showClearHistoryDialog, setShowClearHistoryDialog] = useState(false);
  const [showDeleteAccountDialog, setShowDeleteAccountDialog] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [historySaveError, setHistorySaveError] = useState<string | null>(null);

  function handleAcceptCookies() {
    setCookie(CONSENT_COOKIE, "accepted");
    setConsentState("accepted");
    setShowCookieSettings(false);
  }

  function handleDeclineCookies() {
    setCookie(CONSENT_COOKIE, "declined");
    setConsentState("declined");
    deleteCookie(DISPLAY_NAME_COOKIE);
    setShowCookieSettings(false);
  }

  const handleToggleHistory = useCallback(async (enabled: boolean) => {
    setHistorySaveError(null);
    try {
      await updateConversationHistory(enabled);
    } catch {
      setHistorySaveError("Failed to save preference. Please try again.");
    }
  }, [updateConversationHistory]);

  const handleClearHistory = useCallback(async () => {
    try {
      await clearConversationHistory();
      setShowClearHistoryDialog(false);
    } catch {
      setHistorySaveError("Failed to clear history. Please try again.");
    }
  }, [clearConversationHistory]);

  const handleSignOut = useCallback(async () => {
    await signOut(getFirebaseAuth());
  }, []);

  const handleDeleteAccount = useCallback(async () => {
    if (!user) return;
    setIsDeleting(true);
    try {
      await deleteUser(user);
    } catch (err) {
      console.error("Failed to delete account:", err);
      alert("Failed to delete account. You may need to re-authenticate first.");
    } finally {
      setIsDeleting(false);
      setShowDeleteAccountDialog(false);
    }
  }, [user]);

  return (
    <div className="animate-fade-in space-y-6">
      {/* Description */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <p className="text-xs leading-relaxed text-latte">
          Manage your cookies, conversation history, and account settings.
        </p>
      </div>

      {/* Cookie preferences */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-4 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Cookies
        </h3>

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-medium text-bean">Cookie preferences</p>
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
            className="shrink-0 self-start rounded-lg border border-stone/50 px-3 py-1.5 text-xs font-medium text-bean transition-all hover:bg-cream/50"
          >
            {consentState ? "Change" : "Set preferences"}
          </button>
        </div>

        {showCookieSettings && (
          <div className="mt-4 rounded-lg border border-cafe/15 bg-marble p-4 animate-fade-in">
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

      {/* Conversation history */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-4 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Conversation History
        </h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-4 rounded-lg bg-marble/50 px-3 py-2.5">
            <div>
              <p className="text-sm font-medium text-bean">Save conversations</p>
              <p className="mt-0.5 text-[11px] text-latte/70">
                Store and access your past conversations
              </p>
            </div>
            {profileLoading ? (
              <div className="h-6 w-11 animate-pulse rounded-full bg-stone" />
            ) : (
              <Toggle
                enabled={conversationHistoryEnabled}
                onChange={handleToggleHistory}
                label="Enable conversation history"
              />
            )}
          </div>

          {historySaveError && (
            <p className="text-xs text-danger/80 animate-fade-in">{historySaveError}</p>
          )}

          <button
            onClick={() => setShowClearHistoryDialog(true)}
            disabled={saving}
            className="flex w-full items-center gap-2 rounded-lg bg-marble/50 px-3 py-2.5 text-left text-sm font-medium text-bean transition-all hover:bg-cream/50 disabled:opacity-50"
          >
            <Trash2Icon className="h-4 w-4 text-latte" />
            Clear conversation history
          </button>
        </div>
      </div>

      {/* Account actions */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-4 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Account
        </h3>

        <div className="space-y-3">
          <button
            onClick={handleSignOut}
            className="flex w-full items-center gap-2 rounded-lg border border-stone/50 bg-ivory px-3 py-2.5 text-sm font-medium text-bean transition-all hover:border-espresso/40 hover:bg-cream/50"
          >
            <LogOutIcon className="h-4 w-4" />
            Sign out
          </button>

          <button
            onClick={() => setShowDeleteAccountDialog(true)}
            className="flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm font-medium text-danger/80 transition-all hover:bg-danger/10"
          >
            <AlertTriangleIcon className="h-4 w-4" />
            Delete account
          </button>
        </div>
      </div>

      {/* Clear history dialog */}
      {showClearHistoryDialog && (
        <ConfirmDialog
          title="Clear conversation history?"
          message="This will permanently delete all your conversations. This action cannot be undone."
          confirmLabel={saving ? "Clearing..." : "Clear history"}
          onConfirm={handleClearHistory}
          onCancel={() => setShowClearHistoryDialog(false)}
        />
      )}

      {/* Delete account dialog */}
      {showDeleteAccountDialog && (
        <ConfirmDialog
          title="Delete account?"
          message="This will permanently delete your account and all associated data. This action cannot be undone. You may need to re-authenticate before deleting."
          confirmLabel={isDeleting ? "Deleting..." : "Delete account"}
          onConfirm={handleDeleteAccount}
          onCancel={() => setShowDeleteAccountDialog(false)}
        />
      )}
    </div>
  );
}

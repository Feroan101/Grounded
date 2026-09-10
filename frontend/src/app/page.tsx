"use client";

import { useAuth } from "@/lib/auth-context";
import { ConversationProvider } from "@/lib/conversation-context";
import { ProfileProvider } from "@/lib/profile-context";
import { BackendReadinessProvider } from "@/lib/backend-readiness";
import { LandingPage } from "@/components/landing-page";
import { AuthenticatedApp } from "@/components/authenticated-app";
import { CookieConsent } from "@/components/cookie-consent";

export default function Home() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center bg-[#2B1B15]">
        <div className="flex items-center gap-2 text-white/60">
          <div className="h-1.5 w-1.5 rounded-full bg-white animate-pulse-dot" />
          <div className="h-1.5 w-1.5 rounded-full bg-white animate-pulse-dot" />
          <div className="h-1.5 w-1.5 rounded-full bg-white animate-pulse-dot" />
        </div>
      </div>
    );
  }

  if (!user) {
    return <LandingPage />;
  }

  return (
    <ProfileProvider>
      <BackendReadinessProvider>
        <ConversationProvider>
          <AuthenticatedApp />
          <CookieConsent />
        </ConversationProvider>
      </BackendReadinessProvider>
    </ProfileProvider>
  );
}

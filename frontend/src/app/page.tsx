"use client";

import { useAuth } from "@/lib/auth-context";
import { ConversationProvider } from "@/lib/conversation-context";
import { LandingPage } from "@/components/landing-page";
import { AuthenticatedApp } from "@/components/authenticated-app";

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
    <ConversationProvider>
      <AuthenticatedApp />
    </ConversationProvider>
  );
}

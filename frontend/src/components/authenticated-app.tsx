"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useAuth } from "@/lib/auth-context";
import { useConversations } from "@/lib/conversation-context";
import { ChatView } from "@/components/chat-view";
import { HistoryView } from "@/components/history-view";
import { ProfileView } from "@/components/profile-view";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { WakeUpToast } from "@/components/wake-up-toast";

type Section = "chat" | "history" | "profile";

function ErrorToast({ message, onDismiss }: { message: string; onDismiss: () => void }) {
  useEffect(() => {
    const t = setTimeout(onDismiss, 5000);
    return () => clearTimeout(t);
  }, [onDismiss]);

  return (
    <div className="fixed bottom-20 left-1/2 z-[60] -translate-x-1/2 animate-slide-up md:bottom-6">
      <div className="flex items-center gap-3 rounded-xl border border-espresso/15 bg-marble px-4 py-3 shadow-lg">
        <svg className="h-4 w-4 flex-shrink-0 text-espresso" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="10" />
          <path d="M12 8v4M12 16h.01" />
        </svg>
        <p className="text-sm text-bean">{message}</p>
        <button
          onClick={onDismiss}
          className="ml-2 flex h-5 w-5 flex-shrink-0 items-center justify-center rounded text-latte hover:text-espresso"
          aria-label="Dismiss"
        >
          <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M18 6L6 18M6 6l12 12" />
          </svg>
        </button>
      </div>
    </div>
  );
}

function RenameInput({
  initialTitle,
  onSave,
  onCancel,
}: {
  initialTitle: string;
  onSave: (title: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initialTitle);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    inputRef.current?.focus();
    inputRef.current?.select();
  }, []);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    onSave(value);
  }

  return (
    <form onSubmit={handleSubmit} className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
      <input
        ref={inputRef}
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={() => onSave(value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onCancel();
        }}
        className="min-w-0 flex-1 rounded border border-espresso/40 bg-ivory px-1.5 py-0.5 text-xs text-bean focus:outline-none focus:ring-1 focus:ring-espresso/30"
        aria-label="Rename conversation"
      />
    </form>
  );
}

function SidebarNav({
  activeSection,
  onNavigate,
  onNewChat,
}: {
  activeSection: Section;
  onNavigate: (s: Section) => void;
  onNewChat: () => void;
}) {
  const { user } = useAuth();
  const {
    conversations,
    activeConversationId,
    setActiveConversation,
    deleteConversation,
    renameConversation,
  } = useConversations();

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [renameTarget, setRenameTarget] = useState<string | null>(null);

  function handleSelect(id: string) {
    setActiveConversation(id);
    onNavigate("chat");
  }

  function handleDeleteConfirm() {
    if (deleteTarget) {
      deleteConversation(deleteTarget);
      setDeleteTarget(null);
    }
  }

  function handleRenameSave(title: string) {
    if (renameTarget) {
      renameConversation(renameTarget, title);
      setRenameTarget(null);
    }
  }

  return (
    <aside className="hidden h-full w-[220px] flex-shrink-0 flex-col border-r border-stone/50 bg-marble md:flex">
      <div className="flex items-center gap-3 border-b border-stone/50 px-4 py-4">
        <img
          src="/coffee-logo.png"
          alt="Grounded logo"
          className="h-8 w-8 rounded-lg object-cover"
        />
        <span className="text-sm font-semibold tracking-widest uppercase text-espresso">
          Grounded
        </span>
      </div>

      <div className="px-3 pt-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center gap-2 rounded-lg border border-stone/50 bg-ivory px-3 py-2 text-sm text-bean transition-all hover:border-espresso/40 hover:bg-cream/50"
        >
          <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
          New Chat
        </button>
      </div>

      <nav className="mt-3 flex flex-col gap-0.5 px-3">
        {(["chat", "history", "profile"] as Section[]).map((s) => (
          <button
            key={s}
            onClick={() => onNavigate(s)}
            className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-all ${
              activeSection === s
                ? "bg-espresso/10 text-espresso"
                : "text-latte hover:bg-cream/50 hover:text-bean"
            }`}
          >
            {s === "chat" && (
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
              </svg>
            )}
            {s === "history" && (
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 6v6l3 3" />
              </svg>
            )}
            {s === "profile" && (
              <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="8" r="4" />
                <path d="M20 21a8 8 0 1 0-16 0" />
              </svg>
            )}
            {s.charAt(0).toUpperCase() + s.slice(1)}
          </button>
        ))}
      </nav>

      {activeSection === "chat" && conversations.length > 0 && (
        <div className="mt-4 flex-1 overflow-y-auto border-t border-stone/50 px-3 pt-3">
          <p className="mb-2 px-3 text-[10px] font-medium uppercase tracking-wider text-latte/60">
            Recent
          </p>
          <div className="space-y-0.5">
            {conversations.slice(0, 8).map((conv) => (
              <div
                key={conv.id}
                onClick={() => handleSelect(conv.id)}
                className={`group flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-xs transition-all cursor-pointer ${
                  conv.id === activeConversationId
                    ? "bg-espresso/10 text-espresso"
                    : "text-latte hover:bg-cream/50 hover:text-bean"
                }`}
              >
                {renameTarget === conv.id ? (
                  <RenameInput
                    initialTitle={conv.title}
                    onSave={handleRenameSave}
                    onCancel={() => setRenameTarget(null)}
                  />
                ) : (
                  <>
                    <span className="truncate">{conv.title}</span>
                    <div className="flex flex-shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setRenameTarget(conv.id);
                        }}
                        className="rounded p-0.5 text-latte hover:text-espresso"
                        aria-label="Rename"
                      >
                        <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M17 3a2.83 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                        </svg>
                      </button>
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setDeleteTarget(conv.id);
                        }}
                        className="rounded p-0.5 text-latte hover:text-espresso"
                        aria-label="Delete"
                      >
                        <svg className="h-3 w-3" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M18 6L6 18M6 6l12 12" />
                        </svg>
                      </button>
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="mt-auto border-t border-stone/50 px-3 py-3">
        <div className="flex items-center gap-3">
          {user?.photoURL ? (
            <img
              src={user.photoURL}
              alt=""
              className="h-8 w-8 rounded-full object-cover ring-2 ring-stone/50"
            />
          ) : (
            <div className="flex h-8 w-8 items-center justify-center rounded-full bg-espresso/10 text-xs font-semibold text-espresso">
              {user?.displayName?.[0] || user?.email?.[0] || "?"}
            </div>
          )}
          <div className="min-w-0">
            <p className="truncate text-xs font-medium text-bean">
              {user?.displayName || "User"}
            </p>
            <p className="truncate text-[10px] text-latte">
              {user?.email}
            </p>
          </div>
        </div>
      </div>

      {deleteTarget && (
        <ConfirmDialog
          title="Delete conversation?"
          message="This conversation and its saved messages will be permanently deleted."
          confirmLabel="Delete"
          onConfirm={handleDeleteConfirm}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </aside>
  );
}

function MobileHeader({
  activeSection,
  onNewChat,
}: {
  activeSection: Section;
  onNewChat: () => void;
}) {
  return (
    <header className="flex h-14 items-center justify-between border-b border-stone/50 bg-marble/80 px-4 backdrop-blur-md md:hidden">
      <div className="flex items-center gap-2.5">
        <img
          src="/coffee-logo.png"
          alt="Grounded logo"
          className="h-7 w-7 rounded-lg object-cover"
        />
        <span className="text-xs font-semibold tracking-widest uppercase text-espresso">
          Grounded
        </span>
      </div>
      {activeSection === "chat" && (
        <button
          onClick={onNewChat}
          className="flex h-8 w-8 items-center justify-center rounded-lg text-espresso transition-colors hover:bg-cream/50"
          aria-label="New chat"
        >
          <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M12 5v14M5 12h14" />
          </svg>
        </button>
      )}
    </header>
  );
}

function MobileBottomNav({
  activeSection,
  onNavigate,
}: {
  activeSection: Section;
  onNavigate: (s: Section) => void;
}) {
  return (
    <nav className="flex h-14 flex-shrink-0 items-center border-t border-stone/50 bg-marble/80 backdrop-blur-md md:hidden" role="navigation" aria-label="Main navigation">
      {(["chat", "history", "profile"] as Section[]).map((s) => (
        <button
          key={s}
          onClick={() => onNavigate(s)}
          className={`flex flex-1 flex-col items-center justify-center gap-0.5 py-2 text-[10px] font-medium transition-colors ${
            activeSection === s ? "text-espresso" : "text-latte"
          }`}
          aria-current={activeSection === s ? "page" : undefined}
        >
          {s === "chat" && (
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
            </svg>
          )}
          {s === "history" && (
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" />
              <path d="M12 6v6l3 3" />
            </svg>
          )}
          {s === "profile" && (
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="8" r="4" />
              <path d="M20 21a8 8 0 1 0-16 0" />
            </svg>
          )}
          {s.charAt(0).toUpperCase() + s.slice(1)}
        </button>
      ))}
    </nav>
  );
}

export function AuthenticatedApp() {
  const [activeSection, setActiveSection] = useState<Section>("chat");
  const { startNewChat, error, clearError } = useConversations();

  const handleNewChat = useCallback(() => {
    startNewChat();
    setActiveSection("chat");
  }, [startNewChat]);

  const handleNavigate = useCallback((s: Section) => {
    setActiveSection(s);
  }, []);

  const handleHistorySelect = useCallback(() => {
    setActiveSection("chat");
  }, []);

  return (
    <div className="flex h-dvh flex-col overflow-hidden marble-bg marble-veins md:h-screen md:flex-row md:overflow-visible">
      <SidebarNav
        activeSection={activeSection}
        onNavigate={handleNavigate}
        onNewChat={handleNewChat}
      />
      <MobileHeader activeSection={activeSection} onNewChat={handleNewChat} />

      <main className="min-h-0 flex-1 overflow-hidden">
        {activeSection === "chat" && <ChatView />}
        {activeSection === "history" && <HistoryView onSelect={handleHistorySelect} />}
        {activeSection === "profile" && <ProfileView />}
      </main>

      <MobileBottomNav activeSection={activeSection} onNavigate={handleNavigate} />

      {error && <ErrorToast message={error} onDismiss={clearError} />}
      <WakeUpToast />
    </div>
  );
}

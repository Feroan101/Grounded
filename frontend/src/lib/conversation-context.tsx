"use client";

import {
  createContext,
  useContext,
  useState,
  useCallback,
  useEffect,
  useRef,
  ReactNode,
} from "react";
import {
  collection,
  doc,
  setDoc,
  deleteDoc,
  onSnapshot,
  orderBy,
  query,
  serverTimestamp,
} from "firebase/firestore";
import { useAuth } from "./auth-context";
import { useProfile } from "./profile-context";
import { useBackendReadiness } from "./backend-readiness";
import { getFirebaseFirestore } from "./firebase";
import { sendChatMessage } from "./api";
import { friendlyActivity, ACTIVITY_STARTING } from "./activity-labels";

const MIN_ACTIVITY_GAP_MS = 150;

export interface Message {
  role: "user" | "assistant";
  content: string;
}

export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
}

interface ConversationContextValue {
  conversations: Conversation[];
  loading: boolean;
  error: string | null;
  activeConversationId: string | null;
  activeConversation: Conversation | undefined;
  isSending: boolean;
  activity: string | null;
  startNewChat: () => void;
  setActiveConversation: (id: string | null) => void;
  sendMessage: (content: string) => Promise<void>;
  regenerate: () => Promise<void>;
  deleteConversation: (id: string) => Promise<void>;
  renameConversation: (id: string, newTitle: string) => Promise<void>;
  clearError: () => void;
}

const ConversationContext = createContext<ConversationContextValue | null>(null);

export function useConversations() {
  const ctx = useContext(ConversationContext);
  if (!ctx) throw new Error("useConversations must be used within ConversationProvider");
  return ctx;
}

let nextId = 1;
function genId() {
  return `conv_${Date.now()}_${nextId++}`;
}

function deriveTitle(messages: Message[]): string {
  const firstUser = messages.find((m) => m.role === "user");
  if (firstUser) {
    const text = firstUser.content;
    return text.length > 40 ? text.slice(0, 40) + "..." : text;
  }
  return "New conversation";
}

function conversationsPath(uid: string) {
  return `users/${uid}/conversations`;
}

export function ConversationProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { conversationHistoryEnabled } = useProfile();
  const { status: backendStatus, setStatus: setBackendStatus } = useBackendReadiness();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const [activity, setActivity] = useState<string | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const activeIdRef = useRef<string | null>(null);
  const historyEnabledRef = useRef(conversationHistoryEnabled);
  const sendingRef = useRef(false);
  const hasConnectedRef = useRef(false);
  const lastActivityAtRef = useRef(0);
  const currentActivityRef = useRef<string | null>(null);

  const applyActivity = useCallback((label: string | null) => {
    if (label === null) {
      currentActivityRef.current = null;
      setActivity(null);
      return;
    }
    const now = Date.now();
    // Suppress flicker: ignore the same label repeated within a short window,
    // but always surface a real change and always clear to null.
    if (
      currentActivityRef.current === label &&
      now - lastActivityAtRef.current < MIN_ACTIVITY_GAP_MS
    ) {
      return;
    }
    lastActivityAtRef.current = now;
    currentActivityRef.current = label;
    setActivity(label);
  }, []);

  useEffect(() => {
    activeIdRef.current = activeConversationId;
  }, [activeConversationId]);

  useEffect(() => {
    historyEnabledRef.current = conversationHistoryEnabled;
  }, [conversationHistoryEnabled]);

  const activeConversation = conversations.find((c) => c.id === activeConversationId);

  const prevUserRef = useRef(user);

  useEffect(() => {
    const prevUser = prevUserRef.current;
    prevUserRef.current = user;

    if (prevUser && !user) {
      setConversations([]);
      setActiveConversationId(null);
      setLoading(false);
      setError(null);
      return;
    }

    if (!user) return;

    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }

    const db = getFirebaseFirestore();
    const convQuery = query(
      collection(db, conversationsPath(user.uid)),
      orderBy("createdAt", "desc")
    );

    let hasLoaded = false;

    const unsubscribe = onSnapshot(
      convQuery,
      (snapshot) => {
        const convs: Conversation[] = snapshot.docs.map((d) => {
          const data = d.data();
          return {
            id: d.id,
            title: data.title || "New conversation",
            messages: data.messages || [],
            createdAt: data.createdAt?.toMillis?.() || Date.now(),
          };
        });
        setConversations(convs);
        if (!hasLoaded) {
          hasLoaded = true;
          setLoading(false);
          setError(null);
        }
      },
      (err) => {
        console.error("Firestore listener error:", err);
        setError("Couldn't load your conversations. Please try again.");
        setLoading(false);
      }
    );

    unsubscribeRef.current = unsubscribe;

    return () => {
      unsubscribe();
      unsubscribeRef.current = null;
    };
  }, [user]);

  const clearError = useCallback(() => setError(null), []);

  const startNewChat = useCallback(() => {
    activeIdRef.current = null;
    setActiveConversationId(null);
  }, []);

  const persistConversation = useCallback(
    (id: string, title: string, messages: Message[]) => {
      if (!user || !historyEnabledRef.current) return;
      const db = getFirebaseFirestore();
      setDoc(doc(db, conversationsPath(user.uid), id), {
        title,
        messages,
        createdAt: serverTimestamp(),
      }).catch((err) => {
        console.error("Failed to save conversation to Firestore:", err);
      });
    },
    [user]
  );

  const sendToAgent = useCallback(
    async (convId: string, payloadMessages: Message[]) => {
      let idToken: string;
      try {
        idToken = await user!.getIdToken();
      } catch {
        setError("Couldn't reach your account. Please sign in again.");
        setBackendStatus((prev) => (prev === "waking" ? "failed" : prev));
        sendingRef.current = false;
        setIsSending(false);
        applyActivity(null);
        return;
      }

      let assistantText: string;
      try {
        const result = await sendChatMessage({
          messages: payloadMessages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
          conversationId: convId,
          idToken,
          onActivity: (event) => applyActivity(friendlyActivity(event)),
        });
        assistantText = result.answer;
      } catch (err) {
        const message =
          err instanceof Error && err.message
            ? err.message
            : "Something went wrong while preparing the response.";
        setError(message);
        setBackendStatus((prev) => (prev === "waking" ? "failed" : prev));
        sendingRef.current = false;
        setIsSending(false);
        applyActivity(null);
        return;
      }

      const assistantMsg: Message = { role: "assistant", content: assistantText };

      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== convId) return c;
          return { ...c, messages: [...c.messages, assistantMsg] };
        })
      );

      setConversations((prev) => {
        const target = prev.find((c) => c.id === convId);
        if (target) {
          persistConversation(convId, target.title, target.messages);
        }
        return prev;
      });

      // First successful backend contact: the readiness check passed.
      setBackendStatus((prev) => (prev === "waking" ? "ready" : prev));
      applyActivity(null);

      sendingRef.current = false;
      setIsSending(false);
    },
    [user, persistConversation, setBackendStatus, applyActivity]
  );

  const sendMessage = useCallback(
    async (content: string) => {
      if (!user || sendingRef.current) return;
      sendingRef.current = true;
      setIsSending(true);
      setError(null);
      applyActivity(ACTIVITY_STARTING);

      // The first real POST /api/chat acts as the backend readiness check.
      // Surface the wake-up status so the UI can tell the customer the
      // backend may still be starting up. A retry after a connection failure
      // re-enters the waking state so a later success can move to "ready".
      if (!hasConnectedRef.current) {
        hasConnectedRef.current = true;
        setBackendStatus("waking");
      } else if (backendStatus === "failed") {
        setBackendStatus("waking");
      }

      const userMsg: Message = { role: "user", content };

      let convId = activeIdRef.current;

      if (!convId) {
        convId = genId();
        const conv: Conversation = {
          id: convId,
          title: "New conversation",
          messages: [],
          createdAt: Date.now(),
        };
        setConversations((prev) => [conv, ...prev]);
        setActiveConversationId(convId);
        activeIdRef.current = convId;
        persistConversation(convId, deriveTitle([userMsg]), [userMsg]);
      }

      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== convId) return c;
          const newMessages = [...c.messages, userMsg];
          return {
            ...c,
            title: deriveTitle(newMessages),
            messages: newMessages,
          };
        })
      );

      const payloadMessages = [...(activeConversation?.messages ?? []), userMsg];

      await sendToAgent(convId, payloadMessages);
    },
    [
      user,
      activeConversation,
      backendStatus,
      setBackendStatus,
      applyActivity,
      persistConversation,
      sendToAgent,
    ]
  );

  const regenerate = useCallback(async () => {
    if (!user || sendingRef.current || !activeConversation) return;

    // Re-run the last exchange: drop the trailing assistant replies and send
    // the conversation up to and including the latest customer message again.
    const convId = activeConversation.id;
    let lastUserIndex = -1;
    for (let idx = activeConversation.messages.length - 1; idx >= 0; idx--) {
      if (activeConversation.messages[idx].role === "user") {
        lastUserIndex = idx;
        break;
      }
    }
    if (lastUserIndex < 0) return;

    sendingRef.current = true;
    setIsSending(true);
    setError(null);
    applyActivity(ACTIVITY_STARTING);

    if (!hasConnectedRef.current) {
      hasConnectedRef.current = true;
      setBackendStatus("waking");
    } else if (backendStatus === "failed") {
      setBackendStatus("waking");
    }

    const truncated = activeConversation.messages.slice(0, lastUserIndex + 1);

    setConversations((prev) =>
      prev.map((c) => (c.id === convId ? { ...c, messages: truncated } : c))
    );

    setConversations((prev) => {
      const target = prev.find((c) => c.id === convId);
      if (target) {
        persistConversation(convId, target.title, target.messages);
      }
      return prev;
    });

    await sendToAgent(convId, truncated);
  }, [
    user,
    activeConversation,
    backendStatus,
    setBackendStatus,
    applyActivity,
    persistConversation,
    sendToAgent,
  ]);

  const deleteConversation = useCallback(
    async (id: string) => {
      const prevConversations = conversations;
      const wasActive = activeConversationId === id;

      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (wasActive) {
        setActiveConversationId(null);
      }

      if (user) {
        try {
          const db = getFirebaseFirestore();
          await deleteDoc(doc(db, conversationsPath(user.uid), id));
        } catch (err) {
          console.error("Failed to delete conversation from Firestore:", err);
          setConversations(prevConversations);
          if (wasActive) {
            setActiveConversationId(id);
          }
          setError("Couldn't delete this conversation. Please try again.");
        }
      }
    },
    [activeConversationId, user, conversations]
  );

  const renameConversation = useCallback(
    async (id: string, newTitle: string) => {
      const trimmed = newTitle.trim() || "Untitled conversation";
      const prevConversations = conversations;

      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: trimmed } : c))
      );

      if (user) {
        try {
          const db = getFirebaseFirestore();
          const convRef = doc(db, conversationsPath(user.uid), id);
          await setDoc(convRef, { title: trimmed }, { merge: true });
        } catch (err) {
          console.error("Failed to rename conversation in Firestore:", err);
          setConversations(prevConversations);
          setError("Couldn't rename this conversation. Please try again.");
        }
      }
    },
    [user, conversations]
  );

  return (
    <ConversationContext.Provider
      value={{
        conversations,
        loading,
        error,
        activeConversationId,
        activeConversation,
        isSending,
        activity,
        startNewChat,
        setActiveConversation: setActiveConversationId,
        sendMessage,
        regenerate,
        deleteConversation,
        renameConversation,
        clearError,
      }}
    >
      {children}
    </ConversationContext.Provider>
  );
}

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
  startNewChat: () => void;
  setActiveConversation: (id: string | null) => void;
  sendMessage: (content: string) => Promise<void>;
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
  const { setStatus: setBackendStatus } = useBackendReadiness();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [isSending, setIsSending] = useState(false);
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const activeIdRef = useRef<string | null>(null);
  const historyEnabledRef = useRef(conversationHistoryEnabled);
  const sendingRef = useRef(false);
  const hasConnectedRef = useRef(false);

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

  const sendMessage = useCallback(
    async (content: string) => {
      if (!user || sendingRef.current) return;
      sendingRef.current = true;
      setIsSending(true);
      setError(null);

      // The first real POST /api/chat acts as the backend readiness check.
      // Surface the wake-up status so the UI can tell the customer the
      // backend may still be starting up.
      if (!hasConnectedRef.current) {
        hasConnectedRef.current = true;
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

      let idToken: string;
      try {
        idToken = await user.getIdToken();
      } catch {
        setError("Couldn't reach your account. Please sign in again.");
        setBackendStatus((prev) => (prev === "waking" ? "failed" : prev));
        sendingRef.current = false;
        setIsSending(false);
        return;
      }

      const payloadMessages = [...(activeConversation?.messages ?? []), userMsg];

      let assistantText: string;
      try {
        const result = await sendChatMessage({
          messages: payloadMessages.map((m) => ({
            role: m.role,
            content: m.content,
          })),
          conversationId: convId,
          idToken,
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

      sendingRef.current = false;
      setIsSending(false);
    },
    [user, persistConversation, activeConversation, setBackendStatus]
  );

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
        startNewChat,
        setActiveConversation: setActiveConversationId,
        sendMessage,
        deleteConversation,
        renameConversation,
        clearError,
      }}
    >
      {children}
    </ConversationContext.Provider>
  );
}

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
import { getFirebaseFirestore } from "./firebase";

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
  startNewChat: () => void;
  setActiveConversation: (id: string | null) => void;
  sendMessage: (content: string) => void;
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

function fakeAssistantResponse(): string {
  const responses = [
    "I'd love to help you find the perfect coffee. What are you in the mood for today?",
    "Great choice! Let me think about what would suit you best based on what you've told me.",
    "Interesting! Based on your preferences, I have a few ideas. Let me walk you through them.",
    "That's a popular request! Here's what I'd suggest for you right now.",
    "I know just the thing. Let me pull up a couple of options that match your taste.",
  ];
  return responses[Math.floor(Math.random() * responses.length)];
}

function conversationsPath(uid: string) {
  return `users/${uid}/conversations`;
}

export function ConversationProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const { conversationHistoryEnabled } = useProfile();
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const activeIdRef = useRef<string | null>(null);
  const historyEnabledRef = useRef(conversationHistoryEnabled);

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
    (content: string) => {
      if (!user) return;

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
          const updatedConv = {
            ...c,
            title: deriveTitle(newMessages),
            messages: newMessages,
          };
          return updatedConv;
        })
      );

      setTimeout(() => {
        const assistantMsg: Message = {
          role: "assistant",
          content: fakeAssistantResponse(),
        };

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
      }, 1500);
    },
    [user, persistConversation]
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

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
  activeConversationId: string | null;
  activeConversation: Conversation | undefined;
  createConversation: () => string;
  setActiveConversation: (id: string | null) => void;
  sendMessage: (content: string) => void;
  deleteConversation: (id: string) => void;
  renameConversation: (id: string, newTitle: string) => void;
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
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const activeIdRef = useRef<string | null>(null);

  // Keep ref in sync with state via effect
  useEffect(() => {
    activeIdRef.current = activeConversationId;
  }, [activeConversationId]);

  const activeConversation = conversations.find((c) => c.id === activeConversationId);

  // Clear state when user signs out
  useEffect(() => {
    if (user) return;
    setConversations([]);
    setLoading(false);
  }, [user]);

  // Subscribe to user's conversations from Firestore
  useEffect(() => {
    if (!user) return;

    // Clean up previous listener
    if (unsubscribeRef.current) {
      unsubscribeRef.current();
      unsubscribeRef.current = null;
    }

    setLoading(true);
    const db = getFirebaseFirestore();
    const convQuery = query(
      collection(db, conversationsPath(user.uid)),
      orderBy("createdAt", "desc")
    );

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
        setLoading(false);
      },
      (error) => {
        console.error("Firestore listener error:", error);
        setLoading(false);
      }
    );

    unsubscribeRef.current = unsubscribe;

    return () => {
      unsubscribe();
      unsubscribeRef.current = null;
    };
  }, [user]);

  const createConversation = useCallback(() => {
    if (!user) return "";
    const id = genId();
    const conv: Conversation = {
      id,
      title: "New conversation",
      messages: [],
      createdAt: Date.now(),
    };

    // Optimistic UI update
    setConversations((prev) => [conv, ...prev]);
    setActiveConversationId(id);

    // Persist to Firestore
    const db = getFirebaseFirestore();
    setDoc(doc(db, conversationsPath(user.uid), id), {
      title: conv.title,
      messages: conv.messages,
      createdAt: serverTimestamp(),
    }).catch((err) => {
      console.error("Failed to create conversation in Firestore:", err);
    });

    return id;
  }, [user]);

  const sendMessage = useCallback(
    (content: string) => {
      const convId = activeIdRef.current;
      if (!convId || !user) return;

      const userMsg: Message = { role: "user", content };

      // Add user message to state immediately
      setConversations((prev) =>
        prev.map((c) => {
          if (c.id !== convId) return c;
          const newMessages = [...c.messages, userMsg];
          return { ...c, title: deriveTitle(newMessages), messages: newMessages };
        })
      );

      // Simulate assistant response, then persist both messages
      setTimeout(() => {
        const assistantMsg: Message = {
          role: "assistant",
          content: fakeAssistantResponse(),
        };

        setConversations((prev) => {
          const updated = prev.map((c) => {
            if (c.id !== convId) return c;
            const newMessages = [...c.messages, userMsg, assistantMsg];
            const updatedConv = { ...c, messages: newMessages };

            // Persist the full conversation to Firestore
            const db = getFirebaseFirestore();
            setDoc(doc(db, conversationsPath(user.uid), convId), {
              title: updatedConv.title,
              messages: updatedConv.messages,
              createdAt: serverTimestamp(),
            }).catch((err) => {
              console.error("Failed to save conversation to Firestore:", err);
            });

            return updatedConv;
          });
          return updated;
        });
      }, 1500);
    },
    [user]
  );

  const deleteConversation = useCallback(
    (id: string) => {
      setConversations((prev) => prev.filter((c) => c.id !== id));
      if (activeConversationId === id) {
        setActiveConversationId(null);
      }

      // Delete from Firestore
      if (user) {
        const db = getFirebaseFirestore();
        deleteDoc(doc(db, conversationsPath(user.uid), id)).catch((err) => {
          console.error("Failed to delete conversation from Firestore:", err);
        });
      }
    },
    [activeConversationId, user]
  );

  const renameConversation = useCallback(
    (id: string, newTitle: string) => {
      const trimmed = newTitle.trim() || "Untitled conversation";

      // Update React state
      setConversations((prev) =>
        prev.map((c) => (c.id === id ? { ...c, title: trimmed } : c))
      );

      // Persist to Firestore
      if (user) {
        const db = getFirebaseFirestore();
        const convRef = doc(db, conversationsPath(user.uid), id);
        setDoc(convRef, { title: trimmed }, { merge: true }).catch((err) => {
          console.error("Failed to rename conversation in Firestore:", err);
        });
      }
    },
    [user]
  );

  return (
    <ConversationContext.Provider
      value={{
        conversations,
        loading,
        activeConversationId,
        activeConversation,
        createConversation,
        setActiveConversation: setActiveConversationId,
        sendMessage,
        deleteConversation,
        renameConversation,
      }}
    >
      {children}
    </ConversationContext.Provider>
  );
}

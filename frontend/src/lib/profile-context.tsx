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
  doc,
  setDoc,
  deleteDoc,
  onSnapshot,
  collection,
  serverTimestamp,
  getDocs,
} from "firebase/firestore";
import { useAuth } from "./auth-context";
import { getFirebaseFirestore } from "./firebase";

export interface CoffeePreferences {
  favoriteDrink: string;
  temperature: "hot" | "iced" | "either";
  milkPreference: string;
  sweetness: string;
  strength: string;
  caffeinePreference: string;
  roastPreference: string;
  brewMethod: string;
  dietaryPreference: string[];
  allergiesOrIntolerances: string;
}

export interface AIContext {
  customContext: string;
  responseStyle: "short" | "balanced" | "detailed";
  tone: "friendly" | "casual" | "professional" | "playful";
  recommendationStyle: "best" | "few" | "explain";
  usePreferencesInConversations: boolean;
}

export interface Memory {
  id: string;
  text: string;
  createdAt: number;
  updatedAt: number;
}

export interface ProfileState {
  coffee: CoffeePreferences;
  aiContext: AIContext;
  memories: Memory[];
  conversationHistoryEnabled: boolean;
  loading: boolean;
  saving: boolean;
}

interface ProfileContextValue extends ProfileState {
  updateCoffee: (prefs: Partial<CoffeePreferences>) => Promise<void>;
  updateAIContext: (ctx: Partial<AIContext>) => Promise<void>;
  updateConversationHistory: (enabled: boolean) => Promise<void>;
  addMemory: (text: string) => Promise<void>;
  updateMemory: (id: string, text: string) => Promise<void>;
  deleteMemory: (id: string) => Promise<void>;
  clearAllMemories: () => Promise<void>;
  clearConversationHistory: () => Promise<void>;
}

const defaultCoffee: CoffeePreferences = {
  favoriteDrink: "",
  temperature: "either",
  milkPreference: "",
  sweetness: "",
  strength: "",
  caffeinePreference: "",
  roastPreference: "",
  brewMethod: "",
  dietaryPreference: [],
  allergiesOrIntolerances: "",
};

const defaultAIContext: AIContext = {
  customContext: "",
  responseStyle: "balanced",
  tone: "friendly",
  recommendationStyle: "best",
  usePreferencesInConversations: true,
};

const ProfileContext = createContext<ProfileContextValue | null>(null);

export function useProfile() {
  const ctx = useContext(ProfileContext);
  if (!ctx) throw new Error("useProfile must be used within ProfileProvider");
  return ctx;
}

function preferencesPath(uid: string) {
  return `users/${uid}/preferences/current`;
}

function memoriesPath(uid: string) {
  return `users/${uid}/memories`;
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [coffee, setCoffee] = useState<CoffeePreferences>(defaultCoffee);
  const [aiContext, setAIContext] = useState<AIContext>(defaultAIContext);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [conversationHistoryEnabled, setConversationHistoryEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const unsubscribePrefsRef = useRef<(() => void) | null>(null);
  const unsubscribeMemoriesRef = useRef<(() => void) | null>(null);
  const prevUserRef = useRef(user);

  useEffect(() => {
    const prevUser = prevUserRef.current;
    prevUserRef.current = user;

    if (prevUser && !user) {
      setCoffee(defaultCoffee);
      setAIContext(defaultAIContext);
      setMemories([]);
      setConversationHistoryEnabled(true);
      setLoading(false);
      return;
    }

    if (!user) return;

    if (unsubscribePrefsRef.current) {
      unsubscribePrefsRef.current();
      unsubscribePrefsRef.current = null;
    }
    if (unsubscribeMemoriesRef.current) {
      unsubscribeMemoriesRef.current();
      unsubscribeMemoriesRef.current = null;
    }

    const db = getFirebaseFirestore();
    let hasLoaded = false;

    const unsubPrefs = onSnapshot(
      doc(db, preferencesPath(user.uid)),
      (snapshot) => {
        if (snapshot.exists()) {
          const data = snapshot.data();
          if (data.coffee) setCoffee({ ...defaultCoffee, ...data.coffee });
          if (data.aiContext) setAIContext({ ...defaultAIContext, ...data.aiContext });
          if (data.conversationHistoryEnabled !== undefined) {
            setConversationHistoryEnabled(data.conversationHistoryEnabled);
          }
        }
        if (!hasLoaded) {
          hasLoaded = true;
          setLoading(false);
        }
      },
      (err) => {
        console.error("Failed to load preferences:", err);
        if (!hasLoaded) {
          hasLoaded = true;
          setLoading(false);
        }
      }
    );

    const unsubMemories = onSnapshot(
      collection(db, memoriesPath(user.uid)),
      (snapshot) => {
        const mems: Memory[] = snapshot.docs.map((d) => {
          const data = d.data();
          return {
            id: d.id,
            text: data.text || "",
            createdAt: data.createdAt?.toMillis?.() || Date.now(),
            updatedAt: data.updatedAt?.toMillis?.() || Date.now(),
          };
        });
        mems.sort((a, b) => b.createdAt - a.createdAt);
        setMemories(mems);
      },
      (err) => {
        console.error("Failed to load memories:", err);
      }
    );

    unsubscribePrefsRef.current = unsubPrefs;
    unsubscribeMemoriesRef.current = unsubMemories;

    return () => {
      unsubPrefs();
      unsubMemories();
      unsubscribePrefsRef.current = null;
      unsubscribeMemoriesRef.current = null;
    };
  }, [user]);

  const updateCoffee = useCallback(
    async (prefs: Partial<CoffeePreferences>) => {
      if (!user) return;
      setSaving(true);
      try {
        const db = getFirebaseFirestore();
        const updated = { ...coffee, ...prefs };
        await setDoc(doc(db, preferencesPath(user.uid)), { coffee: updated }, { merge: true });
        setCoffee(updated);
      } catch (err) {
        console.error("Failed to save coffee preferences:", err);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [user, coffee]
  );

  const updateAIContext = useCallback(
    async (ctx: Partial<AIContext>) => {
      if (!user) return;
      setSaving(true);
      try {
        const db = getFirebaseFirestore();
        const updated = { ...aiContext, ...ctx };
        await setDoc(doc(db, preferencesPath(user.uid)), { aiContext: updated }, { merge: true });
        setAIContext(updated);
      } catch (err) {
        console.error("Failed to save AI context:", err);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [user, aiContext]
  );

  const updateConversationHistory = useCallback(
    async (enabled: boolean) => {
      if (!user) return;
      setSaving(true);
      try {
        const db = getFirebaseFirestore();
        await setDoc(doc(db, preferencesPath(user.uid)), { conversationHistoryEnabled: enabled }, { merge: true });
        setConversationHistoryEnabled(enabled);
      } catch (err) {
        console.error("Failed to save conversation history preference:", err);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [user]
  );

  const addMemory = useCallback(
    async (text: string) => {
      if (!user) return;
      setSaving(true);
      try {
        const db = getFirebaseFirestore();
        const memRef = doc(collection(db, memoriesPath(user.uid)));
        await setDoc(memRef, {
          text,
          createdAt: serverTimestamp(),
          updatedAt: serverTimestamp(),
        });
      } catch (err) {
        console.error("Failed to add memory:", err);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [user]
  );

  const updateMemory = useCallback(
    async (id: string, text: string) => {
      if (!user) return;
      setSaving(true);
      try {
        const db = getFirebaseFirestore();
        await setDoc(
          doc(db, memoriesPath(user.uid), id),
          { text, updatedAt: serverTimestamp() },
          { merge: true }
        );
      } catch (err) {
        console.error("Failed to update memory:", err);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [user]
  );

  const deleteMemory = useCallback(
    async (id: string) => {
      if (!user) return;
      setSaving(true);
      try {
        const db = getFirebaseFirestore();
        await deleteDoc(doc(db, memoriesPath(user.uid), id));
      } catch (err) {
        console.error("Failed to delete memory:", err);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [user]
  );

  const clearAllMemories = useCallback(async () => {
    if (!user) return;
    setSaving(true);
    try {
      const db = getFirebaseFirestore();
      const promises = memories.map((m) => deleteDoc(doc(db, memoriesPath(user.uid), m.id)));
      await Promise.all(promises);
    } catch (err) {
      console.error("Failed to clear memories:", err);
      throw err;
    } finally {
      setSaving(false);
    }
  }, [user, memories]);

  const clearConversationHistory = useCallback(async () => {
    if (!user) return;
    setSaving(true);
    try {
      const db = getFirebaseFirestore();
      const convSnapshot = await getDocs(collection(db, `users/${user.uid}/conversations`));
      const deletePromises = convSnapshot.docs.map((d) => deleteDoc(d.ref));
      await Promise.all(deletePromises);
    } catch (err) {
      console.error("Failed to clear conversation history:", err);
      throw err;
    } finally {
      setSaving(false);
    }
  }, [user]);

  return (
    <ProfileContext.Provider
      value={{
        coffee,
        aiContext,
        memories,
        conversationHistoryEnabled,
        loading,
        saving,
        updateCoffee,
        updateAIContext,
        updateConversationHistory,
        addMemory,
        updateMemory,
        deleteMemory,
        clearAllMemories,
        clearConversationHistory,
      }}
    >
      {children}
    </ProfileContext.Provider>
  );
}

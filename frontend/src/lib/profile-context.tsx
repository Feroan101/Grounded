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
import {
  getUserPreferences,
  updateUserPreferences,
  ApiUserPreferences,
} from "./api";

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

function memoriesPath(uid: string) {
  return `users/${uid}/memories`;
}

function applyUserPreferences(data: ApiUserPreferences | undefined, setters: {
  setCoffee: (v: CoffeePreferences) => void;
  setAIContext: (v: AIContext) => void;
  setConversationHistoryEnabled: (v: boolean) => void;
}) {
  setters.setCoffee({ ...defaultCoffee, ...data?.coffee });
  setters.setAIContext({ ...defaultAIContext, ...data?.aiContext });
  setters.setConversationHistoryEnabled(data?.conversationHistoryEnabled ?? true);
}

export function ProfileProvider({ children }: { children: ReactNode }) {
  const { user } = useAuth();
  const [coffee, setCoffee] = useState<CoffeePreferences>(defaultCoffee);
  const [aiContext, setAIContext] = useState<AIContext>(defaultAIContext);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [conversationHistoryEnabled, setConversationHistoryEnabled] = useState(true);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const unsubscribeMemoriesRef = useRef<(() => void) | null>(null);
  const prefsRequestRef = useRef(0);
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

    if (unsubscribeMemoriesRef.current) {
      unsubscribeMemoriesRef.current();
      unsubscribeMemoriesRef.current = null;
    }

    const requestId = ++prefsRequestRef.current;
    const loadPreferences = async () => {
      const idToken = await user.getIdToken();
      if (prefsRequestRef.current !== requestId) return;
      setLoading(true);
      try {
        const data = await getUserPreferences({ idToken });
        if (prefsRequestRef.current !== requestId) return;
        applyUserPreferences(data, { setCoffee, setAIContext, setConversationHistoryEnabled });
      } catch (err) {
        console.error("Failed to load preferences:", err);
      } finally {
        if (prefsRequestRef.current === requestId) setLoading(false);
      }
    };
    loadPreferences();

    const db = getFirebaseFirestore();
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

    unsubscribeMemoriesRef.current = unsubMemories;

    return () => {
      unsubMemories();
      unsubscribeMemoriesRef.current = null;
    };
  }, [user]);

  const updateCoffee = useCallback(
    async (prefs: Partial<CoffeePreferences>) => {
      if (!user) return;
      setSaving(true);
      try {
        const idToken = await user.getIdToken();
        const result = await updateUserPreferences({
          idToken,
          updates: { coffee: prefs },
        });
        setCoffee({ ...defaultCoffee, ...result.coffee });
      } catch (err) {
        console.error("Failed to save coffee preferences:", err);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [user]
  );

  const updateAIContext = useCallback(
    async (ctx: Partial<AIContext>) => {
      if (!user) return;
      setSaving(true);
      try {
        const idToken = await user.getIdToken();
        const result = await updateUserPreferences({
          idToken,
          updates: { aiContext: ctx },
        });
        setAIContext({ ...defaultAIContext, ...result.aiContext });
      } catch (err) {
        console.error("Failed to save AI context:", err);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [user]
  );

  const updateConversationHistory = useCallback(
    async (enabled: boolean) => {
      if (!user) return;
      setSaving(true);
      try {
        const idToken = await user.getIdToken();
        const result = await updateUserPreferences({
          idToken,
          updates: { conversationHistoryEnabled: enabled },
        });
        setConversationHistoryEnabled(result.conversationHistoryEnabled ?? enabled);
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
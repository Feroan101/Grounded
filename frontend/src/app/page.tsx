"use client";

import { useState } from "react";
import { GoogleAuthProvider, signInWithPopup, signOut } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import { useAuth } from "@/lib/auth-context";
import { apiGet } from "@/lib/api";

export default function Home() {
  const { user, loading } = useAuth();
  const [meData, setMeData] = useState<string>("");
  const [meError, setMeError] = useState<string>("");
  const [calling, setCalling] = useState(false);

  async function handleGoogleSignIn() {
    const provider = new GoogleAuthProvider();
    try {
      await signInWithPopup(getFirebaseAuth(), provider);
    } catch (err: any) {
      console.error("Sign-in error:", err);
    }
  }

  async function handleSignOut() {
    setMeData("");
    setMeError("");
    await signOut(getFirebaseAuth());
  }

  async function handleCallMe() {
    setCalling(true);
    setMeData("");
    setMeError("");
    try {
      const res = await apiGet("/api/me");
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setMeError(`HTTP ${res.status}: ${body?.detail || res.statusText}`);
        return;
      }
      const json = await res.json();
      setMeData(JSON.stringify(json, null, 2));
    } catch (err: any) {
      setMeError(err.message);
    } finally {
      setCalling(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-zinc-500">Loading...</p>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-zinc-50 dark:bg-zinc-950">
      <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white p-8 shadow-sm dark:border-zinc-800 dark:bg-zinc-900">
        <h1 className="mb-2 text-2xl font-bold">Grounded</h1>
        <p className="mb-6 text-sm text-zinc-500">Coffee that gets to know you.</p>

        {!user ? (
          <button
            onClick={handleGoogleSignIn}
            className="flex w-full items-center justify-center gap-3 rounded-lg border border-zinc-300 bg-white px-4 py-3 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-50 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-200 dark:hover:bg-zinc-700"
          >
            <svg className="h-5 w-5" viewBox="0 0 24 24">
              <path
                d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 0 1-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
                fill="#4285F4"
              />
              <path
                d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                fill="#34A853"
              />
              <path
                d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                fill="#FBBC05"
              />
              <path
                d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                fill="#EA4335"
              />
            </svg>
            Sign in with Google
          </button>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              {user.photoURL && (
                <img
                  src={user.photoURL}
                  alt=""
                  className="h-10 w-10 rounded-full"
                />
              )}
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user.displayName || user.email}</p>
                <p className="text-xs text-zinc-500 truncate">{user.uid}</p>
              </div>
              <button
                onClick={handleSignOut}
                className="text-xs text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
              >
                Sign out
              </button>
            </div>

            <button
              onClick={handleCallMe}
              disabled={calling}
              className="w-full rounded-lg bg-zinc-900 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-zinc-700 disabled:opacity-50 dark:bg-zinc-100 dark:text-zinc-900 dark:hover:bg-zinc-200"
            >
              {calling ? "Calling..." : "GET /api/me"}
            </button>

            {meData && (
              <pre className="rounded-lg bg-green-50 p-4 text-xs text-green-800 whitespace-pre-wrap dark:bg-green-950 dark:text-green-200">
                {meData}
              </pre>
            )}

            {meError && (
              <pre className="rounded-lg bg-red-50 p-4 text-xs text-red-700 whitespace-pre-wrap dark:bg-red-950 dark:text-red-300">
                {meError}
              </pre>
            )}
          </div>
        )}
      </div>
    </main>
  );
}

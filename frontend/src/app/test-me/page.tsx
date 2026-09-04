"use client";

import { useState } from "react";
import { GoogleAuthProvider, signInWithPopup, signOut } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";
import { useAuth } from "@/lib/auth-context";
import { apiGet } from "@/lib/api";

export default function TestMePage() {
  const { user, loading } = useAuth();
  const [data, setData] = useState<string>("");
  const [error, setError] = useState<string>("");
  const [calling, setCalling] = useState(false);

  async function handleGoogleSignIn() {
    const provider = new GoogleAuthProvider();
    await signInWithPopup(getFirebaseAuth(), provider);
  }

  async function handleCallMe() {
    setCalling(true);
    setData("");
    setError("");
    try {
      const res = await apiGet("/api/me");
      if (!res.ok) {
        const body = await res.json().catch(() => null);
        setError(`HTTP ${res.status}: ${body?.detail || res.statusText}`);
        return;
      }
      const json = await res.json();
      setData(JSON.stringify(json, null, 2));
    } catch (err: any) {
      setError(err.message);
    } finally {
      setCalling(false);
    }
  }

  if (loading) {
    return (
      <main className="min-h-screen p-8 font-sans">
        <p>Loading...</p>
      </main>
    );
  }

  return (
    <main className="min-h-screen p-8 font-sans max-w-xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">Test /api/me</h1>

      {!user ? (
        <div className="space-y-4">
          <p className="text-zinc-500">Sign in with Google first.</p>
          <button
            onClick={handleGoogleSignIn}
            className="rounded-lg border border-zinc-300 bg-white px-4 py-2 text-sm font-medium text-zinc-700 hover:bg-zinc-50"
          >
            Sign in with Google
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-zinc-600">
            Signed in as <strong>{user.email}</strong> ({user.uid})
          </p>

          <button
            onClick={handleCallMe}
            disabled={calling}
            className="rounded-lg bg-zinc-900 px-4 py-2 text-sm font-medium text-white hover:bg-zinc-700 disabled:opacity-50"
          >
            {calling ? "Calling..." : "GET /api/me"}
          </button>

          {data && (
            <pre className="rounded-lg bg-green-50 p-4 text-sm text-green-800 whitespace-pre-wrap">
              {data}
            </pre>
          )}

          {error && (
            <pre className="rounded-lg bg-red-50 p-4 text-sm text-red-700 whitespace-pre-wrap">
              {error}
            </pre>
          )}
        </div>
      )}
    </main>
  );
}

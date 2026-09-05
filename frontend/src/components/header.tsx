"use client";

import { useAuth } from "@/lib/auth-context";
import { GoogleAuthProvider, signInWithPopup, signOut } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";

export function Header() {
  const { user } = useAuth();

  async function handleGoogleSignIn() {
    const provider = new GoogleAuthProvider();
    try {
      await signInWithPopup(getFirebaseAuth(), provider);
    } catch (err) {
      console.error("Sign-in error:", err);
    }
  }

  async function handleSignOut() {
    await signOut(getFirebaseAuth());
  }

  return (
    <header className="sticky top-0 z-50 border-b border-stone/50 bg-marble/80 backdrop-blur-md">
      <div className="mx-auto flex h-16 max-w-3xl items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-3">
          <img
            src="/coffee-logo.png"
            alt="Grounded logo"
            className="h-8 w-8 rounded-lg object-cover"
          />
          <div>
            <h1 className="text-sm font-semibold tracking-widest text-espresso uppercase">
              Grounded
            </h1>
            <p className="hidden text-xs text-latte sm:block">
              Coffee that gets to know you.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-3">
          {user ? (
            <div className="flex items-center gap-3">
              <div className="hidden text-right sm:block">
                <p className="text-sm font-medium text-bean truncate max-w-[120px]">
                  {user.displayName || user.email}
                </p>
              </div>
              {user.photoURL ? (
                <button
                  onClick={handleSignOut}
                  className="group relative"
                  title="Sign out"
                >
                  <img
                    src={user.photoURL}
                    alt=""
                    className="h-9 w-9 rounded-full ring-2 ring-stone/50 transition-all group-hover:ring-espresso/50"
                  />
                  <div className="absolute inset-0 rounded-full bg-bean/0 transition-all group-hover:bg-bean/10" />
                </button>
              ) : (
                <button
                  onClick={handleSignOut}
                  className="text-xs text-latte transition-colors hover:text-espresso"
                >
                  Sign out
                </button>
              )}
            </div>
          ) : (
            <button
              onClick={handleGoogleSignIn}
              className="flex items-center gap-2 rounded-full border border-stone bg-ivory px-4 py-2 text-sm font-medium text-espresso transition-all hover:border-espresso/50 hover:shadow-sm"
            >
              <svg className="h-4 w-4" viewBox="0 0 24 24">
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
              Sign in
            </button>
          )}
        </div>
      </div>
    </header>
  );
}

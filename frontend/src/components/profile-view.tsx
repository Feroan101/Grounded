"use client";

import { useAuth } from "@/lib/auth-context";
import { signOut } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";

export function ProfileView() {
  const { user } = useAuth();

  async function handleSignOut() {
    await signOut(getFirebaseAuth());
  }

  return (
    <div className="mx-auto max-w-lg px-4 py-8 sm:px-6">
      {/* Avatar + name */}
      <div className="flex flex-col items-center text-center">
        {user?.photoURL ? (
          <img
            src={user.photoURL}
            alt=""
            className="h-20 w-20 rounded-full ring-4 ring-stone/50"
          />
        ) : (
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-espresso/10 text-3xl font-semibold text-espresso">
            {user?.displayName?.[0] || user?.email?.[0] || "?"}
          </div>
        )}

        <h2 className="mt-4 text-xl font-semibold text-espresso">
          {user?.displayName || "Grounded User"}
        </h2>
        <p className="mt-1 text-sm text-latte">
          {user?.email}
        </p>
      </div>

      {/* Account section */}
      <div className="mt-8 rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-4 text-xs font-medium uppercase tracking-wider text-latte/70">
          Account
        </h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between text-sm">
            <span className="text-bean">Name</span>
            <span className="text-latte">{user?.displayName || "—"}</span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-bean">Email</span>
            <span className="text-latte">{user?.email || "—"}</span>
          </div>
        </div>
      </div>

      {/* Sign out */}
      <button
        onClick={handleSignOut}
        className="mt-6 w-full rounded-xl border border-stone/50 bg-ivory px-4 py-3 text-sm font-medium text-bean transition-all hover:border-espresso/40 hover:bg-cream/50"
      >
        Sign out
      </button>
    </div>
  );
}

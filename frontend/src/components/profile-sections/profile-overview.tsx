"use client";

import { ReactNode } from "react";
import { useAuth } from "@/lib/auth-context";
import { useProfile } from "@/lib/profile-context";
import { ProfileSection } from "@/components/profile-view";
import {
  UserIcon,
  CoffeeIcon,
  BrainIcon,
  LightbulbIcon,
  PaletteIcon,
  ShieldIcon,
  ChevronRightIcon,
} from "@/components/profile-icons";

const DISPLAY_NAME_COOKIE = "grounded_display_name";

function getDisplayName(user: { displayName?: string | null; email?: string | null } | null) {
  if (typeof document === "undefined") return user?.displayName || "Grounded User";
  const match = document.cookie.split("; ").find((c) => c.startsWith(`${DISPLAY_NAME_COOKIE}=`));
  const custom = match ? decodeURIComponent(match.split("=")[1]) : "";
  return custom || user?.displayName || "Grounded User";
}

function SectionCard({
  icon,
  label,
  description,
  summary,
  onClick,
}: {
  icon: ReactNode;
  label: string;
  description: string;
  summary?: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="group flex w-full items-start gap-4 rounded-xl border border-stone/50 bg-ivory/80 p-4 text-left transition-all hover:border-espresso/30 hover:bg-ivory"
    >
      <span className="mt-0.5 flex-shrink-0 text-latte transition-colors group-hover:text-espresso">
        {icon}
      </span>
      <div className="min-w-0 flex-1">
        <h3 className="text-sm font-medium text-bean">{label}</h3>
        <p className="mt-0.5 text-xs text-latte">{description}</p>
        {summary && (
          <p className="mt-2 text-xs text-latte/70 line-clamp-1">{summary}</p>
        )}
      </div>
      <ChevronRightIcon className="mt-1 flex-shrink-0 text-latte/40 transition-colors group-hover:text-espresso/60" />
    </button>
  );
}

export function ProfileOverview({
  onNavigate,
}: {
  onNavigate: (section: ProfileSection) => void;
}) {
  const { user } = useAuth();
  const { coffee, aiContext, memories } = useProfile();

  const displayName = getDisplayName(user);

  const coffeeSummary = [
    coffee.favoriteDrink,
    coffee.milkPreference && `${coffee.milkPreference} milk`,
    coffee.sweetness && `${coffee.sweetness} sweet`,
  ]
    .filter(Boolean)
    .join(" / ") || "Not configured yet";

  const aiSummary = [
    aiContext.customContext ? "Custom context set" : null,
    `Response style: ${aiContext.responseStyle === "short" ? "Short" : aiContext.responseStyle === "detailed" ? "Detailed" : "Balanced"}`,
  ]
    .filter(Boolean)
    .join(" / ") || "Not configured yet";

  const memoryCount = memories.length;

  return (
    <div className="animate-fade-in">
      {/* Profile header */}
      <div className="mb-6 flex items-center gap-4">
        {user?.photoURL ? (
          <img
            src={user.photoURL}
            alt=""
            className="h-16 w-16 rounded-full ring-4 ring-stone/50"
          />
        ) : (
          <div className="flex h-16 w-16 items-center justify-center rounded-full bg-espresso/10 text-2xl font-semibold text-espresso">
            {displayName[0] || "?"}
          </div>
        )}
        <div>
          <h1 className="text-xl font-semibold text-espresso">{displayName}</h1>
          <p className="text-sm text-latte">{user?.email}</p>
        </div>
      </div>

      {/* Section cards */}
      <div className="space-y-2">
        <SectionCard
          icon={<UserIcon />}
          label="Your Profile"
          description="Account and display information"
          onClick={() => onNavigate("profile")}
        />
        <SectionCard
          icon={<CoffeeIcon />}
          label="Your Coffee"
          description="Preferences and usual order"
          summary={coffeeSummary}
          onClick={() => onNavigate("coffee")}
        />
        <SectionCard
          icon={<BrainIcon />}
          label="Know Me Better"
          description="Personalize conversations"
          summary={aiSummary}
          onClick={() => onNavigate("know-me")}
        />
        <SectionCard
          icon={<LightbulbIcon />}
          label="Grounded Remembers"
          description="Manage what Grounded knows"
          summary={memoryCount > 0 ? `${memoryCount} ${memoryCount === 1 ? "memory" : "memories"}` : "No memories yet"}
          onClick={() => onNavigate("memories")}
        />
        <SectionCard
          icon={<PaletteIcon />}
          label="Experience"
          description="Appearance and behavior"
          onClick={() => onNavigate("experience")}
        />
        <SectionCard
          icon={<ShieldIcon />}
          label="Privacy & Account"
          description="Cookies, history, data"
          onClick={() => onNavigate("privacy")}
        />
      </div>
    </div>
  );
}

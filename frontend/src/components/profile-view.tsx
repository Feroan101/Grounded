"use client";

import { useState, useCallback, ReactNode } from "react";
import { useProfile } from "@/lib/profile-context";
import { ProfileOverview } from "@/components/profile-sections/profile-overview";
import { YourProfileSection } from "@/components/profile-sections/your-profile";
import { YourCoffeeSection } from "@/components/profile-sections/your-coffee";
import { KnowMeBetterSection } from "@/components/profile-sections/know-me-better";
import { GroundedMemoriesSection } from "@/components/profile-sections/grounded-memories";
import { ExperienceSection } from "@/components/profile-sections/experience-settings";
import { PrivacyAccountSection } from "@/components/profile-sections/privacy-account";
import {
  UserIcon,
  CoffeeIcon,
  BrainIcon,
  LightbulbIcon,
  PaletteIcon,
  ShieldIcon,
  ChevronLeftIcon,
} from "@/components/profile-icons";

export type ProfileSection =
  | "overview"
  | "profile"
  | "coffee"
  | "know-me"
  | "memories"
  | "experience"
  | "privacy";

const sections: { id: ProfileSection; label: string; description: string; icon: ReactNode }[] = [
  { id: "profile", label: "Your Profile", description: "Account and display information", icon: <UserIcon className="h-5 w-5" /> },
  { id: "coffee", label: "Your Coffee", description: "Preferences and usual order", icon: <CoffeeIcon className="h-5 w-5" /> },
  { id: "know-me", label: "Know Me Better", description: "Personalize conversations", icon: <BrainIcon className="h-5 w-5" /> },
  { id: "memories", label: "Grounded Remembers", description: "Manage what Grounded knows", icon: <LightbulbIcon className="h-5 w-5" /> },
  { id: "experience", label: "Experience", description: "Appearance and behavior", icon: <PaletteIcon className="h-5 w-5" /> },
  { id: "privacy", label: "Privacy & Account", description: "Cookies, history, data", icon: <ShieldIcon className="h-5 w-5" /> },
];

function ProfileSidebar({
  activeSection,
  onNavigate,
}: {
  activeSection: ProfileSection;
  onNavigate: (section: ProfileSection) => void;
}) {
  return (
    <nav className="hidden md:block">
      <div className="mb-4 px-1">
        <h2 className="text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Settings
        </h2>
      </div>
      <div className="space-y-0.5">
        {sections.map((section) => (
          <button
            key={section.id}
            onClick={() => onNavigate(section.id)}
            className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-all ${
              activeSection === section.id
                ? "bg-espresso/10 text-espresso"
                : "text-latte hover:bg-cream/50 hover:text-bean"
            }`}
          >
            <span className={`flex-shrink-0 ${activeSection === section.id ? "text-espresso" : "text-latte"}`}>
              {section.icon}
            </span>
            <span className="text-sm font-medium">{section.label}</span>
          </button>
        ))}
      </div>
    </nav>
  );
}

function MobileSectionHeader({
  section,
  onBack,
}: {
  section: { label: string; icon: ReactNode };
  onBack: () => void;
}) {
  return (
    <div className="flex items-center gap-3 border-b border-stone/50 bg-marble/80 px-4 py-3 backdrop-blur-md md:hidden">
      <button
        onClick={onBack}
        className="flex h-8 w-8 items-center justify-center rounded-lg text-espresso transition-colors hover:bg-cream/50"
        aria-label="Back to profile"
      >
        <ChevronLeftIcon className="h-5 w-5" />
      </button>
      <span className="text-latte">{section.icon}</span>
      <h2 className="text-sm font-semibold text-espresso">{section.label}</h2>
    </div>
  );
}

function SectionContentInner({ section }: { section: ProfileSection }) {
  const { coffee, aiContext } = useProfile();

  switch (section) {
    case "profile":
      return <YourProfileSection />;
    case "coffee":
      return <YourCoffeeSection key={JSON.stringify(coffee)} />;
    case "know-me":
      return <KnowMeBetterSection key={JSON.stringify(aiContext)} />;
    case "memories":
      return <GroundedMemoriesSection />;
    case "experience":
      return <ExperienceSection />;
    case "privacy":
      return <PrivacyAccountSection />;
    default:
      return null;
  }
}

function SectionContent({ section }: { section: ProfileSection }) {
  return <SectionContentInner section={section} />;
}

export function ProfileViewInner() {
  const [activeSection, setActiveSection] = useState<ProfileSection>("overview");
  const activeSectionData = sections.find((s) => s.id === activeSection);

  const handleNavigate = useCallback((section: ProfileSection) => {
    setActiveSection(section);
  }, []);

  const handleBack = useCallback(() => {
    setActiveSection("overview");
  }, []);

  return (
    <div className="h-full overflow-y-auto">
      <div className="mx-auto max-w-5xl px-4 py-6 sm:px-6 md:py-8">
        <div className="md:grid md:grid-cols-[240px_1fr] md:gap-8 lg:grid-cols-[260px_1fr]">
          {/* Desktop sidebar */}
          <div className="mb-6 md:mb-0">
            <ProfileSidebar activeSection={activeSection} onNavigate={handleNavigate} />
          </div>

          {/* Main content */}
          <div className="min-w-0">
            {/* Mobile: show section header when not on overview */}
            {activeSection !== "overview" && activeSectionData && (
              <MobileSectionHeader section={activeSectionData} onBack={handleBack} />
            )}

            {/* Content */}
            <div className={activeSection !== "overview" ? "pt-4 md:pt-0" : ""}>
              {activeSection === "overview" ? (
                <ProfileOverview onNavigate={handleNavigate} />
              ) : (
                <SectionContent section={activeSection} />
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ProfileView() {
  return <ProfileViewInner />;
}

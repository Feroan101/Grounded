"use client";

import { useState } from "react";

const ANIMATIONS_KEY = "grounded_animations_enabled";

function getAnimationsEnabled(): boolean {
  if (typeof window === "undefined") return true;
  const val = localStorage.getItem(ANIMATIONS_KEY);
  if (val === null) return true;
  return val !== "false";
}

function setAnimationsEnabled(value: boolean) {
  localStorage.setItem(ANIMATIONS_KEY, String(value));
}

function Toggle({
  enabled,
  onChange,
  label,
}: {
  enabled: boolean;
  onChange: (enabled: boolean) => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      aria-label={label}
      onClick={() => onChange(!enabled)}
      className={`relative inline-flex h-6 w-11 flex-shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus:outline-none focus:ring-2 focus:ring-espresso/30 focus:ring-offset-2 focus:ring-offset-marble ${
        enabled ? "bg-espresso" : "bg-stone"
      }`}
    >
      <span
        className={`pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out ${
          enabled ? "translate-x-5" : "translate-x-0"
        }`}
      />
    </button>
  );
}

export function ExperienceSection() {
  const [animations, setAnimations] = useState(getAnimationsEnabled);

  function handleToggleAnimations(value: boolean) {
    setAnimations(value);
    setAnimationsEnabled(value);
  }

  return (
    <div className="animate-fade-in space-y-6">
      {/* Description */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <p className="text-xs leading-relaxed text-latte">
          Customize how Grounded looks and feels. These settings are stored locally in your browser
          and don&apos;t affect other devices.
        </p>
      </div>

      {/* Settings */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-4 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Display
        </h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between gap-4 rounded-lg bg-marble/50 px-3 py-2.5">
            <div>
              <p className="text-sm font-medium text-bean">Animations</p>
              <p className="mt-0.5 text-[11px] text-latte/70">
                Enable smooth transitions and animations throughout the interface
              </p>
            </div>
            <Toggle
              enabled={animations}
              onChange={handleToggleAnimations}
              label="Enable animations"
            />
          </div>
        </div>
      </div>

      {/* Info note */}
      <div className="rounded-xl border border-cafe/15 bg-marble p-4">
        <p className="text-xs leading-relaxed text-latte/70">
          More display settings will be available as Grounded evolves. For now, animations are the
          only locally-stored preference.
        </p>
      </div>
    </div>
  );
}

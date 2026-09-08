"use client";

import { useState, useCallback } from "react";
import { useProfile, CoffeePreferences } from "@/lib/profile-context";
import { SaveIcon, CheckIcon } from "@/components/profile-icons";

function SegmentedControl({
  options,
  value,
  onChange,
}: {
  options: { label: string; value: string }[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((option) => (
        <button
          key={option.value}
          onClick={() => onChange(option.value)}
          className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-all ${
            value === option.value
              ? "bg-espresso text-ivory"
              : "border border-stone/50 text-bean hover:bg-cream/50"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function ChipSelect({
  options,
  selected,
  onToggle,
}: {
  options: string[];
  selected: string[];
  onToggle: (option: string) => void;
}) {
  return (
    <div className="flex flex-wrap gap-1.5">
      {options.map((option) => (
        <button
          key={option}
          onClick={() => onToggle(option)}
          className={`rounded-full px-3 py-1 text-xs font-medium transition-all ${
            selected.includes(option)
              ? "bg-espresso text-ivory"
              : "border border-stone/50 text-bean hover:bg-cream/50"
          }`}
        >
          {option}
        </button>
      ))}
    </div>
  );
}

export function YourCoffeeSection() {
  const { coffee, updateCoffee, saving } = useProfile();
  const [localPrefs, setLocalPrefs] = useState<CoffeePreferences>(coffee);
  const [hasChanges, setHasChanges] = useState(false);
  const [showSaved, setShowSaved] = useState(false);

  const handleChange = useCallback(
    (update: Partial<CoffeePreferences>) => {
      setLocalPrefs((prev) => ({ ...prev, ...update }));
      setHasChanges(true);
    },
    []
  );

  const handleSave = useCallback(async () => {
    try {
      await updateCoffee(localPrefs);
      setHasChanges(false);
      setShowSaved(true);
      setTimeout(() => setShowSaved(false), 2000);
    } catch (err) {
      console.error("Failed to save:", err);
    }
  }, [localPrefs, updateCoffee]);

  return (
    <div className="animate-fade-in space-y-6">
      {/* Usual order summary */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-3 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Your Usual
        </h3>
        <div className="flex flex-wrap gap-2">
          {localPrefs.favoriteDrink && (
            <span className="rounded-full bg-espresso/10 px-3 py-1 text-xs font-medium text-espresso">
              {localPrefs.favoriteDrink}
            </span>
          )}
          {localPrefs.temperature !== "either" && (
            <span className="rounded-full bg-espresso/10 px-3 py-1 text-xs font-medium text-espresso">
              {localPrefs.temperature === "hot" ? "Hot" : "Iced"}
            </span>
          )}
          {localPrefs.milkPreference && (
            <span className="rounded-full bg-espresso/10 px-3 py-1 text-xs font-medium text-espresso">
              {localPrefs.milkPreference} milk
            </span>
          )}
          {localPrefs.sweetness && (
            <span className="rounded-full bg-espresso/10 px-3 py-1 text-xs font-medium text-espresso">
              {localPrefs.sweetness} sweet
            </span>
          )}
          {!localPrefs.favoriteDrink && !localPrefs.milkPreference && !localPrefs.sweetness && (
            <span className="text-xs text-latte/70">Configure your preferences below</span>
          )}
        </div>
      </div>

      {/* Preferences form */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-4 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Coffee Preferences
        </h3>

        <div className="space-y-5">
          {/* Favorite drink */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-bean">Favorite drink</label>
            <input
              value={localPrefs.favoriteDrink}
              onChange={(e) => handleChange({ favoriteDrink: e.target.value })}
              placeholder="e.g. Oat milk latte"
              className="w-full rounded-lg border border-stone/50 bg-marble px-3 py-2 text-sm text-bean placeholder:text-latte/50 focus:outline-none focus:ring-1 focus:ring-espresso/30"
            />
          </div>

          {/* Temperature */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-bean">Temperature</label>
            <SegmentedControl
              options={[
                { label: "Hot", value: "hot" },
                { label: "Iced", value: "iced" },
                { label: "Either", value: "either" },
              ]}
              value={localPrefs.temperature}
              onChange={(v) => handleChange({ temperature: v as "hot" | "iced" | "either" })}
            />
          </div>

          {/* Milk */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-bean">Milk preference</label>
            <SegmentedControl
              options={[
                { label: "Whole", value: "whole" },
                { label: "Oat", value: "oat" },
                { label: "Almond", value: "almond" },
                { label: "Soy", value: "soy" },
                { label: "None", value: "none" },
              ]}
              value={localPrefs.milkPreference}
              onChange={(v) => handleChange({ milkPreference: v })}
            />
          </div>

          {/* Sweetness */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-bean">Sweetness</label>
            <SegmentedControl
              options={[
                { label: "None", value: "none" },
                { label: "Less", value: "less" },
                { label: "Regular", value: "regular" },
                { label: "Extra", value: "extra" },
              ]}
              value={localPrefs.sweetness}
              onChange={(v) => handleChange({ sweetness: v })}
            />
          </div>

          {/* Strength */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-bean">Coffee strength</label>
            <SegmentedControl
              options={[
                { label: "Light", value: "light" },
                { label: "Medium", value: "medium" },
                { label: "Strong", value: "strong" },
              ]}
              value={localPrefs.strength}
              onChange={(v) => handleChange({ strength: v })}
            />
          </div>

          {/* Caffeine */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-bean">Caffeine</label>
            <SegmentedControl
              options={[
                { label: "Regular", value: "regular" },
                { label: "Decaf", value: "decaf" },
                { label: "Either", value: "either" },
              ]}
              value={localPrefs.caffeinePreference}
              onChange={(v) => handleChange({ caffeinePreference: v })}
            />
          </div>

          {/* Roast */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-bean">Favorite roast</label>
            <SegmentedControl
              options={[
                { label: "Light", value: "light" },
                { label: "Medium", value: "medium" },
                { label: "Dark", value: "dark" },
              ]}
              value={localPrefs.roastPreference}
              onChange={(v) => handleChange({ roastPreference: v })}
            />
          </div>

          {/* Brew method */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-bean">Brewing method</label>
            <SegmentedControl
              options={[
                { label: "Espresso", value: "espresso" },
                { label: "Pour over", value: "pour-over" },
                { label: "French press", value: "french-press" },
                { label: "Cold brew", value: "cold-brew" },
              ]}
              value={localPrefs.brewMethod}
              onChange={(v) => handleChange({ brewMethod: v })}
            />
          </div>

          {/* Dietary */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-bean">Dietary preferences</label>
            <ChipSelect
              options={["Vegan", "Dairy-free", "Sugar-free", "Gluten-free"]}
              selected={localPrefs.dietaryPreference}
              onToggle={(option) =>
                handleChange({
                  dietaryPreference: localPrefs.dietaryPreference.includes(option)
                    ? localPrefs.dietaryPreference.filter((p) => p !== option)
                    : [...localPrefs.dietaryPreference, option],
                })
              }
            />
          </div>

          {/* Allergies */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-bean">Allergies or intolerances</label>
            <input
              value={localPrefs.allergiesOrIntolerances}
              onChange={(e) => handleChange({ allergiesOrIntolerances: e.target.value })}
              placeholder="e.g. Tree nuts, soy"
              className="w-full rounded-lg border border-stone/50 bg-marble px-3 py-2 text-sm text-bean placeholder:text-latte/50 focus:outline-none focus:ring-1 focus:ring-espresso/30"
            />
          </div>
        </div>
      </div>

      {/* Save button */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {showSaved && (
            <span className="flex items-center gap-1 text-xs text-espresso animate-fade-in">
              <CheckIcon className="h-3.5 w-3.5" />
              Saved
            </span>
          )}
        </div>
        <button
          onClick={handleSave}
          disabled={!hasChanges || saving}
          className="flex items-center gap-2 rounded-lg bg-espresso px-4 py-2 text-sm font-medium text-ivory transition-all hover:bg-espresso/90 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <SaveIcon className="h-4 w-4" />
          {saving ? "Saving..." : "Save preferences"}
        </button>
      </div>
    </div>
  );
}

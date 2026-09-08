"use client";

import { useState, useCallback } from "react";
import { useProfile, AIContext } from "@/lib/profile-context";
import { ConfirmDialog } from "@/components/confirm-dialog";
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

export function KnowMeBetterSection() {
  const { aiContext, updateAIContext, saving } = useProfile();
  const [localCtx, setLocalCtx] = useState<AIContext>(aiContext);
  const [hasChanges, setHasChanges] = useState(false);
  const [showSaved, setShowSaved] = useState(false);
  const [showClearDialog, setShowClearDialog] = useState(false);

  const handleChange = useCallback(
    (update: Partial<AIContext>) => {
      setLocalCtx((prev) => ({ ...prev, ...update }));
      setHasChanges(true);
    },
    []
  );

  const handleSave = useCallback(async () => {
    try {
      await updateAIContext(localCtx);
      setHasChanges(false);
      setShowSaved(true);
      setTimeout(() => setShowSaved(false), 2000);
    } catch (err) {
      console.error("Failed to save:", err);
    }
  }, [localCtx, updateAIContext]);

  const handleClear = useCallback(async () => {
    try {
      await updateAIContext({ customContext: "" });
      setLocalCtx((prev) => ({ ...prev, customContext: "" }));
      setShowClearDialog(false);
      setShowSaved(true);
      setTimeout(() => setShowSaved(false), 2000);
    } catch (err) {
      console.error("Failed to clear:", err);
    }
  }, [updateAIContext]);

  return (
    <div className="animate-fade-in space-y-6">
      {/* Description */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <p className="text-xs leading-relaxed text-latte">
          Give Grounded a little context so its conversations and recommendations feel more personal.
          This information helps Grounded understand your preferences and communicate in a way that
          feels natural to you.
        </p>
      </div>

      {/* Custom context */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-2 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Things I want Grounded to know
        </h3>
        <textarea
          value={localCtx.customContext}
          onChange={(e) => handleChange({ customContext: e.target.value })}
          rows={4}
          placeholder="I usually prefer strong coffee, don&apos;t like overly sweet drinks, and prefer affordable recommendations."
          className="w-full resize-none rounded-lg border border-stone/50 bg-marble px-3 py-2 text-sm leading-relaxed text-bean placeholder:text-latte/50 focus:outline-none focus:ring-1 focus:ring-espresso/30"
        />
        <div className="mt-3 flex items-center justify-between">
          <span className="text-[11px] text-latte/70">
            {localCtx.customContext.length > 0
              ? `${localCtx.customContext.length} characters`
              : "Optional but helpful for personalization"}
          </span>
          {localCtx.customContext.length > 0 && (
            <button
              onClick={() => setShowClearDialog(true)}
              className="text-[11px] font-medium text-latte transition-colors hover:text-espresso"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Response style */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-2 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Response style
        </h3>
        <p className="mb-3 text-xs text-latte/70">
          How detailed should Grounded&apos;s responses be?
        </p>
        <SegmentedControl
          options={[
            { label: "Short & simple", value: "short" },
            { label: "Balanced", value: "balanced" },
            { label: "Detailed", value: "detailed" },
          ]}
          value={localCtx.responseStyle}
          onChange={(v) => handleChange({ responseStyle: v as AIContext["responseStyle"] })}
        />
      </div>

      {/* Tone */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-2 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Tone
        </h3>
        <p className="mb-3 text-xs text-latte/70">
          How should Grounded communicate with you?
        </p>
        <SegmentedControl
          options={[
            { label: "Friendly", value: "friendly" },
            { label: "Casual", value: "casual" },
            { label: "Professional", value: "professional" },
            { label: "Playful", value: "playful" },
          ]}
          value={localCtx.tone}
          onChange={(v) => handleChange({ tone: v as AIContext["tone"] })}
        />
      </div>

      {/* Recommendation style */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-2 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Recommendations
        </h3>
        <p className="mb-3 text-xs text-latte/70">
          How should Grounded present drink suggestions?
        </p>
        <SegmentedControl
          options={[
            { label: "Best pick", value: "best" },
            { label: "A few choices", value: "few" },
            { label: "Explain why", value: "explain" },
          ]}
          value={localCtx.recommendationStyle}
          onChange={(v) => handleChange({ recommendationStyle: v as AIContext["recommendationStyle"] })}
        />
      </div>

      {/* Use preferences toggle */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <div className="flex items-center justify-between gap-4">
          <div>
            <h3 className="text-sm font-medium text-bean">Use my preferences in conversations</h3>
            <p className="mt-0.5 text-[11px] text-latte/70">
              Let Grounded use your preferences to personalize responses
            </p>
          </div>
          <Toggle
            enabled={localCtx.usePreferencesInConversations}
            onChange={(v) => handleChange({ usePreferencesInConversations: v })}
            label="Use preferences in conversations"
          />
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
          {saving ? "Saving..." : "Save settings"}
        </button>
      </div>

      {/* Clear context dialog */}
      {showClearDialog && (
        <ConfirmDialog
          title="Clear your context?"
          message="This will remove the personal context you've shared with Grounded. Your coffee preferences will remain."
          confirmLabel="Clear context"
          onConfirm={handleClear}
          onCancel={() => setShowClearDialog(false)}
        />
      )}
    </div>
  );
}

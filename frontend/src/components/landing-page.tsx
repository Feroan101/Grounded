"use client";

import { useMemo, useState } from "react";
import { GoogleAuthProvider, signInWithPopup } from "firebase/auth";
import { getFirebaseAuth } from "@/lib/firebase";

// Design system colors from DESIGN.md
const BEAN = "#2B1B15";
const ESPRESSO = "#4A2C20";
const LATTE = "#8B6B57";
const CREAM = "#E8DCCF";
const STONE = "#D8D5CF";
const IVORY = "#FCFBF8";
const MARBLE = "#F7F6F2";

const COFFEE_SHOP_IMAGE =
  "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb?w=1920&q=80&auto=format&fit=crop";

const QUOTES: { text: string; author: string }[] = [
  { text: "I came here to work for 20 minutes. It's been four hours. I've had three coffees.", author: "a Coffee Addict" },
  { text: "Grounded successfully convinced me that buying another coffee counts as productivity.", author: "A Grounded User" },
  { text: "Opened my laptop. Stared at it. Grounded understood.", author: "Someone Who Needed Coffee" },
  { text: "Finally an app that respects my extremely serious relationship with coffee.", author: "The Guy at Table 7" },
  { text: "I finished one task and immediately rewarded myself with absolutely nothing.", author: "A Professional Procrastinator" },
  { text: "My productivity increased by 12%. My coffee consumption increased by 47%.", author: "Your Local Caffeine Enthusiast" },
  { text: "I don't know what I'm doing, but at least I found a nice place to do it.", author: "Sleep-Deprived & Thriving" },
  { text: "This app didn't fix my life. It did help me find a nice place to procrastinate.", author: "A Person With 47 Tabs Open" },
  { text: "Grounded knows my coffee order better than my therapist knows my problems.", author: "The \"One More Coffee\" Guy" },
  { text: "Came for the coffee. Stayed because I forgot what I was supposed to be doing.", author: "An Extremely Focused Individual" },
  { text: "My barista and I are in a committed relationship now. Grounded introduced us.", author: "Someone Avoiding Their Inbox" },
  { text: "I told Grounded I needed focus. It suggested a triple espresso. Validated.", author: "A Regular" },
  { text: "Three hours of 'deep work' later and I have a very detailed pros and cons list for lunch.", author: "The Laptop Guy" },
  { text: "Grounded recommended a latte. I got a latte. I've never been happier. This is peak adulthood.", author: "A Recovering Procrastinator" },
  { text: "I don't always trust AI, but when I do, it's about coffee.", author: "Your Friendly Neighborhood Coffee Addict" },
  { text: "This app is the only thing in my life that has its act together.", author: "Someone Who Definitely Came Here to Work" },
  { text: "My coffee consumption is now a personality trait. Thanks, Grounded.", author: "Table 12, Probably" },
  { text: "I started using Grounded to be more productive. Now I just have stronger opinions about beans.", author: "A Mildly Productive Person" },
  { text: "Grounded suggested I take a break. I took a break. I never went back to work.", author: "The Early Bird's Tired Cousin" },
  { text: "Five stars. Would procrastinate here again.", author: "Someone's Manager" },
  { text: "I came for the caffeine. I stayed for the vibes. I'm never leaving.", author: "A Person Who Has Lost Track of Time" },
  { text: "Grounded knows I'm pretending to work and honestly? I respect that.", author: "The Window Seat Regular" },
  { text: "The coffee here is good. The Wi-Fi is better. The existential dread is free.", author: "A Part-Time Dreamer" },
  { text: "I've been staring at this screen for two hours. Grounded just asked if I wanted a refill. Iconic.", author: "The Quiet Overthinker" },
  { text: "I told myself I'd only stay for one cup. That was four cups ago.", author: "The Come Back Daily" },
  { text: "My blood type is now espresso.", author: "Caffeine Operating System" },
  { text: "Grounded helped me realize my true calling is sitting in cafes pretending to write a novel.", author: "An Aspiring Novelist" },
  { text: "I don't have a problem. I can stop whenever I want. I just don't want to.", author: "The Decaf Liar" },
  { text: "This app gets me. My actual friends don't even know my coffee order.", author: "The Loyal Regular" },
  { text: "Came here for the ambiance. Stayed because the coffee made me forget what I was anxious about.", author: "Anxiety & Caffeine" },
  { text: "I've had so much coffee today I can hear colors.", author: "The Overcaffeinated" },
  { text: "Grounded is the only place where doing nothing feels productive.", author: "The Professional Idler" },
];

// Post-it paper colors — warm, slightly desaturated, café-compatible
const PAPER_COLORS = [
  "#F5E6A3", // soft yellow
  "#F2D8A8", // warm cream
  "#E8C4A0", // muted peach
  "#D4A9A0", // dusty pink
  "#B8C5A8", // soft sage
  "#D6C9B0", // warm beige
  "#A8B8C4", // muted blue
  "#C9A88C", // light terracotta
  "#E0D0B8", // parchment
  "#F0DCC0", // vanilla
];

type Decoration = "pin" | "tape" | "none";

interface NoteConfig {
  rotation: number;
  left: string;
  width: string;
  height: string;
  zIndex: number;
  decoration: Decoration;
  bgColor: string;
}

function shuffle<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function pickDecoration(): Decoration {
  const decos: Decoration[] = ["pin", "tape", "tape", "none", "none"];
  return decos[Math.floor(Math.random() * decos.length)];
}

// Desktop configs — scattered across left side
function pickDesktopNotes(count: number): { text: string; author: string; config: NoteConfig }[] {
  const rotations = [-5, 4, -3, 3, -2, 2, -4, 5, -1, 1];
  const configs: NoteConfig[] = [
    { rotation: 0, left: "2%", width: "w-52", height: "min-h-[110px]", zIndex: 30, decoration: "pin", bgColor: "" },
    { rotation: 0, left: "18%", width: "w-44", height: "min-h-[95px]", zIndex: 22, decoration: "tape", bgColor: "" },
    { rotation: 0, left: "32%", width: "w-48", height: "min-h-[100px]", zIndex: 18, decoration: "none", bgColor: "" },
    { rotation: 0, left: "4%", width: "w-56", height: "min-h-[120px]", zIndex: 35, decoration: "pin", bgColor: "" },
    { rotation: 0, left: "24%", width: "w-40", height: "min-h-[85px]", zIndex: 15, decoration: "tape", bgColor: "" },
    { rotation: 0, left: "6%", width: "w-48", height: "min-h-[105px]", zIndex: 28, decoration: "none", bgColor: "" },
    { rotation: 0, left: "28%", width: "w-44", height: "min-h-[95px]", zIndex: 20, decoration: "pin", bgColor: "" },
    { rotation: 0, left: "2%", width: "w-52", height: "min-h-[110px]", zIndex: 25, decoration: "tape", bgColor: "" },
    { rotation: 0, left: "20%", width: "w-40", height: "min-h-[85px]", zIndex: 16, decoration: "none", bgColor: "" },
    { rotation: 0, left: "36%", width: "w-36", height: "min-h-[80px]", zIndex: 12, decoration: "pin", bgColor: "" },
  ];

  const shuffledQuotes = shuffle(QUOTES);
  const shuffledConfigs = shuffle(configs).slice(0, count);
  const shuffledColors = shuffle(PAPER_COLORS);

  return shuffledConfigs.map((cfg, i) => ({
    ...shuffledQuotes[i % shuffledQuotes.length],
    config: {
      ...cfg,
      rotation: rotations[Math.floor(Math.random() * rotations.length)],
      decoration: pickDecoration(),
      bgColor: shuffledColors[i % shuffledColors.length],
    },
  }));
}

// Mobile configs — exactly 3 notes in left/right/left pattern
function pickMobileNotes(): { text: string; author: string; config: NoteConfig }[] {
  const rotations = [-4, 3, -2, 2, -3, 4];
  const shuffledQuotes = shuffle(QUOTES);
  const shuffledColors = shuffle(PAPER_COLORS);

  // Left/right/left pattern with randomized sizes and positions within zones
  const noteConfigs: { zone: "left" | "right"; width: string; height: string }[] = [
    { zone: "left", width: "w-40", height: "min-h-[95px]" },
    { zone: "right", width: "w-44", height: "min-h-[100px]" },
    { zone: "left", width: "w-36", height: "min-h-[85px]" },
  ];

  return noteConfigs.map((cfg, i) => ({
    ...shuffledQuotes[i],
    config: {
      rotation: rotations[Math.floor(Math.random() * rotations.length)],
      left: cfg.zone === "left" ? "5%" : "52%",
      width: cfg.width,
      height: cfg.height,
      zIndex: 20 - i * 2,
      decoration: pickDecoration(),
      bgColor: shuffledColors[i],
    },
  }));
}

function DecorationElement({ type }: { type: Decoration }) {
  switch (type) {
    case "pin":
      return (
        <div className="absolute -top-1.5 left-1/2 -translate-x-1/2">
          <div
            className="h-2.5 w-2.5 rounded-full"
            style={{
              background: `radial-gradient(circle at 35% 35%, #E53E3E, #C53030)`,
              boxShadow: `0 1px 2px rgba(0,0,0,0.3), inset 0 1px 1px rgba(255,255,255,0.3)`,
            }}
          />
        </div>
      );
    case "tape":
      return (
        <div
          className="absolute -top-2 left-1/2 -translate-x-1/2 rotate-1"
          style={{
            width: "40px",
            height: "12px",
            background: `linear-gradient(135deg, rgba(232,220,207,0.7), rgba(216,213,207,0.6))`,
            borderRadius: "1px",
          }}
        />
      );
    default:
      return null;
  }
}

function NoteCard({ note }: { note: { text: string; author: string; config: NoteConfig } }) {
  return (
    <div
      className={`${note.config.width} ${note.config.height} relative p-4 pt-5`}
      style={{
        transform: `rotate(${note.config.rotation}deg)`,
        background: note.config.bgColor,
        boxShadow: `2px 3px 8px rgba(43,27,21,0.18), 0 1px 3px rgba(43,27,21,0.1)`,
        borderRadius: "1px",
      }}
    >
      <DecorationElement type={note.config.decoration} />

      <p
        className="text-[13px] leading-relaxed"
        style={{ color: BEAN }}
      >
        &ldquo;{note.text}&rdquo;
      </p>

      <p
        className="mt-2.5 text-[10px] tracking-wide text-right"
        style={{ color: LATTE }}
      >
        - {note.author}
      </p>
    </div>
  );
}

function TermsModal({ onClose }: { onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4" onClick={onClose}>
      <div className="absolute inset-0" style={{ background: "rgba(0,0,0,0.6)", backdropFilter: "blur(4px)" }} />
      <div
        className="relative flex max-h-[80vh] w-full max-w-lg flex-col rounded-2xl shadow-2xl"
        style={{ background: MARBLE }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b px-6 py-4" style={{ borderColor: STONE }}>
          <h2 className="text-lg font-semibold" style={{ color: BEAN }}>Terms & Conditions</h2>
          <button onClick={onClose} className="flex h-8 w-8 items-center justify-center rounded-lg transition-colors hover:bg-black/5" aria-label="Close">
            <svg className="h-5 w-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: LATTE }}>
              <path d="M18 6L6 18M6 6l12 12" />
            </svg>
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5" style={{ color: BEAN }}>
          <p className="mb-1 text-xs" style={{ color: LATTE }}>Last updated: September 2026</p>
          <p className="mb-4 text-sm leading-relaxed">Welcome to Grounded.</p>
          <p className="mb-4 text-sm leading-relaxed">Grounded is a fictional project created for demonstration, development, and educational purposes. By using this application and continuing with Google sign-in, you acknowledge and agree to the following terms.</p>
          <h3 className="mb-2 mt-5 text-sm font-semibold" style={{ color: ESPRESSO }}>1. Fictional Brand</h3>
          <p className="mb-2 text-sm leading-relaxed">Grounded is a fictional brand and project.</p>
          <p className="mb-2 text-sm leading-relaxed">It is not intended to represent, operate as, or impersonate any existing café, company, application, service, or brand.</p>
          <p className="mb-2 text-sm leading-relaxed">Any similarities in naming, visual style, concepts, or presentation to existing businesses or products are unintentional.</p>
          <p className="mb-4 text-sm leading-relaxed">Grounded does not claim affiliation with or endorsement by any similarly named or visually similar brand.</p>
          <h3 className="mb-2 mt-5 text-sm font-semibold" style={{ color: ESPRESSO }}>2. Open Source & Third-Party Materials</h3>
          <p className="mb-2 text-sm leading-relaxed">This project makes use of open-source software, libraries, frameworks, and openly licensed resources where applicable.</p>
          <p className="mb-2 text-sm leading-relaxed">Third-party software and assets remain subject to their respective licenses and the rights of their original creators.</p>
          <p className="mb-2 text-sm leading-relaxed">Grounded does not claim ownership of third-party open-source software, libraries, assets, trademarks, or intellectual property used by the project.</p>
          <p className="mb-4 text-sm leading-relaxed">Where required, appropriate attribution and licensing information should be provided in the project repository.</p>
          <h3 className="mb-2 mt-5 text-sm font-semibold" style={{ color: ESPRESSO }}>3. Project Purpose</h3>
          <p className="mb-2 text-sm leading-relaxed">Grounded is provided as a fictional demonstration/project and is not intended to represent a commercial café, production business, or real-world service.</p>
          <p className="mb-4 text-sm leading-relaxed">Features, content, locations, reviews, quotes, and other information presented within the application may be fictional or generated for demonstration purposes.</p>
          <h3 className="mb-2 mt-5 text-sm font-semibold" style={{ color: ESPRESSO }}>4. No Affiliation</h3>
          <p className="mb-4 text-sm leading-relaxed">Grounded is independently created and is not affiliated with, sponsored by, endorsed by, or associated with any real-world company or brand unless explicitly stated otherwise.</p>
          <h3 className="mb-2 mt-5 text-sm font-semibold" style={{ color: ESPRESSO }}>5. Use of the Application</h3>
          <p className="mb-4 text-sm leading-relaxed">You agree to use the application only for lawful purposes and not to misuse, disrupt, or attempt to compromise the application or its authentication systems.</p>
          <h3 className="mb-2 mt-5 text-sm font-semibold" style={{ color: ESPRESSO }}>6. Changes</h3>
          <p className="mb-2 text-sm leading-relaxed">These Terms & Conditions may be updated as the project evolves.</p>
          <p className="mb-4 text-sm leading-relaxed">Continued use of the application after changes are made constitutes acceptance of the updated terms.</p>
          <h3 className="mb-2 mt-5 text-sm font-semibold" style={{ color: ESPRESSO }}>7. Contact</h3>
          <p className="mb-4 text-sm leading-relaxed">For questions regarding this project, refer to the project repository and its associated contact information.</p>
        </div>
        <div className="border-t px-6 py-4" style={{ borderColor: STONE }}>
          <button onClick={onClose} className="w-full rounded-xl px-4 py-2.5 text-sm font-medium transition-all" style={{ background: BEAN, color: IVORY }}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

export function LandingPage() {
  const desktopNotes = useMemo(() => pickDesktopNotes(9), []);
  const mobileNotes = useMemo(() => pickMobileNotes(), []);
  const [termsAccepted, setTermsAccepted] = useState(false);
  const [showTermsModal, setShowTermsModal] = useState(false);
  const [isSigningIn, setIsSigningIn] = useState(false);

  async function handleGoogleSignIn() {
    if (!termsAccepted || isSigningIn) return;
    setIsSigningIn(true);
    const provider = new GoogleAuthProvider();
    try {
      await signInWithPopup(getFirebaseAuth(), provider);
    } catch (err) {
      console.error("Sign-in error:", err);
    } finally {
      setIsSigningIn(false);
    }
  }

  return (
    <div className="relative h-screen w-screen overflow-hidden">
      {/* Background image — full bleed */}
      <div
        className="absolute inset-0 bg-cover bg-center bg-no-repeat"
        style={{ backgroundImage: `url(${COFFEE_SHOP_IMAGE})` }}
      />

      {/* Diagonal overlay — black tones (desktop) */}
      <div
        className="absolute inset-0 hidden md:block"
        style={{
          background: `
            linear-gradient(
              115deg,
              transparent 0%,
              transparent 35%,
              rgba(0,0,0,0.08) 40%,
              rgba(0,0,0,0.25) 48%,
              rgba(0,0,0,0.5) 55%,
              rgba(0,0,0,0.72) 62%,
              rgba(0,0,0,0.85) 70%,
              rgba(0,0,0,0.92) 80%,
              rgba(0,0,0,0.95) 100%
            )
          `,
        }}
      />

      {/* Mobile overlay — bottom-to-top gradient, pitch black at bottom */}
      <div
        className="absolute inset-0 md:hidden"
        style={{
          background: `linear-gradient(to top,
            rgba(0,0,0,1) 0%,
            rgba(0,0,0,0.98) 15%,
            rgba(0,0,0,0.9) 30%,
            rgba(0,0,0,0.7) 45%,
            rgba(0,0,0,0.4) 60%,
            rgba(0,0,0,0.15) 75%,
            transparent 100%
          )`,
        }}
      />

      {/* Subtle blur on the right side via gradient mask — desktop only */}
      <div
        className="absolute inset-0 backdrop-blur-[2px] hidden md:block"
        style={{
          maskImage:
            "linear-gradient(115deg, transparent 0%, transparent 30%, black 50%, black 100%)",
          WebkitMaskImage:
            "linear-gradient(115deg, transparent 0%, transparent 30%, black 50%, black 100%)",
        }}
      />

      {/* Bottom vignette — desktop only */}
      <div className="absolute inset-0 bg-gradient-to-t from-black/40 via-transparent to-transparent hidden md:block" />

      {/* ===== DESKTOP NOTICE BOARD — left side ===== */}
      <div className="absolute inset-0 z-10 hidden md:block">
        {/* Board heading */}
        <div
          className="absolute"
          style={{ left: "4%", top: "2%", zIndex: 40 }}
        >
          <div
            className="px-3 py-1.5 rounded"
            style={{ background: `rgba(74,44,32,0.8)` }}
          >
            <span
              className="text-[10px] font-semibold tracking-[0.2em] uppercase"
              style={{ color: CREAM }}
            >
              Notes from the Neighbourhood
            </span>
          </div>
        </div>

        {/* Desktop notes */}
        {desktopNotes.map((note, i) => (
          <div
            key={i}
            className="absolute"
            style={{
              left: note.config.left,
              top: ["8%", "6%", "12%", "26%", "30%", "48%", "52%", "68%", "72%"][i],
              zIndex: note.config.zIndex,
            }}
          >
            <NoteCard note={note} />
          </div>
        ))}
      </div>

      {/* ===== MOBILE NOTICE BOARD ===== */}
      <div className="relative z-10 flex flex-col md:hidden min-h-screen">
        {/* Title — always first */}
        <div className="px-4 pt-5 pb-3">
          <div
            className="inline-block px-3 py-1.5 rounded"
            style={{ background: `rgba(74,44,32,0.8)` }}
          >
            <span
              className="text-[10px] font-semibold tracking-[0.2em] uppercase"
              style={{ color: CREAM }}
            >
              Notes from the Neighbourhood
            </span>
          </div>
        </div>

        {/* Notes — exactly 3, left/right/left pattern */}
        <div className="flex-1 flex flex-col justify-start gap-5 px-4 pt-2">
          {mobileNotes.map((note, i) => (
            <div
              key={i}
              className={i === 0 || i === 2 ? "self-start" : "self-end"}
              style={{
                zIndex: note.config.zIndex,
                maxWidth: "55%",
              }}
            >
              <NoteCard note={note} />
            </div>
          ))}
        </div>

        {/* Bottom safe area — centered credit + auth */}
        <div className="max-md:pb-5 max-md:pt-4 pb-8 pt-6 px-6 flex flex-col items-center">
          {/* Creator credit — centered */}
          <p
            className="text-[10px] max-md:mb-3 mb-5 text-center"
            style={{ color: `${LATTE}B0` }}
          >
            made by <a href="https://github.com/Feroan101" target="_blank" rel="noopener noreferrer" style={{ color: `${CREAM}D0` }} className="hover:underline">@feroan101</a>
          </p>

          {/* Logo mark */}
          <div className="max-md:mb-3 mb-4 flex items-center gap-3">
            <img
              src="/coffee-logo.png"
              alt="Grounded logo"
              className="h-10 w-10 rounded-xl object-cover"
            />
            <span
              className="text-sm font-semibold tracking-widest uppercase"
              style={{ color: MARBLE }}
            >
              Grounded
            </span>
          </div>

          {/* Heading */}
          <h1
            className="max-md:mb-1 mb-2 text-2xl font-semibold tracking-tight"
            style={{ color: MARBLE }}
          >
            Welcome back.
          </h1>
          <p
            className="max-md:mb-4 mb-6 text-sm"
            style={{ color: LATTE }}
          >
            Your workspace is waiting.
          </p>

          {/* Sign-in button */}
          <button
            onClick={handleGoogleSignIn}
            disabled={!termsAccepted || isSigningIn}
            className="group flex w-full items-center justify-center gap-3 rounded-xl px-5 py-3.5 text-sm font-medium shadow-lg transition-all hover:shadow-xl disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-lg"
            style={{
              background: IVORY,
              color: BEAN,
            }}
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
            Continue with Google
          </button>

          <label className="mt-2 flex items-center justify-center gap-1.5 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
              className="h-[14px] w-[14px] shrink-0 cursor-pointer"
              style={{ accentColor: ESPRESSO }}
            />
            <span className="text-[11px] leading-tight" style={{ color: `${LATTE}B0` }}>
              I agree to the{" "}
              <button
                type="button"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowTermsModal(true); }}
                className="underline transition-colors hover:text-marble"
                style={{ color: `${CREAM}B0` }}
              >
                Terms &amp; Conditions
              </button>
            </span>
          </label>

          {/* Subtle note */}
          <p
            className="max-md:mt-2 mt-4 text-center text-[11px]"
            style={{ color: LATTE }}
          >
            Sign in to access your personalized coffee assistant.
          </p>
        </div>
      </div>

      {/* ===== DESKTOP AUTHENTICATION AREA ===== */}
      <div className="absolute inset-y-0 right-0 z-20 hidden md:flex md:items-center md:justify-end md:pr-20 lg:pr-28 md:w-1/2">
        <div className="w-full max-w-md px-6 pb-8 pt-4 md:px-0 md:pb-0">
          {/* Logo mark */}
          <div className="mb-6 flex items-center gap-3 sm:mb-8">
            <img
              src="/coffee-logo.png"
              alt="Grounded logo"
              className="h-10 w-10 rounded-xl object-cover"
            />
            <span
              className="text-sm font-semibold tracking-widest uppercase"
              style={{ color: MARBLE }}
            >
              Grounded
            </span>
          </div>

          {/* Heading */}
          <h1
            className="mb-3 text-3xl font-semibold tracking-tight sm:text-4xl"
            style={{ color: MARBLE }}
          >
            Welcome back.
          </h1>
          <p
            className="mb-8 text-base sm:mb-10"
            style={{ color: LATTE }}
          >
            Your workspace is waiting.
          </p>

          {/* Sign-in button */}
          <button
            onClick={handleGoogleSignIn}
            disabled={!termsAccepted || isSigningIn}
            className="group flex w-full items-center justify-center gap-3 rounded-xl px-5 py-3.5 text-sm font-medium shadow-lg transition-all hover:shadow-xl disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:shadow-lg"
            style={{
              background: IVORY,
              color: BEAN,
            }}
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
            Continue with Google
          </button>

          <label className="mt-2.5 flex items-center gap-1.5 cursor-pointer select-none md:mt-3 md:px-3 md:py-1.5">
            <input
              type="checkbox"
              checked={termsAccepted}
              onChange={(e) => setTermsAccepted(e.target.checked)}
              className="h-[14px] w-[14px] shrink-0 cursor-pointer"
              style={{ accentColor: ESPRESSO }}
            />
            <span className="text-[11px] leading-tight" style={{ color: `${LATTE}B0` }}>
              I agree to the{" "}
              <button
                type="button"
                onClick={(e) => { e.preventDefault(); e.stopPropagation(); setShowTermsModal(true); }}
                className="underline transition-colors hover:text-marble"
                style={{ color: `${CREAM}B0` }}
              >
                Terms &amp; Conditions
              </button>
            </span>
          </label>

          {/* Subtle note */}
          <p
            className="mt-6 text-center text-xs"
            style={{ color: LATTE }}
          >
            Sign in to access your personalized coffee assistant.
          </p>
        </div>
      </div>

      {/* Creator signature — desktop only, bottom left */}
      <div className="absolute bottom-4 left-4 z-10 hidden md:block">
        <p
          className="text-[11px]"
          style={{ color: `${LATTE}B0` }}
        >
          made by <a href="https://github.com/Feroan101" target="_blank" rel="noopener noreferrer" style={{ color: `${CREAM}D0` }} className="hover:underline">@feroan101</a>
        </p>
      </div>

      {showTermsModal && <TermsModal onClose={() => setShowTermsModal(false)} />}
    </div>
  );
}

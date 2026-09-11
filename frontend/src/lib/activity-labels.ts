import type { ChatActivityEvent } from "./api";

export const ACTIVITY_FALLBACK = "Working on your request...";
export const ACTIVITY_STARTING = "Putting that together...";

const TOOL_LABELS: Record<string, string> = {
  search_menu: "Fetching the menu...",
  get_customer_preferences: "Checking your preferences...",
  get_conversation_history: "Looking back at our conversation...",
  get_order_history: "Looking through your previous orders...",
  save_preference: "Remembering that preference...",
  convert_currency: "Converting the price...",
};

export function friendlyActivity(event: ChatActivityEvent): string {
  if (event.type === "generating") return ACTIVITY_STARTING;
  return TOOL_LABELS[event.name] ?? ACTIVITY_FALLBACK;
}
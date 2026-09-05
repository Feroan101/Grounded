"use client";

interface MessageBubbleProps {
  role: "user" | "assistant";
  content: string;
}

export function MessageBubble({ role, content }: MessageBubbleProps) {
  if (role === "user") {
    return (
      <div className="flex justify-end">
        <div className="max-w-[85%] rounded-2xl rounded-br-md bg-cream px-4 py-3 text-sm leading-relaxed text-bean shadow-sm sm:max-w-[70%]">
          {content}
        </div>
      </div>
    );
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] px-1 text-sm leading-relaxed text-bean sm:max-w-[75%]">
        {content}
      </div>
    </div>
  );
}

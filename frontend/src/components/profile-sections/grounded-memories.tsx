"use client";

import { useState, useCallback } from "react";
import { useProfile } from "@/lib/profile-context";
import { ConfirmDialog } from "@/components/confirm-dialog";
import { PlusIcon, EditIcon, TrashIcon, CheckIcon, XIcon } from "@/components/profile-icons";

function MemoryItem({
  text,
  onEdit,
  onDelete,
}: {
  text: string;
  onEdit: () => void;
  onDelete: () => void;
}) {
  return (
    <div className="group flex items-start gap-3 py-3">
      <span className="mt-0.5 text-sm text-latte/50">+</span>
      <span className="flex-1 text-sm leading-relaxed text-bean">{text}</span>
      <div className="flex flex-shrink-0 items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100">
        <button
          onClick={onEdit}
          className="rounded p-1 text-latte hover:text-espresso"
          aria-label="Edit memory"
        >
          <EditIcon className="h-3.5 w-3.5" />
        </button>
        <button
          onClick={onDelete}
          className="rounded p-1 text-latte hover:text-espresso"
          aria-label="Delete memory"
        >
          <TrashIcon className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}

function EditableMemoryItem({
  initialText,
  onSave,
  onCancel,
}: {
  initialText: string;
  onSave: (text: string) => void;
  onCancel: () => void;
}) {
  const [value, setValue] = useState(initialText);

  return (
    <div className="flex items-start gap-3 py-3">
      <span className="mt-2 text-sm text-latte/50">+</span>
      <div className="flex-1">
        <input
          autoFocus
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") onSave(value);
            if (e.key === "Escape") onCancel();
          }}
          className="w-full rounded-lg border border-espresso/40 bg-marble px-3 py-2 text-sm text-bean focus:outline-none focus:ring-1 focus:ring-espresso/30"
          aria-label="Edit memory"
        />
      </div>
      <div className="flex gap-1">
        <button
          onClick={() => onSave(value)}
          className="rounded p-1.5 text-espresso hover:bg-cream/50"
          aria-label="Save"
        >
          <CheckIcon className="h-4 w-4" />
        </button>
        <button
          onClick={onCancel}
          className="rounded p-1.5 text-latte hover:bg-cream/50"
          aria-label="Cancel"
        >
          <XIcon className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}

export function GroundedMemoriesSection() {
  const { memories, addMemory, updateMemory, deleteMemory, clearAllMemories, saving } = useProfile();
  const [newMemory, setNewMemory] = useState("");
  const [editingId, setEditingId] = useState<string | null>(null);
  const [showClearAllDialog, setShowClearAllDialog] = useState(false);

  const handleAdd = useCallback(async () => {
    if (!newMemory.trim()) return;
    try {
      await addMemory(newMemory.trim());
      setNewMemory("");
    } catch (err) {
      console.error("Failed to add memory:", err);
    }
  }, [newMemory, addMemory]);

  const handleEdit = useCallback(
    async (id: string, text: string) => {
      if (!text.trim()) return;
      try {
        await updateMemory(id, text.trim());
        setEditingId(null);
      } catch (err) {
        console.error("Failed to update memory:", err);
      }
    },
    [updateMemory]
  );

  const handleDelete = useCallback(
    async (id: string) => {
      try {
        await deleteMemory(id);
      } catch (err) {
        console.error("Failed to delete memory:", err);
      }
    },
    [deleteMemory]
  );

  const handleClearAll = useCallback(async () => {
    try {
      await clearAllMemories();
      setShowClearAllDialog(false);
    } catch (err) {
      console.error("Failed to clear memories:", err);
    }
  }, [clearAllMemories]);

  return (
    <div className="animate-fade-in space-y-6">
      {/* Description */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <p className="text-xs leading-relaxed text-latte">
          Grounded remembers important details about your preferences. These memories help
          personalize your conversations and recommendations over time.
        </p>
      </div>

      {/* Add new memory */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <h3 className="mb-3 text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
          Remember something
        </h3>
        <div className="flex gap-2">
          <input
            value={newMemory}
            onChange={(e) => setNewMemory(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") handleAdd();
            }}
            placeholder='e.g. I prefer cold brew in the afternoon'
            className="flex-1 rounded-lg border border-stone/50 bg-marble px-3 py-2 text-sm text-bean placeholder:text-latte/50 focus:outline-none focus:ring-1 focus:ring-espresso/30"
          />
          <button
            onClick={handleAdd}
            disabled={!newMemory.trim() || saving}
            className="flex items-center gap-1.5 rounded-lg bg-espresso px-3 py-2 text-xs font-medium text-ivory transition-all hover:bg-espresso/90 disabled:opacity-50"
          >
            <PlusIcon className="h-3.5 w-3.5" />
            Add
          </button>
        </div>
      </div>

      {/* Memories list */}
      <div className="rounded-xl border border-stone/50 bg-ivory/80 p-5">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="text-[10px] font-medium uppercase tracking-[0.2em] text-latte/60">
            Grounded remembers
          </h3>
          {memories.length > 0 && (
            <button
              onClick={() => setShowClearAllDialog(true)}
              className="text-[11px] font-medium text-latte transition-colors hover:text-espresso"
            >
              Clear all
            </button>
          )}
        </div>

        {memories.length === 0 ? (
          <p className="py-4 text-center text-xs text-latte/70">
            No memories yet. Add something above to help Grounded remember your preferences.
          </p>
        ) : (
          <div className="divide-y divide-stone/30">
            {memories.map((memory) =>
              editingId === memory.id ? (
                <EditableMemoryItem
                  key={memory.id}
                  initialText={memory.text}
                  onSave={(text) => handleEdit(memory.id, text)}
                  onCancel={() => setEditingId(null)}
                />
              ) : (
                <MemoryItem
                  key={memory.id}
                  text={memory.text}
                  onEdit={() => setEditingId(memory.id)}
                  onDelete={() => handleDelete(memory.id)}
                />
              )
            )}
          </div>
        )}
      </div>

      {/* Clear all dialog */}
      {showClearAllDialog && (
        <ConfirmDialog
          title="Clear all memories?"
          message="This will permanently delete all memories Grounded has about you. This action cannot be undone."
          confirmLabel="Clear all"
          onConfirm={handleClearAll}
          onCancel={() => setShowClearAllDialog(false)}
        />
      )}
    </div>
  );
}

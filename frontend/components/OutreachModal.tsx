"use client";

// Phase 3 stub — full implementation in Phase 3.
// This component will show GLM-drafted messages, Telegram deep links, and phone fallbacks.

interface OutreachModalProps {
  listingId: string;
  onClose: () => void;
}

export default function OutreachModal({ listingId, onClose }: OutreachModalProps) {
  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-white rounded-xl shadow-xl p-6 max-w-md w-full mx-4">
        <h2 className="text-lg font-semibold text-gray-900 mb-2">Prepare Inquiry</h2>
        <p className="text-sm text-gray-500 mb-4">
          AI-drafted inquiry messages and Telegram handoff will be available in Phase 3.
        </p>
        <p className="text-xs text-gray-400 font-mono mb-4">Listing ID: {listingId}</p>
        <button
          onClick={onClose}
          className="w-full py-2 bg-gray-100 hover:bg-gray-200 text-gray-700 rounded-lg text-sm transition-colors"
        >
          Close
        </button>
      </div>
    </div>
  );
}

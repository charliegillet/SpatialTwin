import React from "react";
export function RoomBrand() {
  return (
    <div className="rl-toolbar-brand">
      <svg
        className="rl-fold-mark"
        viewBox="0 0 48 48"
        width="42"
        height="42"
        aria-hidden="true"
      >
        <path d="M3 11 24 4v21L3 33Z" fill="#68996b" />
        <path d="m24 4 21 18-21 3Z" fill="#9cbe96" />
        <path d="m24 25 21-3v23Z" fill="#3c714b" />
      </svg>
      <div>
        <h1 className="rl-title">SpatialTwin</h1>
        <span className="rl-brand-note">A new perspective.</span>
      </div>
    </div>
  );
}

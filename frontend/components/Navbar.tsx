"use client";

import Link from "next/link";
import { useState } from "react";
import { clearToken, getToken } from "@/lib/api";

export function Navbar() {
  const [open, setOpen] = useState(false);
  const token = getToken();

  return (
    <nav className="sticky top-0 z-40 border-b bg-background/95 backdrop-blur">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center gap-2">
            <span className="font-bold text-lg tracking-tight">DarPilot</span>
            <span className="text-xs font-mono text-muted-foreground">secure-by-design</span>
          </div>
          <div className="hidden md:flex items-center gap-6">
            <Link href="/" className="text-sm font-medium hover:underline">Home</Link>
            <Link href="/listings" className="text-sm font-medium hover:underline">Listings</Link>
            <Link href="/leads/new" className="text-sm font-medium hover:underline">Contact Us</Link>
            {token ? (
              <>
                <Link href="/dashboard" className="text-sm font-medium hover:underline">Dashboard</Link>
                <button
                  onClick={() => { clearToken(); window.location.reload(); }}
                  className="text-sm font-medium text-red-600 hover:underline"
                >
                  Logout
                </button>
              </>
            ) : (
              <>
                <span className="text-xs font-mono text-muted-foreground">not logged in</span>
              </>
            )}
          </div>
          <button
            className="md:hidden p-2 text-sm font-medium"
            onClick={() => setOpen(!open)}
            aria-label="Open menu"
          >
            Menu
          </button>
        </div>
      </div>
      {open && (
        <div className="md:hidden border-b border-border p-4 bg-background">
          <Link href="/" className="block py-2 text-sm font-medium hover:underline">Home</Link>
          <Link href="/listings" className="block py-2 text-sm font-medium hover:underline">Listings</Link>
          <Link href="/leads/new" className="block py-2 text-sm font-medium hover:underline">Contact Us</Link>
          {token ? (
            <>
              <Link href="/dashboard" className="block py-2 text-sm font-medium hover:underline">Dashboard</Link>
              <button
                onClick={() => { clearToken(); window.location.reload(); }}
                className="block py-2 text-sm font-medium text-red-600 hover:underline"
              >
                Logout
              </button>
            </>
          ) : null}
        </div>
      )}
    </nav>
  );
}



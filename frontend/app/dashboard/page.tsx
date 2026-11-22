"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, clearToken, getToken, type Listing } from "@/lib/api";

function decodeToken(token: string): { sub?: string; role?: string } | null {
  try {
    const payload = token.split(".")[1];
    if (!payload) return null;
    const decoded = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(decoded);
  } catch {
    return null;
  }
}

export default function DashboardPage() {
  const [token] = useState<string | null>(() => getToken());
  const claims = token ? decodeToken(token) : null;
  const userId = claims?.sub ? Number(claims.sub) : null;
  const userRole = claims?.role || null;
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState<boolean>(!!token);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    api.getListings()
      .then((data) => {
        setListings(userRole === "admin" ? data : data.filter((l) => l.agent_id === userId));
      })
      .catch(() => setError("Failed to load listings"))
      .finally(() => setLoading(false));
  }, [token, userId, userRole]);

  function handleLogout() {
    clearToken();
    window.location.reload();
  }

  if (loading) return <div className="py-12 text-center">Loading...</div>;

  if (!token) {
    return (
      <div className="max-w-md mx-auto px-4 py-12">
        <h1 className="text-2xl font-bold mb-6">Agent dashboard</h1>
        <p className="text-muted-foreground mb-6">
          Log in to manage your listings and leads.
        </p>
        <div className="text-sm text-muted-foreground mb-6">
          Register via the API (POST /auth/register) with role &quot;agent&quot; or
          &quot;admin&quot;, then log in (POST /auth/login).
        </div>
        <button
          onClick={handleLogout}
          className="inline-block text-sm font-medium text-red-600 hover:underline"
        >
          Logout
        </button>
      </div>
    );
  }

  const myListings = userRole === "admin" ? listings : listings.filter((l) => l.agent_id === userId);

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Agent dashboard</h1>
          <p className="text-muted-foreground">
            Logged in as {userId} ({userRole})
          </p>
        </div>
        <button
          onClick={handleLogout}
          className="text-sm font-medium text-red-600 hover:underline"
        >
          Logout
        </button>
      </div>

      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 text-red-700 text-sm border border-red-100">{error}</div>
      )}

      <div className="mb-6">
        <h2 className="text-lg font-semibold mb-3">Listings ({myListings.length})</h2>
        {myListings.length === 0 ? (
          <p className="text-muted-foreground">No listings assigned to you.</p>
        ) : (
          <div className="grid gap-4 md:grid-cols-3">
            {myListings.map((l) => (
              <div key={l.id} className="border rounded-xl p-4">
                <span className="text-xs font-medium uppercase tracking-wider text-blue-600">{l.property_type}</span>
                <h3 className="font-bold text-lg mb-1">{l.title}</h3>
                <p className="text-sm text-muted-foreground">{l.city}, {l.neighborhood}</p>
                <div className="flex items-baseline gap-1 mt-2">
                  <span className="text-xl font-bold">{l.price_mad.toLocaleString()}</span>
                  <span className="text-sm text-muted-foreground"> MAD</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="mt-8 flex gap-4">
        <Link href="/listings" className="px-4 py-2 border rounded hover:bg-blue-700 hover:text-white transition-colors">
          Browse all listings
        </Link>
        <Link href="/leads/new" className="px-4 py-2 border rounded hover:bg-blue-700 hover:text-white transition-colors">
          Create lead
        </Link>
      </div>
    </div>
  );
}

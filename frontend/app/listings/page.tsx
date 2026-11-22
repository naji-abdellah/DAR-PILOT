"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Listing } from "@/lib/api";

export default function ListingsPage() {
  const [listings, setListings] = useState<Listing[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getListings()
      .then((data) => setListings(data))
      .catch((err) => setError(err instanceof Error ? err.message : "Failed to load listings"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="py-12 text-center">Loading listings...</div>;
  if (error) return (
    <div className="py-12 text-center text-red-600">{error}</div>
  );

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Listings</h1>
        <p className="text-muted-foreground">{listings.length} properties available</p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {listings.map((listing) => (
          <Link
            key={listing.id}
            href={`/listings/${listing.id}`}
            className="group block border rounded-xl p-4 hover:border-blue-600 hover:shadow-md transition-all"
          >
            <div className="flex justify-between items-start mb-2">
              <span className="text-xs font-medium uppercase tracking-wider text-blue-600">{listing.property_type}</span>
              <span className="text-sm font-semibold">{listing.city}, {listing.neighborhood}</span>
            </div>
            <h3 className="font-bold text-lg mb-1 group-hover:underline">{listing.title}</h3>
            <p className="text-sm text-muted-foreground line-clamp-2 mb-3">{listing.description}</p>
            <div className="flex items-baseline gap-1">
              <span className="text-xl font-bold">{listing.price_mad.toLocaleString()}</span>
              <span className="text-sm text-muted-foreground"> MAD</span>
            </div>
            <div className="mt-3 flex items-center gap-1">
              <span className={`text-xs font-medium rounded-full px-2 py-0.5 ${
                listing.status === "available" ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-600"
              }`}>
                {listing.status}
              </span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}



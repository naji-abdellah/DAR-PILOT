import Link from "next/link";
import { api, type Listing } from "@/lib/api";

export default async function ListingDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const listingId = Number(id);

  let listing: Listing | null = null;
  let error: string | null = null;

  try {
    listing = await api.getListing(listingId);
  } catch (err) {
    error = err instanceof Error ? err.message : "Failed to load listing";
  }

  if (error || !listing) {
    return (
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-12 text-center">
        {error || "Listing not found"}
        <br />
        <Link href="/listings" className="mt-4 inline-block text-sm underline text-blue-600 hover:underline">
          Back to listings
        </Link>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">{listing.title}</h1>
        <Link href="/listings" className="text-sm underline text-blue-600 hover:underline">
          Back to listings
        </Link>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <div className="bg-background p-6 rounded-xl border">
          <h2 className="text-lg font-semibold mb-3">Details</h2>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between">
              <dt className="text-muted-foreground">City</dt>
              <dd className="font-medium">{listing.city}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Neighborhood</dt>
              <dd className="font-medium">{listing.neighborhood}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Type</dt>
              <dd className="font-medium">{listing.property_type}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Status</dt>
              <dd className={`font-medium ${
                listing.status === "available" ? "text-green-600" : "text-gray-600"
              }`}>{listing.status}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Price</dt>
              <dd className="font-bold">{listing.price_mad.toLocaleString()} MAD</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted-foreground">Agent</dt>
              <dd className="font-medium">{listing.agent_id ?? "Not assigned"}</dd>
            </div>
          </dl>
        </div>

        <div>
          <h2 className="text-lg font-semibold mb-3">Description</h2>
          <p className="text-muted-foreground mb-6 whitespace-pre-line">{listing.description}</p>

          <div className="bg-blue-600 p-6 rounded-xl text-white max-w-md">
            <h3 className="text-lg font-bold mb-4">Interested in this listing?</h3>
            <Link
              href={`/leads/new?listing_id=${listing.id}`}
              className="block w-full text-center bg-white text-blue-600 px-4 py-2 rounded-lg font-medium hover:bg-gray-100 transition-colors"
            >
              Send a message
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}

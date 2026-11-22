"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";

export default function LeadFormPage({
  defaultListingId,
}: {
  defaultListingId?: number;
}) {
  const router = useRouter();
  const [form, setForm] = useState({
    name: "",
    phone: "",
    email: "",
    message: "",
    listing_id: defaultListingId,
    status: "new" as const,
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.createLead({
        name: form.name,
        phone: form.phone || undefined,
        email: form.email,
        message: form.message,
        listing_id: form.listing_id,
        status: form.status,
      });
      setSuccess(true);
      setForm({
        name: "",
        phone: "",
        email: "",
        message: "",
        listing_id: defaultListingId,
        status: "new",
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to send message");
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="max-w-md mx-auto px-4 py-12 text-center">
        <h1 className="text-2xl font-bold text-green-600">Message sent!</h1>
        <p className="mt-2 text-muted-foreground">An agent will get back to you shortly.</p>
        <button
          onClick={() => router.push("/listings")}
          className="mt-6 inline-block px-4 py-2 border rounded hover:bg-blue-700 hover:text-white transition-colors"
        >
          Browse listings
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-2xl font-bold mb-6">Contact an agent</h1>
      {error && (
        <div className="mb-4 p-3 rounded bg-red-50 text-red-700 text-sm border border-red-100">{error}</div>
      )}
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium mb-1">Full name</label>
          <input
            className="w-full border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            placeholder="Youssef Benali"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Email</label>
          <input
            type="email"
            className="w-full border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
            value={form.email}
            onChange={(e) => setForm({ ...form, email: e.target.value })}
            placeholder="youssef@example.com"
            required
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Phone (optional)</label>
          <input
            type="tel"
            className="w-full border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
            value={form.phone}
            onChange={(e) => setForm({ ...form, phone: e.target.value })}
            placeholder="0612345678"
          />
        </div>
        <div>
          <label className="block text-sm font-medium mb-1">Message</label>
          <textarea
            className="w-full border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-600"
            value={form.message}
            onChange={(e) => setForm({ ...form, message: e.target.value })}
            placeholder="I am interested in this listing..."
            rows={4}
          />
        </div>
        <input type="hidden" name="listing_id" value={String(form.listing_id ?? "")} />
        <button
          type="submit"
          disabled={loading}
          className="w-full bg-blue-600 text-white px-4 py-2 rounded font-medium disabled:opacity-50 hover:bg-blue-700 transition-colors"
        >
          {loading ? "Sending..." : "Send message"}
        </button>
      </form>
    </div>
  );
}

import Link from "next/link";

export default function Home() {
  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
      <div className="text-center mb-12">
        <h1 className="text-4xl font-bold tracking-tight mb-4">DarPilot</h1>
        <p className="text-lg text-muted-foreground">
          Secure-by-design AI assistant for a fictional Moroccan real-estate
          agency. Browse listings, book a visit, or contact an agent.
        </p>
      </div>

      <div className="grid gap-6 md:grid-cols-3 max-w-5xl mx-auto">
        <Link
          href="/listings"
          className="group block p-6 border rounded-xl hover:border-blue-600 hover:bg-accent/50 transition-colors"
        >
          <h2 className="text-lg font-semibold mb-2">Browse listings</h2>
          <p className="text-sm text-muted-foreground">View all available properties in Casablanca and Marrakech.</p>
        </Link>
        <Link
          href="/leads/new"
          className="group block p-6 border rounded-xl hover:border-blue-600 hover:bg-accent/50 transition-colors"
        >
          <h2 className="text-lg font-semibold mb-2">Contact an agent</h2>
          <p className="text-sm text-muted-foreground">Send a message about a listing and we will get back to you.</p>
        </Link>
        <div className="p-6 border rounded-xl bg-muted/50">
          <h2 className="text-lg font-semibold mb-2">Agent dashboard</h2>
          <p className="text-sm text-muted-foreground">Log in to manage your listings and leads.</p>
          <Link href="/dashboard" className="mt-4 inline-block text-sm font-medium underline">
            Go to dashboard
          </Link>
        </div>
      </div>
    </div>
  );
}

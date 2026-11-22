import LeadForm from "./form";

export const dynamic = "force-dynamic";

export default async function LeadFormPage({
  searchParams,
}: {
  searchParams: Promise<{ listing_id?: string }>;
}) {
  const params = await searchParams;
  const defaultListingId = params.listing_id ? Number(params.listing_id) : undefined;
  return <LeadForm defaultListingId={defaultListingId} />;
}

import { RecordsResearch } from "@/components/records-research";

export default async function RecordsPage({
  searchParams,
}: {
  searchParams: Promise<{ customer_reference?: string; appointment_reference?: string }>;
}) {
  const params = await searchParams;
  return (
    <div className="page">
      <div className="page-heading">
        <div>
          <p className="eyebrow">Authoritative operational data</p>
          <h1>Business records</h1>
          <p>Research the same customer, appointment, invoice, membership, and booking records available to the investigator.</p>
        </div>
      </div>
      <RecordsResearch
        initialCustomerReference={params.customer_reference ?? ""}
        initialAppointmentReference={params.appointment_reference ?? ""}
      />
    </div>
  );
}

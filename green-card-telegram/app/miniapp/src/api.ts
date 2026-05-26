export type Vehicle = {
  vehicle_country_registration: string;
  vehicle_type: string;
  insurance_start_date: string;
  insurance_period_days: number;
  license_plate: string;
  vin: string;
  brand_model: string;
  manufacture_year: number;
  engine_type: string;
  engine_capacity_cc?: number;
  engine_power?: number;
  power_unit: string;
  comment?: string;
  vehicle_docs: File[];
};

export type ApplicationPayload = {
  first_name: string;
  last_name: string;
  phone: string;
  email: string;
  preferred_language: string;
  policyholder_type: "individual" | "company";
  birth_date: string;
  registration_address: string;
  passport_series_number: string;
  company?: {
    company_name: string;
    company_inn?: string;
    company_country: string;
    company_legal_address: string;
    ceo_full_name: string;
    ceo_title: string;
  };
  vehicles: Vehicle[];
  terms_accepted: boolean;
  privacy_accepted: boolean;
  marketing_consent?: boolean;
  telegram_init_data?: string;
};

export async function submitApplication(payload: ApplicationPayload) {
  const fd = new FormData();
  fd.append("application_json", JSON.stringify({
    ...payload,
    vehicles: payload.vehicles.map((v) => ({ ...v, vehicle_docs: v.vehicle_docs.map((f) => f.name) })),
  }));
  for (const file of payload.vehicles[0]?.vehicle_docs || []) {
    fd.append("vehicle_docs", file);
  }

  const res = await fetch("/api/applications", { method: "POST", body: fd });
  return res.json();
}

import React, { useMemo, useState } from "react";
import StepContacts from "./components/StepContacts";
import StepPolicyholder from "./components/StepPolicyholder";
import StepVehicle from "./components/StepVehicle";
import StepConfirm from "./components/StepConfirm";
import { submitApplication } from "./api";
import ru from "./i18n/ru";
import en from "./i18n/en";
import pl from "./i18n/pl";
import ka from "./i18n/ka";
import kk from "./i18n/kk";

const dicts:any = { ru, en, pl, ka, kk };
const currentYear = new Date().getFullYear();

export default function App() {
  const initData = (window as any).Telegram?.WebApp?.initData || "";
  const [submitted, setSubmitted] = useState<any>(null);
  const [step, setStep] = useState(1);
  const [form, setForm] = useState<any>({
    first_name:"", last_name:"", phone:"", email:"", preferred_language:"ru",
    policyholder_type:"individual", birth_date:"", registration_address:"", passport_series_number:"",
    vehicles:[{vehicle_country_registration:"", vehicle_type:"car", insurance_start_date:"", insurance_period_days:30, license_plate:"", vin:"", brand_model:"", manufacture_year:currentYear, engine_type:"petrol", engine_capacity_cc:"", engine_power:"", power_unit:"hp", comment:"", vehicle_docs:[]}],
    terms_accepted:false, privacy_accepted:false, marketing_consent:false
  });
  const t = useMemo(()=>dicts[form.preferred_language] || ru, [form.preferred_language]);

  const validate = () => {
    if (!/^\+[1-9]\d{1,14}$/.test(form.phone)) return t.errors.phone;
    if (!/^\S+@\S+\.\S+$/.test(form.email)) return t.errors.email;
    if (form.vehicles[0].vin && form.vehicles[0].vin.length !== 17) return t.errors.vin;
    const y = Number(form.vehicles[0].manufacture_year);
    if (y < 1950 || y > currentYear) return t.errors.year;
    if (!form.terms_accepted) return t.errors.terms;
    if (!form.privacy_accepted) return t.errors.privacy;
    return "";
  };

  const onSubmit = async () => {
    if (submitted) return;
    const err = validate();
    if (err) return alert(err);
    const payload = { ...form, telegram_init_data: initData };
    const result = await submitApplication(payload);
    if (result?.detail) {
      const key = String(result.detail);
      if (key.includes("invalid_mime")) return alert(t.errors.upload_invalid_mime);
      if (key.includes("file_too_large")) return alert(t.errors.upload_file_too_large);
      if (key.includes("too_many_files")) return alert(t.errors.upload_too_many_files);
      return alert(key);
    }
    setSubmitted(result);
  };

  return <div>
    <h1>{t.appTitle}</h1>
    {step===1 && <><h3>{t.step1}</h3><StepContacts form={form} setForm={setForm}/></>}
    {step===2 && <><h3>{t.step2}</h3><StepPolicyholder form={form} setForm={setForm}/></>}
    {step===3 && <><h3>{t.step3}</h3><StepVehicle form={form} setForm={setForm}/></>}
    {step===4 && <><h3>{t.step4}</h3><StepConfirm form={form} setForm={setForm}/></>}

    <button onClick={()=>setStep(Math.max(1, step-1))}>{t.back}</button>
    {step<4 ? <button onClick={()=>setStep(Math.min(4, step+1))}>{t.next}</button> : <button disabled={!!submitted} onClick={onSubmit}>{t.submit}</button>}

    {submitted && <div><p>{t.submitted}</p><p>{t.requestId}: {submitted.request_id}</p><p>{t.noResubmit}</p></div>}
  </div>;
}

import React from "react";
export default function StepPolicyholder({ form, setForm }: any) {
  const company = form.company || {};
  return <div>
    <select value={form.policyholder_type} onChange={(e)=>setForm({...form, policyholder_type:e.target.value})}><option value="individual">individual</option><option value="company">company</option></select>
    <input value={form.birth_date} onChange={(e)=>setForm({...form, birth_date:e.target.value})} placeholder="birth_date"/>
    <input value={form.registration_address} onChange={(e)=>setForm({...form, registration_address:e.target.value})} placeholder="registration_address"/>
    <input value={form.passport_series_number} onChange={(e)=>setForm({...form, passport_series_number:e.target.value})} placeholder="passport_series_number"/>
    {form.policyholder_type === "company" && <>
      <input value={company.company_name||""} onChange={(e)=>setForm({...form, company:{...company, company_name:e.target.value}})} placeholder="company_name"/>
      <input value={company.company_inn||""} onChange={(e)=>setForm({...form, company:{...company, company_inn:e.target.value}})} placeholder="company_inn"/>
      <input value={company.company_country||""} onChange={(e)=>setForm({...form, company:{...company, company_country:e.target.value}})} placeholder="company_country"/>
      <input value={company.company_legal_address||""} onChange={(e)=>setForm({...form, company:{...company, company_legal_address:e.target.value}})} placeholder="company_legal_address"/>
      <input value={company.ceo_full_name||""} onChange={(e)=>setForm({...form, company:{...company, ceo_full_name:e.target.value}})} placeholder="ceo_full_name"/>
      <input value={company.ceo_title||""} onChange={(e)=>setForm({...form, company:{...company, ceo_title:e.target.value}})} placeholder="ceo_title"/>
    </>}
  </div>;
}

import React from "react";
export default function StepContacts({ form, setForm }: any) {
  return <div>
    <input value={form.first_name} onChange={(e)=>setForm({...form, first_name:e.target.value})} placeholder="first_name"/>
    <input value={form.last_name} onChange={(e)=>setForm({...form, last_name:e.target.value})} placeholder="last_name"/>
    <input value={form.phone} onChange={(e)=>setForm({...form, phone:e.target.value})} placeholder="phone"/>
    <input value={form.email} onChange={(e)=>setForm({...form, email:e.target.value})} placeholder="email"/>
    <input value={form.preferred_language} onChange={(e)=>setForm({...form, preferred_language:e.target.value})} placeholder="preferred_language"/>
  </div>;
}

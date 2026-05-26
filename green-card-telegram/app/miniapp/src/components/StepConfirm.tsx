import React from "react";
export default function StepConfirm({ form, setForm }: any) {
  return <div>
    <label><input type="checkbox" checked={form.terms_accepted} onChange={(e)=>setForm({...form,terms_accepted:e.target.checked})}/>terms_accepted</label>
    <label><input type="checkbox" checked={form.privacy_accepted} onChange={(e)=>setForm({...form,privacy_accepted:e.target.checked})}/>privacy_accepted</label>
    <label><input type="checkbox" checked={form.marketing_consent} onChange={(e)=>setForm({...form,marketing_consent:e.target.checked})}/>marketing_consent</label>
  </div>;
}

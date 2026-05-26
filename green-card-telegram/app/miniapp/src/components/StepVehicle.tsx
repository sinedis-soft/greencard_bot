import React from "react";
export default function StepVehicle({ form, setForm }: any) {
  const v = form.vehicles[0];
  const update=(k:string,val:any)=>setForm({...form, vehicles:[{...v,[k]:val}]});
  return <div>
    {Object.keys(v).filter(k=>k!="vehicle_docs").map((k)=><input key={k} value={(v as any)[k] ?? ""} onChange={(e)=>update(k,e.target.value)} placeholder={k}/>)}
    <input type="file" multiple accept=".jpg,.jpeg,.png,.pdf" onChange={(e)=>{
      const files=[...(e.target.files||[])].filter(f=>f.size<=10*1024*1024);
      update("vehicle_docs", files);
    }}/>
  </div>;
}

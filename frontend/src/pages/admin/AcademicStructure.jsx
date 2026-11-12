import { useEffect, useState } from "react";
import { Plus, RefreshCw, Building2, Layers3, GraduationCap, Trash2, Pencil } from "lucide-react";
import MainLayout from "../../layouts/MainLayout";
import { useAuth } from "../../context/AuthContext";
import { getAcademicDirectory, createFaculty, createDepartment, createProgramme, updateFaculty, updateDepartment, updateProgramme, deleteFaculty, deleteDepartment, deleteProgramme } from "../../services/api";

export default function AcademicStructure() {
  const { user } = useAuth();
  const admin = user?.role === "admin";
  const [directory, setDirectory] = useState({ faculties: [], departments: [], programmes: [] });
  const [facultyForm, setFacultyForm] = useState({ name: "", code: "", dean: "" });
  const [departmentForm, setDepartmentForm] = useState({ name: "", code: "", faculty_id: "" });
  const [programmeForm, setProgrammeForm] = useState({ name: "", code: "", department_id: user?.department_id || "", award: "BSc", duration_years: 4 });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = async () => {
    setError("");
    try { setDirectory(await getAcademicDirectory(admin)); }
    catch (e) { setError(e.message || "Academic directory could not be loaded."); }
  };
  useEffect(() => { load(); }, [admin]);
  const run = async (action, success) => {
    setBusy(true); setError(""); setNotice("");
    try { await action(); setNotice(success); await load(); return true; }
    catch (e) { setError(e.message || "The operation could not be completed."); return false; }
    finally { setBusy(false); }
  };
  const submit = async (e, fn, form, reset) => { e.preventDefault(); const saved = await run(() => fn(form), "Academic directory updated successfully."); if (saved) reset(); };
  const renameFaculty = f => { const name=window.prompt("Faculty / school name",f.name); if(name?.trim()) run(()=>updateFaculty(f.id,{name:name.trim(),code:f.code,dean:f.dean}),"Faculty updated."); };
  const renameDepartment = d => { const name=window.prompt("Department name",d.name); if(name?.trim()) run(()=>updateDepartment(d.id,{name:name.trim(),code:d.code,faculty_id:d.faculty_id,head:d.head}),"Department updated."); };
  const renameProgramme = p => { const name=window.prompt("Programme name",p.name); if(name?.trim()) run(()=>updateProgramme(p.id,{name:name.trim(),code:p.code,department_id:p.department_id,award:p.award,duration_years:p.duration_years}),"Programme updated."); };

  return <MainLayout>
    <div className="space-y-6 py-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div><p className="text-xs font-bold tracking-widest text-blue-700">ACADEMIC DIRECTORY</p><h1 className="text-2xl font-bold text-slate-900">{admin ? "Institution structure" : "Department programmes"}</h1><p className="text-sm text-slate-500 mt-1">{admin ? "Maintain faculties and departments. Lecturers manage programmes within their assigned departments." : "Create and maintain the programmes offered by your department."}</p></div>
        <button type="button" onClick={load} className="refresh-btn"><RefreshCw size={15}/> Refresh</button>
      </div>
      {error && <div role="alert" className="rounded-xl bg-red-50 text-red-700 p-3 text-sm">{error}</div>}
      {notice && <div role="status" className="rounded-xl bg-emerald-50 text-emerald-700 p-3 text-sm">{notice}</div>}
      {admin && <section className="grid lg:grid-cols-2 gap-4">
        <form className="academic-panel space-y-3" onSubmit={e=>submit(e,createFaculty,facultyForm,()=>setFacultyForm({name:"",code:"",dean:""}))}>
          <h2 className="font-semibold flex items-center gap-2"><Building2 size={18}/> Add faculty / school</h2>
          <input className="w-full border rounded-lg p-2" placeholder="Faculty or school name" required value={facultyForm.name} onChange={e=>setFacultyForm(v=>({...v,name:e.target.value}))}/>
          <div className="grid grid-cols-2 gap-2"><input className="border rounded-lg p-2" placeholder="Code (optional)" value={facultyForm.code} onChange={e=>setFacultyForm(v=>({...v,code:e.target.value}))}/><input className="border rounded-lg p-2" placeholder="Dean (optional)" value={facultyForm.dean} onChange={e=>setFacultyForm(v=>({...v,dean:e.target.value}))}/></div>
          <button disabled={busy} className="primary-btn"><Plus size={15}/> Add faculty</button>
        </form>
        <form className="academic-panel space-y-3" onSubmit={async e=>{e.preventDefault();const saved=await run(()=>createDepartment({...departmentForm,faculty_id:Number(departmentForm.faculty_id)}),"Department created.");if(saved)setDepartmentForm({name:"",code:"",faculty_id:""});}}>
          <h2 className="font-semibold flex items-center gap-2"><Layers3 size={18}/> Add department</h2>
          <input className="w-full border rounded-lg p-2" placeholder="Department name" required value={departmentForm.name} onChange={e=>setDepartmentForm(v=>({...v,name:e.target.value}))}/>
          <select className="w-full border rounded-lg p-2" required value={departmentForm.faculty_id} onChange={e=>setDepartmentForm(v=>({...v,faculty_id:e.target.value}))}><option value="">Select faculty / school</option>{directory.faculties.map(f=><option key={f.id} value={f.id}>{f.name}</option>)}</select>
          <input className="w-full border rounded-lg p-2" placeholder="Department code (optional)" value={departmentForm.code} onChange={e=>setDepartmentForm(v=>({...v,code:e.target.value}))}/>
          <button disabled={busy || !directory.faculties.length} className="primary-btn"><Plus size={15}/> Add department</button>
        </form>
      </section>}
      {!admin && <section className="academic-panel space-y-3">
        <h2 className="font-semibold flex items-center gap-2"><GraduationCap size={18}/> Create a department programme</h2>
        <form className="grid md:grid-cols-2 gap-3" onSubmit={async e=>{e.preventDefault();const saved=await run(()=>createProgramme({...programmeForm,department_id:Number(programmeForm.department_id),duration_years:Number(programmeForm.duration_years)}),"Programme created.");if(saved)setProgrammeForm(v=>({...v,name:"",code:""}));}}>
          <input className="border rounded-lg p-2" placeholder="Programme name" required value={programmeForm.name} onChange={e=>setProgrammeForm(v=>({...v,name:e.target.value}))}/>
          <input className="border rounded-lg p-2" placeholder="Programme code (optional)" value={programmeForm.code} onChange={e=>setProgrammeForm(v=>({...v,code:e.target.value}))}/>
          <select className="border rounded-lg p-2" required value={programmeForm.department_id} onChange={e=>setProgrammeForm(v=>({...v,department_id:e.target.value}))}><option value="">Select department</option>{directory.departments.filter(d=>admin || d.id===user?.department_id).map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select>
          <div className="flex gap-2"><input className="min-w-0 flex-1 border rounded-lg p-2" placeholder="Award e.g. BSc" value={programmeForm.award} onChange={e=>setProgrammeForm(v=>({...v,award:e.target.value}))}/><input className="w-28 border rounded-lg p-2" type="number" min="1" max="12" value={programmeForm.duration_years} onChange={e=>setProgrammeForm(v=>({...v,duration_years:e.target.value}))}/></div>
          <button disabled={busy || !directory.departments.some(d=>admin || d.id===user?.department_id)} className="primary-btn md:col-span-2"><Plus size={15}/> Create programme</button>
        </form>
      </section>}
      {admin && <section className="academic-panel"><h2 className="font-semibold mb-3">Faculties and departments</h2><div className="grid md:grid-cols-2 gap-3">{directory.faculties.map(f=><article key={f.id} className="border rounded-xl p-3"><div className="flex justify-between gap-2"><b>{f.name}</b><button type="button" title="Edit faculty" onClick={()=>renameFaculty(f)} className="text-blue-700" aria-label={`Edit ${f.name}`}><Pencil size={15}/></button><button type="button" title="Delete faculty" onClick={()=>run(()=>deleteFaculty(f.id),"Faculty deleted.")} className="text-red-600" aria-label={`Delete ${f.name}`}><Trash2 size={15}/></button></div><div className="mt-2 space-y-2">{directory.departments.filter(d=>d.faculty_id===f.id).map(d=><div key={d.id} className="flex justify-between items-center text-sm border-t pt-2"><span>{d.name}</span><div className="flex gap-2"><button type="button" onClick={()=>renameDepartment(d)} className="text-blue-700" aria-label={`Edit ${d.name}`}><Pencil size={14}/></button><button type="button" onClick={()=>run(()=>deleteDepartment(d.id),"Department deleted.")} className="text-red-600" aria-label={`Delete ${d.name}`}><Trash2 size={14}/></button></div></div>)}{!directory.departments.some(d=>d.faculty_id===f.id)&&<p className="text-xs text-slate-400">No departments yet.</p>}</div></article>)}</div></section>}
      <section className="academic-panel"><h2 className="font-semibold mb-3">Programmes</h2><div className="overflow-x-auto"><table className="w-full min-w-[600px] text-sm"><thead><tr className="text-left border-b text-slate-500"><th className="py-2">Programme</th><th>Code</th><th>Department</th><th>Award</th><th>Duration</th>{!admin&&<th>Action</th>}</tr></thead><tbody>{directory.programmes.filter(p=>admin || directory.departments.find(d=>d.id===p.department_id)?.id===user?.department_id).map(p=><tr key={p.id} className="border-b"><td className="py-3 font-medium">{p.name}</td><td>{p.code||"—"}</td><td>{directory.departments.find(d=>d.id===p.department_id)?.name||"—"}</td><td>{p.award||"—"}</td><td>{p.duration_years||"—"} years</td>{!admin&&<td><div className="flex gap-2"><button type="button" onClick={()=>renameProgramme(p)} className="text-blue-700" aria-label={`Edit ${p.name}`}><Pencil size={14}/></button><button type="button" onClick={()=>run(()=>deleteProgramme(p.id),"Programme deleted.")} className="text-red-600" aria-label={`Delete ${p.name}`}><Trash2 size={15}/></button></div></td>}</tr>)}</tbody></table></div>{!directory.programmes.length&&<p className="text-sm text-slate-500 py-3">No programmes have been created yet.</p>}</section>
    </div>
  </MainLayout>;
}

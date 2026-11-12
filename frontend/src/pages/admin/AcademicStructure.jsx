import { useCallback, useEffect, useState } from "react";
import { Plus, RefreshCw, Building2, Layers3, GraduationCap, Trash2, Pencil, Eye } from "lucide-react";
import MainLayout from "../../layouts/MainLayout";
import { useAuth } from "../../context/AuthContext";
import { getAcademicDirectory, getMyAcademicDirectory, createFaculty, createDepartment, createProgramme, updateFaculty, updateDepartment, updateProgramme, deleteFaculty, deleteDepartment, deleteProgramme } from "../../services/api";

const emptyFaculty = { name: "", code: "", dean: "" };
const emptyDepartment = { name: "", code: "", faculty_id: "", head: "" };
const emptyProgramme = { name: "", code: "", department_id: "", award: "BSc", duration_years: 4 };

export default function AcademicStructure() {
  const { user } = useAuth();
  const admin = user?.role === "admin";
  const [directory, setDirectory] = useState({ faculties: [], departments: [], programmes: [] });
  const [facultyForm, setFacultyForm] = useState(emptyFaculty);
  const [departmentForm, setDepartmentForm] = useState(emptyDepartment);
  const [programmeForm, setProgrammeForm] = useState(emptyProgramme);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      const data = admin ? await getAcademicDirectory(true) : await getMyAcademicDirectory();
      setDirectory(data || { faculties: [], departments: [], programmes: [] });
    } catch (e) { setError(e.message || "Academic directory could not be loaded."); }
  }, [admin]);

  useEffect(() => { load(); }, [load]);

  const run = async (action, success) => {
    setBusy(true); setError(""); setNotice("");
    try { await action(); setNotice(success); await load(); return true; }
    catch (e) { setError(e.message || "The operation could not be completed."); return false; }
    finally { setBusy(false); }
  };

  const submit = async (e, fn, form, reset) => {
    e.preventDefault();
    const saved = await run(() => fn(form), "Academic structure saved successfully.");
    if (saved) reset();
  };

  const editFaculty = (item) => {
    const name = window.prompt("Faculty / school name", item.name);
    if (name?.trim()) run(() => updateFaculty(item.id, { name: name.trim(), code: item.code || "", dean: item.dean || "" }), "Faculty updated.");
  };
  const editDepartment = (item) => {
    const name = window.prompt("Department name", item.name);
    if (name?.trim()) run(() => updateDepartment(item.id, { name: name.trim(), code: item.code || "", faculty_id: item.faculty_id, head: item.head || "" }), "Department updated.");
  };
  const editProgramme = (item) => {
    const name = window.prompt("Programme name", item.name);
    if (name?.trim()) run(() => updateProgramme(item.id, { name: name.trim(), code: item.code || "", department_id: item.department_id, award: item.award || "", duration_years: item.duration_years || 4 }), "Programme updated.");
  };

  return <MainLayout>
    <div className="space-y-6 py-2">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-xs font-bold tracking-widest text-blue-700">ACADEMIC DIRECTORY</p>
          <h1 className="text-2xl font-bold text-slate-900">{admin ? "Institution oversight" : "Build your institution"}</h1>
          <p className="text-sm text-slate-500 mt-1">{admin ? "View academic structures across institutions. Administrators monitor; lecturers create and maintain their institution's structure." : "Set up your institution's faculties, departments and programmes. You can then create courses for those programmes."}</p>
          {!admin && <p className="text-sm font-semibold text-slate-700 mt-2">Institution: {user?.institution_name || "Not set"}</p>}
        </div>
        <button type="button" onClick={load} className="refresh-btn" disabled={busy}><RefreshCw size={15}/> Refresh</button>
      </div>
      {error && <div role="alert" className="rounded-xl bg-red-50 text-red-700 p-3 text-sm">{error}</div>}
      {notice && <div role="status" className="rounded-xl bg-emerald-50 text-emerald-700 p-3 text-sm">{notice}</div>}

      {!admin && <section className="grid lg:grid-cols-2 gap-4">
        <form className="academic-panel space-y-3" onSubmit={e => submit(e, createFaculty, facultyForm, () => setFacultyForm(emptyFaculty))}>
          <h2 className="font-semibold flex items-center gap-2"><Building2 size={18}/> Create faculty / school</h2>
          <input className="w-full border rounded-lg p-2" placeholder="Faculty or school name" required minLength={2} value={facultyForm.name} onChange={e => setFacultyForm(v => ({ ...v, name: e.target.value }))}/>
          <input className="w-full border rounded-lg p-2" placeholder="Faculty code (optional)" value={facultyForm.code} onChange={e => setFacultyForm(v => ({ ...v, code: e.target.value }))}/>
          <input className="w-full border rounded-lg p-2" placeholder="Dean / head (optional)" value={facultyForm.dean} onChange={e => setFacultyForm(v => ({ ...v, dean: e.target.value }))}/>
          <button className="sc-button sc-button-primary" disabled={busy}><Plus size={15}/> Add faculty</button>
        </form>

        <form className="academic-panel space-y-3" onSubmit={e => submit(e, createDepartment, { ...departmentForm, faculty_id: Number(departmentForm.faculty_id) }, () => setDepartmentForm(emptyDepartment))}>
          <h2 className="font-semibold flex items-center gap-2"><Layers3 size={18}/> Create department</h2>
          <input className="w-full border rounded-lg p-2" placeholder="Department name" required minLength={2} value={departmentForm.name} onChange={e => setDepartmentForm(v => ({ ...v, name: e.target.value }))}/>
          <select className="w-full border rounded-lg p-2" required value={departmentForm.faculty_id} onChange={e => setDepartmentForm(v => ({ ...v, faculty_id: e.target.value }))}><option value="">Select faculty / school</option>{directory.faculties.map(f => <option key={f.id} value={f.id}>{f.name}</option>)}</select>
          <input className="w-full border rounded-lg p-2" placeholder="Department code (optional)" value={departmentForm.code} onChange={e => setDepartmentForm(v => ({ ...v, code: e.target.value }))}/>
          <button className="sc-button sc-button-primary" disabled={busy || !directory.faculties.length}><Plus size={15}/> Add department</button>
        </form>

        <form className="academic-panel space-y-3 lg:col-span-2" onSubmit={e => submit(e, createProgramme, { ...programmeForm, department_id: Number(programmeForm.department_id), duration_years: Number(programmeForm.duration_years) }, () => setProgrammeForm(emptyProgramme))}>
          <h2 className="font-semibold flex items-center gap-2"><GraduationCap size={18}/> Create programme</h2>
          <div className="grid md:grid-cols-2 gap-3">
            <input className="w-full border rounded-lg p-2" placeholder="Programme name" required minLength={2} value={programmeForm.name} onChange={e => setProgrammeForm(v => ({ ...v, name: e.target.value }))}/>
            <select className="w-full border rounded-lg p-2" required value={programmeForm.department_id} onChange={e => setProgrammeForm(v => ({ ...v, department_id: e.target.value }))}><option value="">Select department</option>{directory.departments.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
            <input className="w-full border rounded-lg p-2" placeholder="Programme code (optional)" value={programmeForm.code} onChange={e => setProgrammeForm(v => ({ ...v, code: e.target.value }))}/>
            <input className="w-full border rounded-lg p-2" placeholder="Award (e.g. BSc)" value={programmeForm.award} onChange={e => setProgrammeForm(v => ({ ...v, award: e.target.value }))}/>
            <input className="w-full border rounded-lg p-2" type="number" min="1" max="12" value={programmeForm.duration_years} onChange={e => setProgrammeForm(v => ({ ...v, duration_years: e.target.value }))}/>
          </div>
          <button className="sc-button sc-button-primary" disabled={busy || !directory.departments.length}><Plus size={15}/> Add programme</button>
        </form>
      </section>}

      <section className="academic-panel">
        <div className="flex items-center gap-2 mb-3"><Building2 size={18}/><h2 className="font-semibold">Faculties / Schools</h2></div>
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-3">
          {directory.faculties.map(f => <article key={f.id} className="rounded-xl border p-4"><div className="flex justify-between gap-2"><div><b>{f.name}</b><p className="text-xs text-slate-500">{f.code || "No code"}{admin && f.institution_name ? " · " + f.institution_name : ""}</p></div>{admin ? <Eye size={16}/> : <div className="flex gap-2"><button type="button" onClick={() => editFaculty(f)} aria-label="Edit faculty"><Pencil size={15}/></button><button type="button" onClick={() => run(() => deleteFaculty(f.id), "Faculty deleted.")} aria-label="Delete faculty" className="text-red-600"><Trash2 size={15}/></button></div>}</div><p className="text-xs text-slate-500 mt-2">{directory.departments.filter(d => d.faculty_id === f.id).length} departments</p></article>)}
          {!directory.faculties.length && <p className="text-sm text-slate-500">No faculties have been created yet.</p>}
        </div>
      </section>

      <section className="academic-panel">
        <h2 className="font-semibold mb-3">Departments</h2>
        <div className="overflow-x-auto"><table className="w-full min-w-[600px] text-sm"><thead><tr className="text-left border-b text-slate-500"><th className="py-2">Department</th><th>Faculty / School</th><th>Code</th>{admin && <th>Institution</th>}{!admin && <th>Actions</th>}</tr></thead><tbody>{directory.departments.map(d => <tr key={d.id} className="border-b"><td className="py-3 font-medium">{d.name}</td><td>{directory.faculties.find(f => f.id === d.faculty_id)?.name || "—"}</td><td>{d.code || "—"}</td>{admin && <td>{d.institution_name || "—"}</td>}{!admin && <td><div className="flex gap-2"><button type="button" onClick={() => editDepartment(d)} aria-label="Edit department"><Pencil size={14}/></button><button type="button" onClick={() => run(() => deleteDepartment(d.id), "Department deleted.")} className="text-red-600" aria-label="Delete department"><Trash2 size={15}/></button></div></td>}</tr>)}</tbody></table></div>
        {!directory.departments.length && <p className="text-sm text-slate-500 py-3">No departments have been created yet.</p>}
      </section>

      <section className="academic-panel">
        <h2 className="font-semibold mb-3">Programmes</h2>
        <div className="overflow-x-auto"><table className="w-full min-w-[650px] text-sm"><thead><tr className="text-left border-b text-slate-500"><th className="py-2">Programme</th><th>Code</th><th>Department</th><th>Award</th><th>Duration</th>{admin && <th>Institution</th>}{!admin && <th>Actions</th>}</tr></thead><tbody>{directory.programmes.map(p => <tr key={p.id} className="border-b"><td className="py-3 font-medium">{p.name}</td><td>{p.code || "—"}</td><td>{directory.departments.find(d => d.id === p.department_id)?.name || "—"}</td><td>{p.award || "—"}</td><td>{p.duration_years || "—"} years</td>{admin && <td>{p.institution_name || "—"}</td>}{!admin && <td><div className="flex gap-2"><button type="button" onClick={() => editProgramme(p)} aria-label="Edit programme"><Pencil size={14}/></button><button type="button" onClick={() => run(() => deleteProgramme(p.id), "Programme deleted.")} className="text-red-600" aria-label="Delete programme"><Trash2 size={15}/></button></div></td>}</tr>)}</tbody></table></div>
        {!directory.programmes.length && <p className="text-sm text-slate-500 py-3">No programmes have been created yet.</p>}
      </section>
    </div>
  </MainLayout>;
}

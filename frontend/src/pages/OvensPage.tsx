import { useEffect, useState } from "react";
import { api } from "../api/client";
type O = { id: number; label: string; capacity_note: string; cool_min: number };
export default function OvensPage() {
  const [rows, setRows] = useState<O[]>([]);
  const [draft, setDraft] = useState<Record<number, number>>({});
  const [savedId, setSavedId] = useState<number | null>(null);
  const [err, setErr] = useState("");
  const reload = () => api<O[]>("/ovens").then(os => { setRows(os); setDraft(Object.fromEntries(os.map(o => [o.id, o.cool_min]))); });
  useEffect(() => { reload(); }, []);
  async function save(o: O) {
    setErr(""); setSavedId(null);
    const cool_min = Math.max(0, Math.min(24 * 60, Math.round(draft[o.id] ?? o.cool_min) || 0));
    try {
      const updated = await api<O>(`/ovens/${o.id}`, { method: "PATCH", body: JSON.stringify({ cool_min }) });
      setRows(rs => rs.map(r => r.id === o.id ? updated : r));
      setDraft(d => ({ ...d, [o.id]: updated.cool_min }));
      setSavedId(o.id);
      setTimeout(() => setSavedId(v => v === o.id ? null : v), 1500);
    } catch (e) { setErr(e instanceof Error ? e.message : String(e)); }
  }
  return (<>
    <h2>炉位</h2>
    <p className="hint">每座炉登记出炉后的半开冷却尾段：烘烤止起继续占炉，下一批最早冷却止才能开工。填 0 表示下一批可紧接烘烤结束端点排入。</p>
    {err && <div className="err">{err}</div>}
    <table className="table">
      <thead><tr><th>标签</th><th>备注</th><th>冷却分钟</th><th></th></tr></thead>
      <tbody>{rows.map(o => <tr key={o.id}>
        <td>{o.label}</td>
        <td>{o.capacity_note}</td>
        <td><input type="number" min={0} max={24 * 60} value={draft[o.id] ?? o.cool_min}
          onChange={e => setDraft(d => ({ ...d, [o.id]: Number(e.target.value) }))}
          onKeyDown={e => { if (e.key === "Enter") save(o); }}
          style={{ width: 90 }} /> <span className="muted">min</span></td>
        <td><button onClick={() => save(o)}>保存</button>{savedId === o.id && <span className="ok inline-ok">已存</span>}</td>
      </tr>)}</tbody>
    </table>
  </>);
}

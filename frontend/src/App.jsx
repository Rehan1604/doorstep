import { useEffect, useRef, useState } from "react";
import * as api from "./api.js";

const SCREEN_BUDGET_S = 45;
const INTERESTS = ["anything", "birds", "trees", "sounds", "photography", "light"];

function useStatus() {
  const [s, set] = useState({ online: navigator.onLine, ai: "checking" });
  useEffect(() => {
    const poll = () => api.health().then((h) => set((p) => ({ ...p, voice: !!h.voice, ai: h.provider === "ollama" ? (h.model_present ? "local" : "fallback") : (h.configured ? "cloud" : "fallback") })))
      .catch(() => set((p) => ({ ...p, ai: "down" })));
    const on = () => set((p) => ({ ...p, online: true })), off = () => set((p) => ({ ...p, online: false }));
    window.addEventListener("online", on); window.addEventListener("offline", off);
    poll(); const t = setInterval(poll, 8000);
    return () => { clearInterval(t); window.removeEventListener("online", on); window.removeEventListener("offline", off); };
  }, []);
  return s;
}

function Badge({ status }) {
  const ai = { local: "AI: LOCAL", cloud: "AI: READY", fallback: "AI: MODEL MISSING", down: "AI: OFFLINE", checking: "AI: …" }[status.ai];
  return (
    <div className="badge" role="status" aria-live="polite">
      <span className={status.online ? "dot" : "dot off"} /> INTERNET: {status.online ? "ON" : "DISCONNECTED"}
      <span className="sep">·</span> {ai} <span className="sep">·</span> DATA: {status.ai === "cloud" ? "CLOUD" : "LOCAL"}
    </div>
  );
}

function Home({ onGo, onHistory, history }) {
  const [minutes, setMinutes] = useState(20);
  const [energy, setEnergy] = useState("medium");
  const [interest, setInterest] = useState("anything");
  const [group, setGroup] = useState("solo");
  return (
    <main className="screen home">
      <h1>You have <em>{minutes} minutes.</em><br />Let’s do something real.</h1>
      <input aria-label="Minutes available" type="range" min="5" max="60" step="5" value={minutes} onChange={(e) => setMinutes(+e.target.value)} />
      <div className="row" role="group" aria-label="Energy">
        {["low", "medium", "high"].map((e) => <button key={e} className={"chip" + (energy === e ? " on" : "")} onClick={() => setEnergy(e)}>{e} energy</button>)}
      </div>
      <div className="row" role="group" aria-label="Interest">
        {INTERESTS.map((i) => <button key={i} className={"chip" + (interest === i ? " on" : "")} onClick={() => setInterest(i)}>{i}</button>)}
      </div>
      <div className="row" role="group" aria-label="Company">
        {["solo", "group"].map((g) => <button key={g} className={"chip" + (group === g ? " on" : "")} onClick={() => setGroup(g)}>{g}</button>)}
      </div>
      <button className="cta" onClick={() => onGo({ minutes, energy, interest, group })}>CREATE MY MISSION</button>
      {history && history.completed > 0 && <p className="foot">{history.minutes_outside} minutes outside so far. <button className="link" onClick={onHistory}>See them</button></p>}
    </main>
  );
}

function Breathe({ cloud }) {
  return (
    <main className="screen center">
      <div className="breath" aria-hidden="true" />
      <p className="soft">Your mission is being written {cloud ? "by a hosted model" : "on this machine"}.<br />Breathe in. Out.</p>
    </main>
  );
}

function MissionCard({ data, onStart }) {
  const { mission, source } = data;
  const [left, setLeft] = useState(SCREEN_BUDGET_S);
  const fired = useRef(false);
  useEffect(() => {
    const t = setInterval(() => setLeft((l) => l - 1), 1000);
    return () => clearInterval(t);
  }, []);
  useEffect(() => { if (left <= 0 && !fired.current) { fired.current = true; onStart(); } }, [left, onStart]);
  return (
    <main className="screen card">
      <div className="budget" aria-label={`Screen time left ${left} seconds`}>
        <div className="bar" style={{ width: `${(left / SCREEN_BUDGET_S) * 100}%` }} />
        <span>{Math.max(left, 0)}s of screen left</span>
      </div>
      <p className="meta">{mission.duration_minutes} MIN · {mission.difficulty.toUpperCase()}{source === "fallback" ? " · OFFLINE-SAFE MISSION" : ""}</p>
      {data.why && <p className="mlwhy"><span className="pill">{data.style_label}</span> {data.why}{data.novelty != null && <> <span className="pill">{Math.round(data.novelty * 100)}% new</span></>}</p>}
      <h2>{mission.title}</h2>
      <p className="obj">{mission.objective}</p>
      <ol>{mission.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
      <p className="why">{mission.why_it_matters}</p>
      <p className="safety">Safety: {mission.safety_notes.join(" ")} AI suggestions can be wrong; use your own judgement.</p>
      <button className="cta" onClick={onStart}>GO OUTSIDE</button>
    </main>
  );
}

function PhoneDown({ mission, onBack }) {
  const total = mission.duration_minutes * 60;
  const [left, setLeft] = useState(total);
  useEffect(() => { const t = setInterval(() => setLeft((l) => Math.max(l - 1, 0)), 1000); return () => clearInterval(t); }, []);
  const m = Math.floor(left / 60), s = String(left % 60).padStart(2, "0");
  return (
    <main className="screen down">
      <p className="phone">PHONE DOWN</p>
      <p className="big">{mission.steps[0]}</p>
      <p className="tiny">{m}:{s}</p>
      <button className="ghost" onClick={onBack}>I’m back</button>
    </main>
  );
}

function Complete({ onSubmit, busy, voice }) {
  const [completed, setCompleted] = useState(true);
  const [surprise, setSurprise] = useState("");
  const [feeling, setFeeling] = useState("better");
  const [rec, setRec] = useState("idle");
  const [note, setNote] = useState("");
  const mr = useRef(null);

  const toggle = async () => {
    if (rec === "recording") { mr.current.stop(); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = [];
      const r = new MediaRecorder(stream);
      r.ondataavailable = (e) => chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRec("working");
        try { setSurprise((await api.transcribe(new Blob(chunks, { type: r.mimeType }))).text.slice(0, 280)); setNote(""); }
        catch { setNote("Voice isn’t available right now. Type it instead."); }
        setRec("idle");
      };
      mr.current = r; r.start(); setRec("recording"); setNote("");
      setTimeout(() => r.state === "recording" && r.stop(), 30000);
    } catch { setNote("Microphone blocked. Type it instead."); }
  };

  return (
    <main className="screen home">
      <h1>Welcome back.</h1>
      <div className="row"><button className={"chip" + (completed ? " on" : "")} onClick={() => setCompleted(true)}>I did it</button>
        <button className={"chip" + (!completed ? " on" : "")} onClick={() => setCompleted(false)}>Not today</button></div>
      <label className="lbl" htmlFor="sp">What surprised you?</label>
      <textarea id="sp" maxLength={280} value={surprise} onChange={(e) => setSurprise(e.target.value)} rows={3} />
      {voice && <button className={"chip" + (rec === "recording" ? " on" : "")} onClick={toggle} disabled={rec === "working"}>
        {rec === "recording" ? "Stop (max 30s)" : rec === "working" ? "Transcribing locally…" : "Or say it out loud"}</button>}
      {note && <p className="soft" role="status">{note}</p>}
      <div className="row" role="group" aria-label="How do you feel">
        {[["worse", "worse"], ["same", "same"], ["better", "better"], ["much_better", "much better"]].map(([v, l]) =>
          <button key={v} className={"chip" + (feeling === v ? " on" : "")} onClick={() => setFeeling(v)}>{l}</button>)}
      </div>
      <button className="cta" disabled={busy || rec !== "idle"} onClick={() => onSubmit({ completed, surprise, feeling })}>{busy ? "WRITING…" : "FINISH"}</button>
    </main>
  );
}

function Insights({ data }) {
  if (!data || data.total < 1) return null;
  return (
    <section className="ins" aria-label="What works for you">
      <h3>What works for you</h3>
      {data.styles.map((s) => (
        <div className="insrow" key={s.style}>
          <span>{s.label}</span>
          <div className="insbar"><div style={{ width: `${Math.round(s.mean * 100)}%` }} /></div>
          <span className="soft">{s.good}/{s.n} felt better</span>
        </div>
      ))}
      <p className="soft">Learned only from your own feedback by a small bandit model.{data.best ? ` Right now: ${data.best}.` : ""}</p>
    </section>
  );
}

function History({ history, insights, onBack }) {
  const items = history?.items || [];
  return (
    <main className="screen">
      <h1>{history?.minutes_outside || 0} <em>minutes</em> outside.</h1>
      <p className="soft">{history?.completed || 0} missions completed. No streaks, no scores, no leaderboard.</p>
      <Insights data={insights} />
      {items.length === 0 && <p className="soft">Nothing yet. The first one is the hardest, and it’s only a few minutes.</p>}
      <ul className="hist">{items.map((i) => (
        <li key={i.id}><strong>{i.mission.title}</strong> <span className="soft">· {i.mission.duration_minutes} min</span>
          {i.surprise && <p>“{i.surprise}”</p>}{i.reflection && <p className="soft">{i.reflection}</p>}</li>))}</ul>
      <button className="ghost" onClick={onBack}>Back</button>
    </main>
  );
}

function Reflection({ text, recalled, onDone }) {
  return (
    <main className="screen center">
      <p className="reflect">{text}</p>
      {recalled > 0 && <p className="soft">Linked to an earlier note of yours.</p>}
      <button className="ghost" onClick={onDone}>Close</button>
    </main>
  );
}

export { Home, MissionCard, Badge, Insights };
export default function App() {
  const status = useStatus();
  const [view, setView] = useState("home");
  const [data, setData] = useState(null);
  const [text, setText] = useState("");
  const [err, setErr] = useState("");
  const [history, setHistory] = useState(null);
  const [insights, setInsights] = useState(null);
  const [recalled, setRecalled] = useState(0);
  useEffect(() => { api.getHistory().then(setHistory).catch(() => {}); }, [view]);
  useEffect(() => { if (view === "history") api.getInsights().then(setInsights).catch(() => {}); }, [view]);

  const go = async (req) => {
    setErr(""); setView("breathe");
    try { setData(await api.createMission(req)); setView("card"); }
    catch { setErr("The local server isn’t reachable. Start the backend and try again."); setView("home"); }
  };
  const finish = async (body) => {
    setView("busy");
    try { const r = await api.completeMission(data.id, body); setText(r.reflection); setRecalled(r.recalled || 0); }
    catch { setText("Saved nothing this time, but you went outside. That is the whole point."); }
    setView("reflect");
  };

  return (
    <>
      <Badge status={status} />
      {err && <div className="err" role="alert">{err}</div>}
      {view === "home" && <Home onGo={go} onHistory={() => setView("history")} history={history} />}
      {view === "history" && <History history={history} insights={insights} onBack={() => setView("home")} />}
      {view === "breathe" && <Breathe cloud={status.ai === "cloud"} />}
      {view === "card" && <MissionCard data={data} onStart={() => setView("down")} />}
      {view === "down" && <PhoneDown mission={data.mission} onBack={() => setView("complete")} />}
      {(view === "complete" || view === "busy") && <Complete onSubmit={finish} busy={view === "busy"} voice={status.voice} />}
      {view === "reflect" && <Reflection text={text} recalled={recalled} onDone={() => { setData(null); setView("home"); }} />}
    </>
  );
}
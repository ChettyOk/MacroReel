import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import type { DailyLogWeekDay, DailyTargets, Profile } from "../api";
import * as api from "../api";
import { ACTIVITY_LEVELS, ALLERGENS, DIETARY_FLAGS, GOALS, SECURITY_QUESTIONS } from "../api";
import { BodyStatsFields } from "../components/BodyStatsFields";
import { loadTodayLog } from "../lib/dailyLog";
import { resolveBodyStats } from "../lib/bodyMetrics";
import { useAuth } from "../context/AuthContext";

const ACTIVITY_LABEL: Record<string, string> = {
  sedentary: "Sedentary",
  light: "Light (1–3 d/wk)",
  moderate: "Moderate (3–5 d/wk)",
  active: "Active (6–7 d/wk)",
  very_active: "Very active",
};

const GOAL_LABEL: Record<string, string> = {
  lose: "Lose weight",
  maintain: "Maintain",
  gain: "Gain / build",
};

function humanizeFlag(id: string): string {
  return id
    .split("-")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

const CUSTOM_QUESTION = "Write your own question";

export function ProfilePage() {
  const navigate = useNavigate();
  const { user, logout, refreshUser } = useAuth();
  const [heightCm, setHeightCm] = useState<number | null>(null);
  const [weightKg, setWeightKg] = useState<number | null>(null);
  const [age, setAge] = useState<number | null>(null);
  const [sex, setSex] = useState<string>("");
  const [activity, setActivity] = useState<string>("");
  const [goal, setGoal] = useState<string>("");
  const [allergies, setAllergies] = useState<string[]>([]);
  const [prefs, setPrefs] = useState<string[]>([]);
  const [targets, setTargets] = useState<DailyTargets | null>(null);

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [mealsLogged, setMealsLogged] = useState(0);
  const [week, setWeek] = useState<DailyLogWeekDay[]>([]);
  const [questionPreset, setQuestionPreset] = useState<string>(SECURITY_QUESTIONS[0]);
  const [customQuestion, setCustomQuestion] = useState("");
  const [securityAnswer, setSecurityAnswer] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [securitySaved, setSecuritySaved] = useState(false);
  const [securitySaving, setSecuritySaving] = useState(false);
  const [securityError, setSecurityError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    void Promise.all([api.getProfile(), loadTodayLog(), api.fetchDailyLogWeek(7)])
      .then(([p, log, w]) => {
        if (cancelled) return;
        setHeightCm(p.height_cm);
        setWeightKg(p.weight_kg);
        setAge(p.age);
        setSex(p.sex ?? "");
        setActivity(p.activity_level ?? "");
        setGoal(p.goal ?? "");
        setAllergies(p.allergies ?? []);
        setPrefs(p.dietary_prefs ?? []);
        setTargets(p.targets);
        setMealsLogged(log.entries.length);
        setWeek(w);
      })
      .catch((e) => !cancelled && setError(e instanceof Error ? e.message : "Failed to load profile"))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, []);

  function toggle(list: string[], setter: (v: string[]) => void, value: string) {
    setter(list.includes(value) ? list.filter((x) => x !== value) : [...list, value]);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    setSaved(false);
    const stats = resolveBodyStats({ heightCm, weightKg, age });
    const payload: Profile = {
      height_cm: stats.heightCm,
      weight_kg: stats.weightKg,
      age: stats.age,
      sex: sex || null,
      activity_level: activity || null,
      goal: goal || null,
      allergies,
      dietary_prefs: prefs,
    };
    try {
      const res = await api.saveProfile(payload);
      setHeightCm(res.height_cm);
      setWeightKg(res.weight_kg);
      setAge(res.age);
      setSex(res.sex ?? "");
      setActivity(res.activity_level ?? "");
      setGoal(res.goal ?? "");
      setAllergies(res.allergies ?? []);
      setPrefs(res.dietary_prefs ?? []);
      setTargets(res.targets);
      setSaved(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function handleSecuritySubmit(e: React.FormEvent) {
    e.preventDefault();
    setSecurityError(null);
    setSecuritySaved(false);
    const securityQuestion =
      questionPreset === CUSTOM_QUESTION ? customQuestion.trim() : questionPreset;
    if (!securityQuestion || securityQuestion.length < 3) {
      setSecurityError("Choose or write a security question.");
      return;
    }
    if (securityQuestion.length > 300) {
      setSecurityError("Security question must be at most 300 characters.");
      return;
    }
    if (securityAnswer.trim().length < 2) {
      setSecurityError("Security answer must be at least 2 characters.");
      return;
    }
    if (securityAnswer.trim().length > 200) {
      setSecurityError("Security answer must be at most 200 characters.");
      return;
    }
    if (!currentPassword) {
      setSecurityError("Enter your current password.");
      return;
    }
    setSecuritySaving(true);
    try {
      await api.updateSecurityQuestion(securityQuestion, securityAnswer.trim(), currentPassword);
      setSecuritySaved(true);
      setCurrentPassword("");
      setSecurityAnswer("");
      await refreshUser();
    } catch (err) {
      setSecurityError(err instanceof Error ? err.message : "Could not save security question");
    } finally {
      setSecuritySaving(false);
    }
  }

  if (loading) return <p className="page-sub">Loading profile…</p>;

  const maxWeekCal = Math.max(...week.map((d) => d.calories ?? 0), targets?.target_calories ?? 2000, 1);

  return (
    <div className="page">
      <h1 className="page-title">Profile</h1>
      <p className="page-sub">Signed in as {user?.name?.trim() || user?.email}</p>

      <section className="card">
        <strong>Account</strong>
        <p className="page-sub" style={{ marginTop: "0.35rem", marginBottom: "0.85rem" }}>
          {user?.email}
        </p>
        <button
          type="button"
          className="btn btn--secondary btn--block"
          onClick={() => {
            logout();
            navigate("/login", { replace: true });
          }}
        >
          Sign out
        </button>
      </section>

      {user?.has_password && !user.has_security_question ? (
        <section className="card form-stack">
          <strong>Password recovery</strong>
          <p className="page-sub" style={{ marginTop: "0.35rem", marginBottom: "0.65rem" }}>
            Add a security question so you can reset your password without email.
          </p>
          {securityError ? <div className="alert alert--error" role="alert">{securityError}</div> : null}
          {securitySaved ? (
            <div className="alert alert--success" role="status">Security question saved.</div>
          ) : null}
          <form onSubmit={handleSecuritySubmit} className="form-stack">
            <label className="field">
              <span className="field__label">Security question</span>
              <select
                className="select"
                value={questionPreset}
                onChange={(e) => setQuestionPreset(e.target.value)}
              >
                {SECURITY_QUESTIONS.map((q) => (
                  <option key={q} value={q}>{q}</option>
                ))}
                <option value={CUSTOM_QUESTION}>{CUSTOM_QUESTION}</option>
              </select>
            </label>
            {questionPreset === CUSTOM_QUESTION ? (
              <label className="field">
                <span className="field__label">Your question</span>
                <input
                  className="input"
                  type="text"
                  value={customQuestion}
                  onChange={(e) => setCustomQuestion(e.target.value)}
                  required
                  minLength={3}
                  maxLength={300}
                />
              </label>
            ) : null}
            <label className="field">
              <span className="field__label">Security answer</span>
              <input
                className="input"
                type="text"
                value={securityAnswer}
                onChange={(e) => setSecurityAnswer(e.target.value)}
                required
                minLength={2}
                maxLength={200}
                autoComplete="off"
              />
            </label>
            <label className="field">
              <span className="field__label">Current password</span>
              <input
                className="input"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                required
                maxLength={128}
                autoComplete="current-password"
              />
            </label>
            <button type="submit" className="btn btn--secondary btn--block" disabled={securitySaving}>
              {securitySaving ? "Saving…" : "Save security question"}
            </button>
          </form>
        </section>
      ) : null}

      <section className="card">
        <p style={{ margin: 0, fontSize: "0.72rem", textTransform: "uppercase", letterSpacing: "0.1em", color: "var(--accent)" }}>
          Today
        </p>
        <p className="display-num" style={{ fontSize: "2.5rem", margin: "0.15rem 0", color: "var(--text)" }}>
          {mealsLogged}
        </p>
        <p style={{ margin: 0, color: "var(--text-muted)", fontSize: "0.88rem" }}>
          meal{mealsLogged === 1 ? "" : "s"} logged today
        </p>
      </section>

      {week.length > 0 ? (
        <section className="card">
          <strong>Last 7 days</strong>
          <div className="week-chart" aria-label="Calories logged per day">
            {week.map((d) => {
              const cal = d.calories ?? 0;
              const h = Math.max(8, Math.round((cal / maxWeekCal) * 100));
              const dayLabel = d.date.slice(5);
              return (
                <div key={d.date} className="week-chart__col" title={`${d.date}: ${cal} kcal`}>
                  <div className="week-chart__bar" style={{ height: `${h}%` }} />
                  <span className="week-chart__lbl">{dayLabel}</span>
                  <span className="week-chart__val">{cal > 0 ? cal : ""}</span>
                </div>
              );
            })}
          </div>
        </section>
      ) : null}

      {targets ? (
        <section className="card">
          <strong>Estimated daily targets</strong>
          {targets.bmi != null ? (
            <p className="page-sub" style={{ marginTop: "0.35rem", marginBottom: "0.65rem" }}>
              BMI {targets.bmi}
              {targets.bmi_category ? ` · ${targets.bmi_category.replace("_", " ")}` : ""}
            </p>
          ) : null}
          <div className="targets-grid">
            <div className="target-card">
              <div className="target-card__value">{targets.target_calories ?? "—"}</div>
              <div className="target-card__label">Calories</div>
            </div>
            <div className="target-card">
              <div className="target-card__value">{targets.protein_g != null ? `${targets.protein_g}g` : "—"}</div>
              <div className="target-card__label">Protein</div>
            </div>
            <div className="target-card">
              <div className="target-card__value">{targets.carbs_g != null ? `${targets.carbs_g}g` : "—"}</div>
              <div className="target-card__label">Carbs</div>
            </div>
            <div className="target-card">
              <div className="target-card__value">{targets.fat_g != null ? `${targets.fat_g}g` : "—"}</div>
              <div className="target-card__label">Fat</div>
            </div>
            <div className="target-card">
              <div className="target-card__value">{targets.tdee ?? "—"}</div>
              <div className="target-card__label">Daily burn (TDEE)</div>
            </div>
          </div>
          {targets.basis ? <p className="page-sub" style={{ marginTop: "0.65rem", marginBottom: 0 }}>{targets.basis}</p> : null}
        </section>
      ) : null}

      <form onSubmit={handleSubmit} className="card form-stack">
        {error ? <div className="alert alert--error" role="alert">{error}</div> : null}
        {saved ? <div className="alert alert--success" role="status">Profile saved.</div> : null}

        <BodyStatsFields
          heightCm={heightCm}
          weightKg={weightKg}
          age={age}
          onHeightCm={setHeightCm}
          onWeightKg={setWeightKg}
          onAge={setAge}
        />

        <label className="field">
          <span className="field__label">Sex</span>
          <select className="select" value={sex} onChange={(e) => setSex(e.target.value)}>
            <option value="">—</option>
            <option value="male">Male</option>
            <option value="female">Female</option>
            <option value="other">Other / prefer not to say</option>
          </select>
        </label>

        <div className="form-grid-2">
          <label className="field">
            <span className="field__label">Activity level</span>
            <select className="select" value={activity} onChange={(e) => setActivity(e.target.value)}>
              <option value="">—</option>
              {ACTIVITY_LEVELS.map((a) => (
                <option key={a} value={a}>{ACTIVITY_LABEL[a]}</option>
              ))}
            </select>
          </label>
          <label className="field">
            <span className="field__label">Goal</span>
            <select className="select" value={goal} onChange={(e) => setGoal(e.target.value)}>
              <option value="">—</option>
              {GOALS.map((g) => (
                <option key={g} value={g}>{GOAL_LABEL[g]}</option>
              ))}
            </select>
          </label>
        </div>

        <div className="form-section">
          <span className="field__label">Allergies</span>
          <div className="chip-row">
            {ALLERGENS.map((a) => (
              <button
                key={a}
                type="button"
                className={`chip ${allergies.includes(a) ? "chip--on" : ""}`}
                onClick={() => toggle(allergies, setAllergies, a)}
              >
                {humanizeFlag(a)}
              </button>
            ))}
          </div>
        </div>

        <div className="form-section">
          <span className="field__label">Dietary preferences</span>
          <div className="chip-row">
            {DIETARY_FLAGS.map((d) => (
              <button
                key={d}
                type="button"
                className={`chip ${prefs.includes(d) ? "chip--on" : ""}`}
                onClick={() => toggle(prefs, setPrefs, d)}
              >
                {humanizeFlag(d)}
              </button>
            ))}
          </div>
        </div>

        <button type="submit" disabled={saving} className="btn btn--primary btn--block">
          {saving ? "Saving…" : "Save profile"}
        </button>
      </form>
    </div>
  );
}

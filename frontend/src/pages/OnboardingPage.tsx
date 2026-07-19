import { useState } from "react";
import { useNavigate } from "react-router-dom";
import * as api from "../api";
import { ACTIVITY_LEVELS } from "../api";
import { BodyStatsFields } from "../components/BodyStatsFields";
import { MacroRing } from "../components/MacroRing";
import { useAuth } from "../context/AuthContext";
import { markOnboardingDone } from "../lib/storage";

const GOALS = [
  { id: "gain", icon: "💪", title: "Build muscle", sub: "Higher protein, strength-focused fuel" },
  { id: "lose", icon: "🔥", title: "Lose weight", sub: "Calorie-aware meals that keep you full" },
  { id: "maintain", icon: "🥗", title: "Eat healthier", sub: "Balanced, sustainable everyday eating" },
] as const;

export function OnboardingPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const [step, setStep] = useState(0);
  const [goal, setGoal] = useState<string>("maintain");
  const [heightCm, setHeightCm] = useState<number | null>(null);
  const [weightKg, setWeightKg] = useState<number | null>(null);
  const [age, setAge] = useState<number | null>(null);
  const [sex, setSex] = useState("male");
  const [activity, setActivity] = useState("moderate");
  const [targets, setTargets] = useState<api.DailyTargets | null>(null);
  const [saving, setSaving] = useState(false);

  async function skipStats() {
    setSaving(true);
    try {
      await api.saveProfile({
        height_cm: null,
        weight_kg: null,
        age: null,
        sex: null,
        activity_level: null,
        goal,
        allergies: [],
        dietary_prefs: [],
      });
    } catch {
      /* still let them in */
    }
    markOnboardingDone(user?.id);
    navigate("/home", { replace: true });
    setSaving(false);
  }

  async function finish() {
    setSaving(true);
    try {
      const p = await api.saveProfile({
        height_cm: heightCm,
        weight_kg: weightKg,
        age: age,
        sex,
        activity_level: activity,
        goal,
        allergies: [],
        dietary_prefs: [],
      });
      setTargets(p.targets);
      markOnboardingDone(user?.id);
      navigate("/home", { replace: true });
    } catch {
      markOnboardingDone(user?.id);
      navigate("/home", { replace: true });
    } finally {
      setSaving(false);
    }
  }

  async function loadPreviewTargets() {
    try {
      const p = await api.saveProfile({
        height_cm: heightCm,
        weight_kg: weightKg,
        age: age,
        sex,
        activity_level: activity,
        goal,
        allergies: [],
        dietary_prefs: [],
      });
      setTargets(p.targets);
    } catch {
      /* preview optional */
    }
  }

  return (
    <div className="onboarding">
      <img className="brand-logo brand-logo--onboarding" src="/macroreel-icon.svg" alt="MacroReel" />
      <p className="page-sub" style={{ margin: 0 }}>
        Step {step + 1} of 3
      </p>
      <h1 className="page-title" style={{ fontSize: "2rem" }}>
        {step === 0 ? "What's your goal?" : step === 1 ? "Quick stats" : "Your daily targets"}
      </h1>

      {step === 0 ? (
        <>
          <p className="page-sub">Pick one — we'll tailor macros to match.</p>
          <div className="goal-grid">
            {GOALS.map((g) => (
              <button
                key={g.id}
                type="button"
                className={`goal-card ${goal === g.id ? "goal-card--on" : ""}`}
                onClick={() => setGoal(g.id)}
              >
                <div className="goal-card__icon">{g.icon}</div>
                <p className="goal-card__title">{g.title}</p>
                <p className="goal-card__sub">{g.sub}</p>
              </button>
            ))}
          </div>
          <button type="button" className="btn btn--primary btn--block" onClick={() => setStep(1)}>
            Continue
          </button>
        </>
      ) : null}

      {step === 1 ? (
        <>
          <p className="page-sub">Optional — used for daily calorie & macro targets. You can add these anytime in Profile.</p>
          <div className="card form-stack" style={{ padding: "0.85rem" }}>
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
                <option value="male">Male</option>
                <option value="female">Female</option>
                <option value="other">Other / prefer not to say</option>
              </select>
            </label>
            <label className="field">
              <span className="field__label">Activity</span>
              <select className="select" value={activity} onChange={(e) => setActivity(e.target.value)}>
                {ACTIVITY_LEVELS.map((a) => (
                  <option key={a} value={a}>
                    {a === "sedentary"
                      ? "Sedentary"
                      : a === "light"
                        ? "Lightly active"
                        : a === "moderate"
                          ? "Moderately active"
                          : a === "active"
                            ? "Active"
                            : "Very active"}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="btn-row--split">
            <button type="button" className="btn btn--ghost" onClick={() => setStep(0)} disabled={saving}>
              Back
            </button>
            <button
              type="button"
              className="btn btn--primary"
              style={{ flex: 1 }}
              disabled={saving}
              onClick={() => {
                void loadPreviewTargets();
                setStep(2);
              }}
            >
              Continue
            </button>
          </div>
          <button
            type="button"
            className="btn btn--ghost btn--block"
            style={{ marginTop: "0.5rem" }}
            disabled={saving}
            onClick={() => void skipStats()}
          >
            {saving ? "Saving…" : "Skip for now"}
          </button>
        </>
      ) : null}

      {step === 2 ? (
        <>
          <p className="page-sub">Auto-calculated from your goal — edit anytime in Profile.</p>
          {targets ? (
            <div className="card" style={{ textAlign: "center" }}>
              <MacroRing
                consumed={{ calories: 0, protein_g: 0, carbs_g: 0, fat_g: 0, fiber_g: 0 }}
                targets={{
                  calories: targets.target_calories,
                  protein_g: targets.protein_g,
                  carbs_g: targets.carbs_g,
                  fat_g: targets.fat_g,
                  fiber_g: 0,
                }}
              />
              <p style={{ margin: "1rem 0 0", fontSize: "0.85rem", color: "var(--text-muted)" }}>
                {targets.target_calories} kcal · {targets.protein_g}g protein · {targets.carbs_g}g carbs · {targets.fat_g}g fat
              </p>
            </div>
          ) : (
            <div className="card">
              <p className="page-sub" style={{ margin: 0 }}>
                No targets yet — add your stats in Profile anytime, or skip and explore recipes now.
              </p>
            </div>
          )}
          <button
            type="button"
            className="btn btn--primary"
            style={{ width: "100%", marginTop: "1.25rem" }}
            disabled={saving}
            onClick={() => void finish()}
          >
            {saving ? "Saving…" : targets ? "Start exploring" : "Continue without targets"}
          </button>
          <button type="button" className="btn btn--ghost" style={{ width: "100%", marginTop: "0.5rem" }} onClick={() => setStep(1)}>
            Back
          </button>
        </>
      ) : null}
    </div>
  );
}

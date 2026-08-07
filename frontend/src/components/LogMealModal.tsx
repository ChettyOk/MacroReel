import { useState } from "react";
import type { Nutrition, Recipe } from "../api";
import * as api from "../api";
import { localDateKey } from "../lib/storage";
import { toUserErrorMessage } from "../lib/userError";
import { AnimatedNumber } from "./AnimatedNumber";

type Props = {
  recipe: Recipe;
  perServing: Nutrition;
  onClose: () => void;
  onLogged: () => void;
};

export function LogMealModal({ recipe, perServing, onClose, onLogged }: Props) {
  const [servings, setServings] = useState(1);
  const [saving, setSaving] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function confirm() {
    setSaving(true);
    setError(null);
    try {
      await api.addDailyLogEntry({
        recipe_id: recipe.id,
        title: recipe.title,
        servings,
        nutrition: perServing,
        log_date: localDateKey(),
      });
      setSuccess(true);
      await new Promise((r) => setTimeout(r, 650));
      onLogged();
      onClose();
    } catch (e) {
      setError(toUserErrorMessage(e, "Couldn’t log this meal. Please try again."));
    } finally {
      setSaving(false);
    }
  }

  const estKcal = (perServing.calories ?? 0) * servings;

  return (
    <div
      role="dialog"
      aria-modal
      className="modal-backdrop"
      onClick={() => {
        if (!saving) onClose();
      }}
    >
      <div className={`card reveal-up modal-sheet ${success ? "modal-sheet--success" : ""}`} onClick={(e) => e.stopPropagation()}>
        {success ? (
          <div className="log-success" aria-live="polite">
            <span className="log-success__check">✓</span>
            <p className="log-success__text">Logged to today</p>
          </div>
        ) : (
          <>
            <h3 style={{ margin: "0 0 0.5rem" }}>Log to today</h3>
            <p style={{ margin: "0 0 1rem", fontSize: "0.88rem", color: "var(--text-muted)" }}>
              How many servings did you eat?
            </p>
            <div className="portion-stepper">
              <button
                type="button"
                className="btn btn--secondary portion-stepper__btn"
                onClick={() => setServings((s) => Math.max(0.25, s - 0.25))}
              >
                −
              </button>
              <span className="display-num portion-stepper__val">
                <AnimatedNumber value={servings} duration={150} decimals={servings % 1 === 0 ? 0 : 2} />
              </span>
              <button
                type="button"
                className="btn btn--secondary portion-stepper__btn"
                onClick={() => setServings((s) => s + 0.25)}
              >
                +
              </button>
            </div>
            <p style={{ textAlign: "center", fontSize: "0.85rem", color: "var(--accent)", marginBottom: "1rem" }}>
              ≈ <AnimatedNumber value={estKcal} duration={150} suffix=" kcal" />
            </p>
            {error ? <p className="alert alert--error" style={{ marginBottom: "0.75rem" }}>{error}</p> : null}
            <div className="btn-row">
              <button type="button" className="btn btn--ghost" style={{ flex: 1 }} onClick={onClose} disabled={saving}>
                Cancel
              </button>
              <button type="button" className="btn btn--primary" style={{ flex: 1 }} onClick={() => void confirm()} disabled={saving}>
                {saving ? "Saving…" : "Log meal"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

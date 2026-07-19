import { useMemo, useState } from "react";
import {
  BODY_STAT_DEFAULTS,
  cmToFeetInches,
  feetInchesToCm,
  getPreferredUnits,
  kgToLb,
  lbToKg,
  range,
  setPreferredUnits,
  type UnitSystem,
} from "../lib/bodyMetrics";
import { ComboStatField } from "./ComboStatField";

type Props = {
  heightCm: number | null;
  weightKg: number | null;
  age: number | null;
  onHeightCm: (v: number | null) => void;
  onWeightKg: (v: number | null) => void;
  onAge: (v: number | null) => void;
};

export function BodyStatsFields({
  heightCm,
  weightKg,
  age,
  onHeightCm,
  onWeightKg,
  onAge,
}: Props) {
  const [units, setUnits] = useState<UnitSystem>(getPreferredUnits);

  // Display placeholders only — do not write defaults into the profile until the user picks a value.
  const cm = heightCm ?? BODY_STAT_DEFAULTS.heightCm;
  const kg = Math.round(weightKg ?? BODY_STAT_DEFAULTS.weightKg);
  const ageVal = age ?? BODY_STAT_DEFAULTS.age;

  const { ft, inches } = useMemo(() => cmToFeetInches(cm), [cm]);
  const lb = useMemo(() => kgToLb(kg), [kg]);

  const ageItems = useMemo(
    () => range(13, 100).map((n) => ({ value: n, label: String(n) })),
    [],
  );
  const cmItems = useMemo(
    () => range(120, 220).map((n) => ({ value: n, label: `${n}` })),
    [],
  );
  const kgItems = useMemo(
    () => range(30, 200).map((n) => ({ value: n, label: `${n}` })),
    [],
  );
  const ftItems = useMemo(
    () => range(4, 7).map((n) => ({ value: n, label: `${n}` })),
    [],
  );
  const inItems = useMemo(
    () => range(0, 11).map((n) => ({ value: n, label: `${n}` })),
    [],
  );
  const lbItems = useMemo(
    () => range(66, 440).map((n) => ({ value: n, label: `${n}` })),
    [],
  );

  function switchUnits(next: UnitSystem) {
    setUnits(next);
    setPreferredUnits(next);
  }

  return (
    <div className="body-stats">
      <div className="unit-toggle" role="group" aria-label="Unit system">
        <button
          type="button"
          className={`unit-toggle__btn ${units === "metric" ? "unit-toggle__btn--on" : ""}`}
          onClick={() => switchUnits("metric")}
        >
          cm / kg
        </button>
        <button
          type="button"
          className={`unit-toggle__btn ${units === "imperial" ? "unit-toggle__btn--on" : ""}`}
          onClick={() => switchUnits("imperial")}
        >
          ft / lb
        </button>
      </div>

      {units === "metric" ? (
        <div className="body-stats-grid body-stats-grid--metric">
          <ComboStatField
            label="Age"
            aria-label="Age in years"
            value={ageVal}
            onChange={(n) => onAge(n)}
            items={ageItems}
            unit="yrs"
          />
          <ComboStatField
            label="Height"
            aria-label="Height in centimeters"
            value={cm}
            onChange={(n) => onHeightCm(n)}
            items={cmItems}
            unit="cm"
          />
          <ComboStatField
            label="Weight"
            aria-label="Weight in kilograms"
            value={kg}
            onChange={(n) => onWeightKg(n)}
            items={kgItems}
            unit="kg"
          />
        </div>
      ) : (
        <div className="body-stats-grid body-stats-grid--imperial">
          <div className="form-grid-2">
            <ComboStatField
              label="Age"
              aria-label="Age in years"
              value={ageVal}
              onChange={(n) => onAge(n)}
              items={ageItems}
              unit="yrs"
            />
            <ComboStatField
              label="Weight"
              aria-label="Weight in pounds"
              value={lb}
              onChange={(n) => onWeightKg(lbToKg(n))}
              items={lbItems}
              unit="lb"
            />
          </div>
          <div className="field">
            <span className="field__label">Height</span>
            <div className="form-grid-2">
              <ComboStatField
                label="Feet"
                aria-label="Height feet"
                value={ft}
                onChange={(f) => onHeightCm(feetInchesToCm(f, inches))}
                items={ftItems}
                unit="ft"
              />
              <ComboStatField
                label="Inches"
                aria-label="Height inches"
                value={inches}
                onChange={(i) => onHeightCm(feetInchesToCm(ft, i))}
                items={inItems}
                unit="in"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

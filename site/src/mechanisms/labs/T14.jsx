import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { arrivingRatings, threeWindows, windowFeatures } from "../lib/moefit.js";

const TRAIN = "#4ade80";
const VALIDATE = "#facc15";
const TEST = "#f87171";
const whole = (value) => value.toFixed(0);

// Each window's features may read only the windows before it: validate reads train, and test
// reads train and validate. The guard refuses any history that reaches the window it describes.
function guard(history, rows, label) {
  try {
    const found = windowFeatures(history, rows);
    const known = found.filter((f) => f.userCount > 0 && f.movieCount > 0).length;
    return `Allowed: ${label} reads ${history.length} earlier ratings; ${known} of its ${rows.length} ratings have both histories.`;
  } catch (error) {
    return `Refused: ${error.message}.`;
  }
}

export default function T14() {
  const [validateFrom, setValidateFrom] = useState(600);
  const [testFrom, setTestFrom] = useState(800);
  const [leak, setLeak] = useState(false);

  const rows = useMemo(() => arrivingRatings({ seed: 191 }), []);
  const users = useMemo(() => Math.max(...rows.map((row) => row.user)) + 1, [rows]);
  const cut = useMemo(() => {
    try {
      return { windows: threeWindows(rows, { validateFrom, testFrom }) };
    } catch (error) {
      return { error: error.message };
    }
  }, [rows, validateFrom, testFrom]);

  const verdicts = useMemo(() => {
    if (cut.error) return null;
    const { train, validate, test } = cut.windows;
    const validateHistory = leak ? [...train, ...validate] : train;
    return {
      validate: guard(validateHistory, validate, "validate"),
      test: guard([...train, ...validate], test, "test"),
    };
  }, [cut, leak]);

  const space = useCallback(
    (colors) => {
      if (cut.error) return [];
      const { train, validate, test } = cut.windows;
      const points = (name, found, color) => ({
        type: "scatter3d",
        mode: "markers",
        name,
        x: found.map((row) => row.time),
        y: found.map((row) => row.user),
        z: found.map((row) => row.rating),
        marker: { size: 2.5, color, opacity: 0.8 },
      });
      const wall = (name, at) => ({
        type: "mesh3d",
        name,
        x: [at, at, at, at],
        y: [0, users, users, 0],
        z: [0.5, 0.5, 5.5, 5.5],
        i: [0, 0],
        j: [1, 2],
        k: [2, 3],
        color: colors.accent,
        opacity: 0.25,
        hoverinfo: "name",
      });
      return [
        points("Train", train, TRAIN),
        points("Validate", validate, VALIDATE),
        points("Test", test, TEST),
        wall("Validation starts", validateFrom),
        wall("Test starts", testFrom),
      ];
    },
    [cut, users, validateFrom, testFrom],
  );

  const spaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "Time" }, range: [0, 1000] },
        yaxis: { title: { text: "User" } },
        zaxis: { title: { text: "Rating" }, range: [0.5, 5.5] },
        camera: { eye: { x: 1.4, y: -1.8, z: 0.8 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  return (
    <article className="lab">
      <p>
        A feature may only use what was known when the prediction was asked for. Two walls cut
        time into three windows: train, validate and test. The validation window's features, which
        the gate is fitted on, may read only train; the test window's features may read train and
        validate, never test itself. Slide the walls and the windows change; put the second wall
        on or before the first and the split is refused; tick the leak box and the validation
        features are handed their own window, which the guard refuses rather than silently
        counting the future.
      </p>
      <Plot traces={space} layout={spaceLayout} label="Ratings by time, user and rating, cut into train, validate and test" />
      <div className="controls">
        <Slider label="Validation starts" value={validateFrom} min={100} max={950} step={10} onChange={setValidateFrom} format={whole} />
        <Slider label="Test starts" value={testFrom} min={150} max={990} step={10} onChange={setTestFrom} format={whole} />
        <label className="toggle">
          <input type="checkbox" checked={leak} onChange={(event) => setLeak(event.target.checked)} />{" "}
          Hand the validation features their own window too
        </label>
      </div>
      <dl className="readouts">
        {cut.error ? (
          <div>
            <dt>The split</dt>
            <dd>Refused: {cut.error}.</dd>
          </div>
        ) : (
          <>
            <div style={{ borderTop: `3px solid ${TRAIN}` }}>
              <dt>Train</dt>
              <dd>{cut.windows.train.length} ratings</dd>
            </div>
            <div style={{ borderTop: `3px solid ${VALIDATE}` }}>
              <dt>Validate</dt>
              <dd>{verdicts.validate}</dd>
            </div>
            <div style={{ borderTop: `3px solid ${TEST}` }}>
              <dt>Test</dt>
              <dd>{verdicts.test}</dd>
            </div>
          </>
        )}
      </dl>
      <Provenance
        data="Synthetic ratings from users and movies that arrive over time, generated in this page: arrivingRatings({ seed: 191 }); no real ratings"
        split="Train before the first wall, validate up to the second, test from it; the second wall must come after the first"
        features="The user's and the movie's rating counts from the windows before each one, read by windowFeatures in lib/moefit.js"
        method="Strictly-before boundary at the start of each window, the same rule as scripts/moe.py's gate_features, which raises on any later rating"
      />
    </article>
  );
}

import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { bucket, clmFit, ordinalRatings, score } from "../lib/ordinal.js";

const STARS = ["#ef4444", "#f59e0b", "#facc15", "#4ade80", "#93c5fd"];
const POINT = "#3b82f6";
const GRID = [-4, -2, 0, 2, 4];

export default function M14() {
  const [bucketed, setBucketed] = useState(false);
  const [shift, setShift] = useState(0);

  const rows = useMemo(() => ordinalRatings({ seed: 141 }), []);
  const fit = useMemo(() => clmFit(rows), [rows]);
  const scores = useMemo(() => rows.map((row) => score(fit, row)), [rows, fit]);
  const base = useMemo(() => scores.map((value) => bucket(value, fit.cuts)), [scores, fit]);
  const shifted = scores.map((value) => bucket(value, fit.cuts, shift));
  const flips = shifted.filter((level, index) => level !== base[index]).length;
  const counts = [1, 2, 3, 4, 5].map((level) => shifted.filter((value) => value === level).length);
  const matched = base.filter((level, index) => level === rows[index].rating).length;
  const gaps = fit.cuts.slice(1).map((cut, index) => cut - fit.cuts[index]);

  const space = useCallback(
    (colors) => {
      const plane = GRID.flatMap((x) => GRID.map((y) => ({ x, y })));
      const traces = [
        {
          type: "scatter3d",
          mode: "markers",
          name: "Fitted latent plane",
          x: plane.map((point) => point.x),
          y: plane.map((point) => point.y),
          z: plane.map((point) => fit.b1 * point.x + fit.b2 * point.y),
          marker: { size: 2, color: colors.muted, opacity: 0.6 },
          hoverinfo: "skip",
        },
        {
          type: "scatter3d",
          mode: "markers",
          name: bucketed ? "Ratings, coloured by star" : "Hidden scores",
          x: rows.map((row) => row.user),
          y: rows.map((row) => row.movie),
          z: scores,
          marker: {
            size: 5,
            color: bucketed ? shifted.map((level) => STARS[level - 1]) : POINT,
            line: { color: colors.ink, width: 0.5 },
          },
        },
      ];
      if (bucketed) {
        fit.cuts.forEach((cut, index) => {
          traces.push({
            type: "surface",
            name: `Cut ${index + 1}|${index + 2}`,
            x: [-4, 4],
            y: [-4, 4],
            z: [
              [cut + shift, cut + shift],
              [cut + shift, cut + shift],
            ],
            showscale: false,
            opacity: 0.18,
            colorscale: [
              [0, STARS[index + 1]],
              [1, STARS[index + 1]],
            ],
            hoverinfo: "skip",
          });
        });
      }
      return traces;
    },
    [rows, fit, scores, shifted, bucketed, shift],
  );

  const spaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User clue (x)" }, range: [-4, 4] },
        yaxis: { title: { text: "Movie clue (y)" }, range: [-4, 4] },
        zaxis: { title: { text: "Hidden score (z)" }, range: [-5, 5] },
        camera: { eye: { x: 1.5, y: -1.5, z: 0.8 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  return (
    <article className="lab">
      <p>
        The model scores each rating on a hidden continuous scale, then four cut-points slice that
        scale into one to five stars. The cut-points are learned, not assumed equally spaced, which
        is exactly what the continuous models take for granted. Shift them together and count how
        many predictions change star: if a small shift causes many flips, the ordinal assumptions
        are too fragile to rely on.
      </p>
      <Plot traces={space} layout={spaceLayout} label="Hidden scores sliced into star ratings" />
      <div className="controls">
        <label className="toggle">
          <input
            type="checkbox"
            checked={bucketed}
            onChange={(event) => setBucketed(event.target.checked)}
          />{" "}
          Apply ordinal bucketing: the five stars and their cut-off planes
        </label>
        <Slider
          label="Sensitivity audit, shift every cut-off"
          value={shift}
          min={-1}
          max={1}
          step={0.05}
          onChange={setShift}
        />
      </div>
      <dl className="readouts">
        {counts.map((count, index) => (
          <div key={index} style={{ borderTop: `3px solid ${STARS[index]}` }}>
            <dt>
              ★{index + 1} bucket
            </dt>
            <dd>{bucketed ? count : "—"}</dd>
          </div>
        ))}
        <div>
          <dt>Rating flips</dt>
          <dd>
            {flips} / {rows.length} change star at a shift of {shift.toFixed(2)}
          </dd>
        </div>
        <div>
          <dt>Fitted cut-points</dt>
          <dd>
            {fit.cuts.map((cut) => cut.toFixed(2)).join(", ")}; gaps{" "}
            {gaps.map((gap) => gap.toFixed(2)).join(", ")}, where a continuous model assumes one
            equal step
          </dd>
        </div>
        <div>
          <dt>Against the observed ratings</dt>
          <dd>
            {matched} of {rows.length} fall in the bucket their fitted score predicts; coefficients{" "}
            {fit.b1.toFixed(2)} for the user clue and {fit.b2.toFixed(2)} for the movie clue
          </dd>
        </div>
      </dl>
      <Provenance
        data="Synthetic ratings, generated in this page: ordinalRatings({ seed: 141 }); no real ratings"
        method="Proportional-odds cumulative link model, free ordered cut-points, maximum likelihood by gradient ascent"
      />
    </article>
  );
}

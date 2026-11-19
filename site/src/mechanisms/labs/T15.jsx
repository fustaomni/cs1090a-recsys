import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import { bucketReport, pooledRmse } from "../lib/moe.js";
import { EXPERT_NAMES, runMixture } from "../lib/moepipeline.js";

const MINIMUM = 30;
const BUCKETS = [
  { name: "warm", place: [1, 1], color: "#4ade80" },
  { name: "new user", place: [0, 1], color: "#3b82f6" },
  { name: "new movie", place: [1, 0], color: "#facc15" },
  { name: "both new", place: [0, 0], color: "#f472b6" },
];
// Each bucket shows two blocks side by side: the fitted mixture, and the single expert that
// did best on validation, chosen there rather than on test.
const MODELS = [
  { key: "mixture", shift: -0.2, opacity: 0.9 },
  { key: "expert", shift: 0.2, opacity: 0.45 },
];
const three = (value) => value.toFixed(3);

function box([cx, cy], height, color, opacity, name) {
  const [x0, x1, y0, y1] = [cx - 0.15, cx + 0.15, cy - 0.3, cy + 0.3];
  return {
    type: "mesh3d",
    name,
    color,
    opacity,
    flatshading: true,
    x: [x0, x1, x1, x0, x0, x1, x1, x0],
    y: [y0, y0, y1, y1, y0, y0, y1, y1],
    z: [0, 0, 0, 0, height, height, height, height],
    i: [0, 0, 4, 4, 0, 0, 1, 1, 2, 2, 3, 3],
    j: [1, 2, 5, 6, 1, 5, 2, 6, 3, 7, 0, 4],
    k: [2, 3, 6, 7, 5, 4, 6, 5, 7, 6, 4, 7],
    hoverinfo: "name",
  };
}

const describe = (found) =>
  `${three(found.rmse)} (${three(found.low)} to ${three(found.high)}), n ${found.n}${found.small ? ", too few to trust" : ""}`;

export default function T15() {
  const [split, setSplit] = useState(true);

  const run = useMemo(() => runMixture({ seed: 191 }), []);
  const best = run.validation.experts.indexOf(Math.min(...run.validation.experts));
  const scored = useMemo(
    () => ({
      mixture: run.rows.map((row) => ({ ...row, prediction: row.mixture })),
      expert: run.rows.map((row) => ({ ...row, prediction: row.experts[best] })),
    }),
    [run, best],
  );
  const pooled = useMemo(
    () => ({ mixture: pooledRmse(scored.mixture), expert: pooledRmse(scored.expert) }),
    [scored],
  );
  const reports = useMemo(
    () => ({
      mixture: bucketReport(scored.mixture, { minimum: MINIMUM, draws: 200, seed: 15 }),
      expert: bucketReport(scored.expert, { minimum: MINIMUM, draws: 200, seed: 15 }),
    }),
    [scored],
  );
  const label = (key) => (key === "mixture" ? "fitted mixture" : EXPERT_NAMES[best]);

  const space = useCallback(
    (colors) => {
      if (!split) {
        return MODELS.map(({ key, shift, opacity }) =>
          box([0.5 + shift, 0.5], pooled[key], colors.accent, opacity, `${label(key)}: pooled RMSE ${three(pooled[key])}`),
        );
      }
      return BUCKETS.flatMap((bucket) =>
        MODELS.flatMap(({ key, shift, opacity }) => {
          const found = reports[key][bucket.name];
          if (!found) return [];
          const [cx, cy] = bucket.place;
          const x = cx + shift;
          return [
            box([x, cy], found.rmse, bucket.color, opacity, `${bucket.name}, ${label(key)}: RMSE ${describe(found)}`),
            {
              type: "scatter3d",
              mode: "lines",
              name: `${bucket.name}, ${label(key)} interval`,
              x: [x, x],
              y: [cy, cy],
              z: [found.low, found.high],
              line: { color: colors.ink, width: 6 },
              hoverinfo: "skip",
              showlegend: false,
            },
          ];
        }),
      );
    },
    [split, pooled, reports, best],
  );

  const spaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User history" }, tickvals: [0, 1], ticktext: ["new", "known"], range: [-0.6, 1.6] },
        yaxis: { title: { text: "Movie history" }, tickvals: [0, 1], ticktext: ["new", "known"], range: [-0.6, 1.6] },
        zaxis: { title: { text: "RMSE" }, rangemode: "tozero" },
        camera: { eye: { x: 1.6, y: -1.6, z: 1.0 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  return (
    <article className="lab">
      <p>
        One RMSE over every test rating can hide where a model fails. Here Model 15's fitted
        mixture and the single expert that did best on validation each predict the test window,
        and each rating falls in one bucket by what the earlier windows knew about its user and its
        movie. The pooled value is computed from every error, not averaged over buckets; split it
        and each bucket shows two blocks, the mixture solid and the expert faint, each with its
        own RMSE, count and a bootstrap interval that resamples users. A block under {MINIMUM}{" "}
        ratings is flagged.
      </p>
      <Plot traces={space} layout={spaceLayout} label="RMSE pooled, or per training-history bucket, for the mixture and the best single expert" />
      <div className="controls">
        <label className="toggle">
          <input type="checkbox" checked={split} onChange={(event) => setSplit(event.target.checked)} />{" "}
          Split the score by bucket
        </label>
      </div>
      <dl className="readouts">
        <div>
          <dt>Pooled RMSE</dt>
          <dd>
            fitted mixture {three(pooled.mixture)}, {EXPERT_NAMES[best]} {three(pooled.expert)},
            over {run.rows.length} test ratings
          </dd>
        </div>
        {BUCKETS.map((bucket) => {
          const mixture = reports.mixture[bucket.name];
          const expert = reports.expert[bucket.name];
          return (
            <div key={bucket.name} style={{ borderTop: `3px solid ${bucket.color}` }}>
              <dt>{bucket.name}</dt>
              <dd>
                {mixture
                  ? `mixture ${describe(mixture)}; ${EXPERT_NAMES[best]} ${three(expert.rmse)}`
                  : "no test ratings"}
              </dd>
            </div>
          );
        })}
      </dl>
      <Provenance
        data="Synthetic ratings from users and movies that arrive over time, generated in this page: arrivingRatings({ seed: 191 }); no real ratings"
        split="Model 15's windows: train before 600, validate 600 to 800, test from 800, scored once"
        features="Each test rating's bucket from its user's and its movie's rating counts in train and validate"
        method={`Model 15's fitted mixture beside ${EXPERT_NAMES[best]}, the expert with the lowest validation RMSE; per-bucket RMSE with a 95% percentile bootstrap that resamples users, 200 draws`}
      />
    </article>
  );
}

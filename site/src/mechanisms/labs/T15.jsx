import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import { clip } from "../lib/metrics.js";
import { bucketOf, bucketReport, gateFeatures, pooledRmse, usable } from "../lib/moe.js";
import { timedRatings } from "../lib/ratings.js";

const BOUNDARY = 700;
const SHRINK = 10;
const MINIMUM = 30;
const BUCKETS = [
  { name: "warm", place: [1, 1], color: "#4ade80" },
  { name: "new user", place: [0, 1], color: "#3b82f6" },
  { name: "new movie", place: [1, 0], color: "#facc15" },
  { name: "both new", place: [0, 0], color: "#f472b6" },
];
const three = (value) => value.toFixed(3);

function scoreTest(train, test) {
  const mu = train.reduce((sum, row) => sum + row.rating, 0) / train.length;
  const totals = (key, residual) => {
    const found = new Map();
    train.forEach((row) => {
      const [total, n] = found.get(row[key]) ?? [0, 0];
      found.set(row[key], [total + residual(row), n + 1]);
    });
    return found;
  };
  const shrunk = (found, id) => {
    const [total, n] = found.get(id) ?? [0, 0];
    return total / (n + SHRINK);
  };
  const users = totals("user", (row) => row.rating - mu);
  const movies = totals("movie", (row) => row.rating - mu - shrunk(users, row.user));
  return test.map((row) => ({
    ...row,
    prediction: clip(mu + shrunk(users, row.user) + shrunk(movies, row.movie)),
    bucket: bucketOf(gateFeatures(train, row, BOUNDARY)),
  }));
}

function box([cx, cy], height, color, name) {
  const [x0, x1, y0, y1] = [cx - 0.35, cx + 0.35, cy - 0.35, cy + 0.35];
  return {
    type: "mesh3d",
    name,
    color,
    opacity: 0.85,
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

export default function T15() {
  const [split, setSplit] = useState(true);

  const rows = useMemo(() => timedRatings({ seed: 191 }), []);
  const scored = useMemo(() => {
    const { before, blocked } = usable(rows, BOUNDARY);
    return scoreTest(before, blocked);
  }, [rows]);
  const pooled = useMemo(() => pooledRmse(scored), [scored]);
  const report = useMemo(() => bucketReport(scored, { minimum: MINIMUM, draws: 200, seed: 15 }), [scored]);
  const present = BUCKETS.filter((bucket) => report[bucket.name]);
  const trusted = present.filter((bucket) => !report[bucket.name].small);
  const ranked = (trusted.length ? trusted : present)
    .slice()
    .sort((p, q) => report[p.name].rmse - report[q.name].rmse);

  const space = useCallback(
    (colors) => {
      if (!split) {
        return [
          {
            type: "surface",
            name: "Pooled RMSE",
            x: [-0.5, 1.5],
            y: [-0.5, 1.5],
            z: [
              [pooled, pooled],
              [pooled, pooled],
            ],
            showscale: false,
            opacity: 0.8,
            colorscale: [
              [0, colors.accent],
              [1, colors.accent],
            ],
            hovertemplate: `Pooled RMSE ${three(pooled)}<extra></extra>`,
          },
        ];
      }
      return present.flatMap((bucket) => {
        const found = report[bucket.name];
        const [cx, cy] = bucket.place;
        const label = `${bucket.name}: RMSE ${three(found.rmse)}, n ${found.n}${found.small ? ", too few to trust" : ""}`;
        return [
          box(bucket.place, found.rmse, bucket.color, label),
          {
            type: "scatter3d",
            mode: "lines",
            name: `${bucket.name} interval`,
            x: [cx, cx],
            y: [cy, cy],
            z: [found.low, found.high],
            line: { color: colors.ink, width: 6 },
            hoverinfo: "skip",
          },
        ];
      });
    },
    [split, pooled, present, report],
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
        One RMSE over every test rating can hide where a model fails. Here a shrunk bias model
        predicts each rating after the cut, and each rating falls in one bucket by what training
        knew about its user and its movie. The pooled value is computed from every error, not
        averaged over buckets; split it and each block shows its own RMSE, its count, and a
        bootstrap interval that resamples users. A block under {MINIMUM} ratings is flagged.
      </p>
      <Plot traces={space} layout={spaceLayout} label="RMSE pooled, or per training-history bucket" />
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
            {three(pooled)} over {scored.length} test ratings
          </dd>
        </div>
        {BUCKETS.map((bucket) => {
          const found = report[bucket.name];
          return (
            <div key={bucket.name} style={{ borderTop: `3px solid ${bucket.color}` }}>
              <dt>{bucket.name}</dt>
              <dd>
                {found
                  ? `${three(found.rmse)} (${three(found.low)} to ${three(found.high)}), n ${found.n}${found.small ? ", too few to trust" : ""}`
                  : "no test ratings"}
              </dd>
            </div>
          );
        })}
        {ranked.length > 0 && (
          <div>
            <dt>Best and worst</dt>
            <dd>
              {ranked[0].name} is best and {ranked[ranked.length - 1].name} is worst
              {trusted.length ? ", among buckets large enough to trust" : ", though every bucket is small"}
            </dd>
          </div>
        )}
      </dl>
      <Provenance
        data="Synthetic ratings, generated in this page: timedRatings({ seed: 191 }); no real ratings"
        split={`Ratings before time ${BOUNDARY} train; ratings at or after it are the test window`}
        features="Each test rating's bucket from its user's and its movie's training rating counts"
        method="Bias model with user and movie effects shrunk by 10; per-bucket RMSE with a 95% percentile bootstrap that resamples users, 200 draws"
      />
    </article>
  );
}

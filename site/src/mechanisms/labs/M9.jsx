import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Slider from "../Slider.jsx";
import {
  blockSurface,
  ensemblePredict,
  forest,
  outOfBag,
  splitFrequency,
  varianceAcrossDatasets,
} from "../lib/ensemble.js";
import { fixed } from "../lib/format.js";
import { rmse } from "../lib/metrics.js";
import { mulberry32 } from "../lib/random.js";
import { forestRatings } from "../lib/ratings.js";
import { impurityImportance, permutationImportance } from "../lib/tree.js";

const FEATURES = ["user", "film", "genre", "noise"];
const LABELS = { user: "user history", film: "film history", genre: "genre", noise: "noise" };
const TRAIN = 200;
const TREES = 40;
const RANGE = [-2.5, 2.5];
const FIXED = { genre: 0, noise: 0 };

function shares(values) {
  const positive = values.map((v) => Math.max(v, 0));
  const total = positive.reduce((s, v) => s + v, 0) || 1;
  return positive.map((v) => v / total);
}

function Bars({ title, values }) {
  return (
    <div>
      <h4>{title}</h4>
      <div className="bars">
        {values.map((value, j) => (
          <div className="bar-row" key={FEATURES[j]}>
            <span>{LABELS[FEATURES[j]]}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${value * 100}%` }} />
            </div>
            <strong>{fixed(value * 100, 0)}%</strong>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function M9() {
  const [mtry, setMtry] = useState(2);
  const [fraction, setFraction] = useState(1);
  const [minLeaf, setMinLeaf] = useState(3);

  const rows = useMemo(() => forestRatings({ seed: 101, n: 240 }), []);
  const train = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const later = useMemo(() => rows.slice(TRAIN), [rows]);
  const queries = useMemo(() => forestRatings({ seed: 9, n: 20 }), []);
  const settings = { trees: TREES, minLeaf, sampleFraction: fraction, seed: 11 };

  const built = useMemo(() => {
    const started = performance.now();
    const members = forest(train, FEATURES, { ...settings, mtry });
    return { members, ms: performance.now() - started };
  }, [train, mtry, fraction, minLeaf]);
  const bagged = useMemo(
    () => forest(train, FEATURES, { ...settings, mtry: FEATURES.length }),
    [train, fraction, minLeaf],
  );
  const { members } = built;
  const predict = useCallback((row) => ensemblePredict(members, row), [members]);

  const sweep = useMemo(
    () =>
      [1, 2, 3, 4].map((m) => {
        const trial = forest(train, FEATURES, { ...settings, trees: 25, mtry: m });
        const spread = varianceAcrossDatasets(
          (seed) => forestRatings({ seed, n: TRAIN }),
          FEATURES,
          queries,
          { datasets: 8, trees: 20, mtry: m, minLeaf, sampleFraction: fraction },
        );
        return {
          mtry: m,
          ...spread,
          later: rmse(
            later.map((row) => ensemblePredict(trial, row)),
            later.map((row) => row.rating),
          ),
        };
      }),
    [train, later, queries, fraction, minLeaf],
  );
  const surface = useMemo(
    () => blockSurface(predict, "user", "film", RANGE, RANGE, 48, FIXED),
    [predict],
  );
  const frequency = splitFrequency(members, FEATURES, 3);
  const baggedFrequency = splitFrequency(bagged, FEATURES, 3);
  const impurity = useMemo(() => {
    const totals = FEATURES.map(() => 0);
    for (const member of members) {
      impurityImportance(member.tree, FEATURES).forEach((v, j) => {
        totals[j] += v / members.length;
      });
    }
    return totals;
  }, [members]);
  const permutation = useMemo(
    () => shares(permutationImportance(predict, later, FEATURES, mulberry32(3), 10)),
    [predict, later],
  );
  const oob = outOfBag(members, train);
  const oobKept = oob.map((v, i) => [v, train[i].rating]).filter(([v]) => !Number.isNaN(v));
  const leaves =
    members.reduce((s, member) => s + member.model.leaves.length, 0) / members.length;

  const surfaceTraces = useCallback(
    (colors) => [
      {
        type: "surface",
        ...surface,
        colorscale: "Viridis",
        cmin: 1,
        cmax: 5,
        opacity: 0.92,
        showscale: false,
        name: "Forest prediction",
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Training ratings",
        x: train.map((row) => row.user),
        y: train.map((row) => row.film),
        z: train.map((row) => row.rating),
        marker: { size: 2.5, color: colors.muted, opacity: 0.5 },
      },
    ],
    [surface, train],
  );
  const sweepTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Variance floor ρσ²",
        x: sweep.map((s) => s.mtry),
        y: sweep.map((s) => s.floor),
        line: { color: colors.accent },
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Later-window RMSE",
        x: sweep.map((s) => s.mtry),
        y: sweep.map((s) => s.later),
        yaxis: "y2",
        line: { color: colors.ink },
      },
    ],
    [sweep],
  );
  const surfaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User history" } },
        yaxis: { title: { text: "Film history" } },
        zaxis: { title: { text: "Predicted rating" }, range: [1, 5] },
        camera: { eye: { x: 1.6, y: -1.6, z: 1.0 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );
  const sweepLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Features tried at each split, max_features" }, dtick: 1 },
      yaxis: { title: { text: "ρσ²" }, rangemode: "tozero" },
      yaxis2: { overlaying: "y", side: "right", title: { text: "RMSE" }, tickformat: ".3f" },
    }),
    [],
  );

  return (
    <article className="lab">
      <h3>Model 9 · Random forest</h3>
      <p>
        A random forest is bagging plus one more source of randomness: every split may only
        choose among a random subset of max_features features. Roots stop being the same split in
        every tree, the trees decorrelate, and the variance floor ρσ² drops, at the price of
        slightly worse individual trees. Trying all four features at every split is plain bagging,
        which is also what scikit-learn's default of 1.0 does, so the setting is declared, never
        left to the default.
      </p>
      <Plot traces={surfaceTraces} layout={surfaceLayout} label="Forest surface" height={440} />
      <div className="controls">
        <Slider
          label="max_features"
          value={mtry}
          min={1}
          max={4}
          step={1}
          onChange={setMtry}
          format={(value) => (value === 4 ? "4 (all: bagging)" : String(value))}
        />
        <Slider
          label="max_samples, share of rows per tree"
          value={fraction}
          min={0.3}
          max={1}
          step={0.05}
          onChange={setFraction}
        />
        <Slider
          label="min_samples_leaf"
          value={minLeaf}
          min={1}
          max={20}
          step={1}
          onChange={setMinLeaf}
          format={String}
        />
      </div>
      <dl className="readouts">
        <div>
          <dt>This forest, {TREES} trees</dt>
          <dd>
            Across datasets, correlation between trees ρ = {fixed(sweep[mtry - 1].rho, 2)} and
            floor ρσ² = {fixed(sweep[mtry - 1].floor, 3)}; on average {fixed(leaves, 1)} leaves
            per tree; grown in {fixed(built.ms, 0)} ms
          </dd>
        </div>
        <div>
          <dt>RMSE</dt>
          <dd>
            Training {fixed(rmse(train.map(predict), train.map((row) => row.rating)))}, out of
            bag{" "}
            {fixed(
              rmse(
                oobKept.map(([v]) => v),
                oobKept.map(([, y]) => y),
              ),
            )}
            , later window {fixed(rmse(later.map(predict), later.map((row) => row.rating)))}
          </dd>
        </div>
      </dl>
      <Plot traces={sweepTraces} layout={sweepLayout} label="Correlation and error" height={300} />
      <div className="lab-grid">
        {[0, 1, 2].map((depth) => (
          <div key={depth}>
            <Bars
              title={`Split features at depth ${depth}, bagging`}
              values={baggedFrequency[depth]}
            />
            <Bars title={`Depth ${depth}, this forest`} values={frequency[depth]} />
          </div>
        ))}
      </div>
      <div className="lab-grid">
        <Bars title="Impurity importance (training)" values={impurity} />
        <Bars title="Permutation importance (later window), as shares" values={permutation} />
      </div>
      <p className="muted">
        Each floor is estimated from eight simulated datasets, so that curve is itself noisy;
        the trend from one feature per split to all four is the point. Impurity importance
        favours continuous features and is computed on training data, so the
        pure-noise column earns a share; permutation importance on later rows gives it almost
        none. User and film history are correlated, so shuffling one leaves the other to cover
        for it: the variable-importance lab goes further. Seeded synthetic data: {train.length}{" "}
        training and {later.length} later ratings on five levels.
      </p>
    </article>
  );
}

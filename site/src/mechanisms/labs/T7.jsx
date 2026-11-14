import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { estimates, oobRmse } from "../lib/oob.js";
import { driftRatings } from "../lib/ratings.js";

const TRAIN = 240;
const TREES = 30;
const ESTIMATES = ["Out of bag", "Random 3-fold CV", "Within-period random", "Temporal"];

function summary(values) {
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const sd = Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / (values.length - 1));
  return { mean, sd };
}

export default function T7() {
  const [seeds, setSeeds] = useState(6);

  const rows = useMemo(() => driftRatings({ seed: 111, n: 300 }), []);
  const train = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const later = useMemo(() => rows.slice(TRAIN), [rows]);
  const runs = useMemo(
    () => Array.from({ length: seeds }, (_, s) => estimates(train, later, s + 1)),
    [train, later, seeds],
  );
  const columns = ESTIMATES.map((_, k) => summary(runs.map((run) => run.values[k])));
  const gap = summary(runs.map((run) => run.temporalHeld - run.values[0]));
  const change = summary(runs.map((run) => run.temporalHeld - run.values[2]));
  const period = summary(runs.map((run) => run.values[2] - run.values[0]));
  const agreement = summary(runs.map((run) => Math.abs(run.values[0] - run.values[1])));
  const growth = useMemo(
    () => Array.from({ length: TREES }, (_, b) => oobRmse(runs[0].members, train, b + 1)),
    [runs, train],
  );

  const pairedTraces = useCallback(
    (colors) => [
      ...runs.map((run, s) => ({
        type: "scatter",
        mode: "lines+markers",
        name: s === 0 ? "One seed" : undefined,
        showlegend: s === 0,
        x: ESTIMATES,
        y: run.values,
        line: { color: colors.line, width: 1 },
        marker: { size: 6, color: colors.muted },
      })),
      {
        type: "scatter",
        mode: "markers",
        name: "Mean ± 1 SD over seeds",
        x: ESTIMATES,
        y: columns.map((c) => c.mean),
        error_y: { type: "data", array: columns.map((c) => c.sd), color: colors.accent },
        marker: { size: 12, color: colors.accent },
      },
    ],
    [runs, columns],
  );
  const gapTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "markers",
        name: "Mean ± 1 SD over seeds",
        x: ["Total gap", "Time change", "Later period"],
        y: [gap.mean, change.mean, period.mean],
        error_y: { type: "data", array: [gap.sd, change.sd, period.sd], color: colors.accent },
        marker: { size: 12, color: colors.accent },
      },
    ],
    [gap, change, period],
  );
  const growthTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Out-of-bag RMSE, seed 1",
        x: growth.map((_, b) => b + 1),
        y: growth,
        line: { color: colors.accent },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "Temporal RMSE, seed 1",
        x: [1, TREES],
        y: [runs[0].values[3], runs[0].values[3]],
        line: { color: colors.ink, dash: "dot" },
      },
    ],
    [growth, runs],
  );
  const pairedLayout = useMemo(() => ({ yaxis: { title: { text: "RMSE" } } }), []);
  const gapLayout = useMemo(
    () => ({
      xaxis: { title: { text: "temporal − OOB = (temporal − within) + (within − OOB)" } },
      yaxis: { title: { text: "Difference in RMSE" }, zeroline: true },
      shapes: [
        {
          type: "line",
          xref: "paper",
          x0: 0,
          x1: 1,
          y0: 0,
          y1: 0,
          line: { width: 1, color: "rgba(127,127,127,0.7)" },
        },
      ],
    }),
    [],
  );
  const growthLayout = useMemo(
    () => ({ xaxis: { title: { text: "Trees, B" } }, yaxis: { title: { text: "RMSE" } } }),
    [],
  );

  return (
    <article className="lab">
      <p>
        Out-of-bag error grades each training row with the trees that never saw it, about a
        third of them. That makes it nearly the same estimate as random cross-validation, so the
        two agreeing proves nothing: both ignore time. The honest comparison is with the temporal
        score, and the gap between them mixes two things. A random split inside the later period
        separates them: how much the period itself differs, and how much a model trained only on
        the past loses.
      </p>
      <div className="lab-grid">
        <Plot traces={pairedTraces} layout={pairedLayout} label="Four estimates per seed" />
        <Plot traces={gapTraces} layout={gapLayout} label="The gap, decomposed" />
      </div>
      <div className="controls">
        <Slider
          label="Seeds (forest and split randomness)"
          value={seeds}
          min={2}
          max={10}
          step={1}
          onChange={setSeeds}
          format={String}
        />
      </div>
      <dl className="readouts">
        <div>
          <dt>Total gap, temporal − out of bag</dt>
          <dd>
            {fixed(gap.mean)} ± {fixed(gap.sd)} across {seeds} seeds: the spread of model
            randomness only, not the uncertainty of the data, which needs the user-clustered
            bootstrap
          </dd>
        </div>
        <div>
          <dt>Decomposed</dt>
          <dd>
            On the half of the later window held out by the within-period split: time change{" "}
            {fixed(change.mean)} (training only on the past costs this much there) plus later
            period {fixed(period.mean)} (that period is this much easier
            or harder to predict at all)
          </dd>
        </div>
        <div>
          <dt>Out of bag against random cross-validation</dt>
          <dd>
            They differ by {fixed(agreement.mean)} on average: close agreement, as expected of two
            random-split estimates, and no evidence about the future
          </dd>
        </div>
      </dl>
      <Plot traces={growthTraces} layout={growthLayout} label="OOB error against B" height={300} />
      <p className="muted">
        With few trees each row's out-of-bag prediction rests on very few of them, so the
        estimate starts high and only settles as B grows. In these synthetic ratings later
        ratings run higher and lean less on user history: the later period is easier to predict,
        which can hide the cost of training on the past inside a small or even negative total
        gap. That is why the gap is decomposed rather than read as proof of leakage. Seeded
        synthetic data: {train.length} training and {later.length} later ratings on five levels.
      </p>
      <Provenance
        data="Synthetic ratings that drift over time, generated in this page: driftRatings({ seed: 111, n: 300 }); no real ratings"
        split="The first 240 rows train; the remaining 60 are the later window"
        features="user, movie, genre, noise"
        method="Random forest, scored out of bag against later-window error"
      />
    </article>
  );
}

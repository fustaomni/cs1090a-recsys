import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { randomFolds } from "../lib/importance.js";
import { mulberry32 } from "../lib/random.js";
import { timedRatings } from "../lib/ratings.js";
import {
  baseline,
  blockEdges,
  byTime,
  cutAt,
  futureLeaks,
  rollingFolds,
} from "../lib/timecv.js";

function rmseOn(predict, rows) {
  return Math.sqrt(rows.reduce((s, r) => s + (predict(r) - r.rating) ** 2, 0) / rows.length);
}

function summary(values) {
  const mean = values.reduce((s, v) => s + v, 0) / values.length;
  const sd = Math.sqrt(values.reduce((s, v) => s + (v - mean) ** 2, 0) / (values.length - 1));
  return { mean, se: sd / Math.sqrt(values.length) };
}

export default function T5() {
  const [blocks, setBlocks] = useState(5);
  const [sliding, setSliding] = useState(false);
  const [width, setWidth] = useState(2);
  const [gap, setGap] = useState(0);
  const [shown, setShown] = useState(0);

  const rows = useMemo(() => byTime(timedRatings({ seed: 181 })), []);
  const tval = useMemo(() => cutAt(rows, 0.8), [rows]);
  const ttest = useMemo(() => cutAt(rows, 0.9), [rows]);
  const edges = useMemo(() => blockEdges(rows, tval, blocks), [rows, tval, blocks]);
  const folds = useMemo(
    () => rollingFolds(edges, { sliding, width, gap }),
    [edges, sliding, width, gap],
  );
  const rolling = useMemo(
    () =>
      folds.map((fold) => {
        const train = fold.train.map((i) => rows[i]);
        const valid = fold.valid.map((i) => rows[i]);
        return {
          rmse: rmseOn(baseline(train), valid),
          lastTrain: Math.max(...train.map((r) => r.time)),
          firstValid: Math.min(...valid.map((r) => r.time)),
          leaks: futureLeaks(train, valid),
          sizes: [train.length, fold.gap.length, valid.length],
        };
      }),
    [folds, rows],
  );
  const random = useMemo(() => {
    const window = rows.slice(0, tval);
    return randomFolds(window.length, blocks, mulberry32(7)).map((fold) => {
      const held = new Set(fold);
      const train = window.filter((_, i) => !held.has(i));
      const valid = fold.map((i) => window[i]);
      return { rmse: rmseOn(baseline(train), valid), leaks: futureLeaks(train, valid) };
    });
  }, [rows, tval, blocks]);
  const rollingSummary = summary(rolling.map((f) => f.rmse));
  const randomSummary = summary(random.map((f) => f.rmse));
  const current = Math.min(shown, folds.length - 1);

  const timelineTraces = useCallback(
    (colors) => {
      const lane = (name, from, to, y, color, width) => ({
        type: "scatter",
        mode: "lines",
        name,
        showlegend: y === folds.length,
        x: [from, to],
        y: [y, y],
        line: { color, width },
        hoverinfo: "skip",
      });
      const traces = [];
      folds.forEach((fold, k) => {
        const y = folds.length - k;
        const thick = k === current ? 16 : 9;
        if (fold.train.length) {
          const end = fold.train.at(-1) + 1;
          traces.push(lane("Train (fit here)", fold.train[0], end, y, colors.ink, thick));
        }
        if (fold.gap.length) {
          traces.push(lane("Gap", fold.gap[0], fold.gap.at(-1) + 1, y, colors.line, thick));
        }
        const after = fold.valid.at(-1) + 1;
        traces.push(lane("Validate", fold.valid[0], after, y, colors.accent, thick));
        traces.push(lane("Hidden", after, tval, y, colors.muted, 2));
      });
      traces.push(
        {
          type: "scatter",
          mode: "lines",
          name: "Fenced: T_val and T_test",
          x: [tval, tval, null, ttest, ttest],
          y: [0.3, folds.length + 0.7, null, 0.3, folds.length + 0.7],
          line: { color: colors.accent, dash: "dot", width: 2 },
        },
      );
      return traces;
    },
    [folds, current, tval, ttest],
  );
  const rmseTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "markers",
        name: "Rolling folds",
        x: rolling.map((_, k) => k + 1),
        y: rolling.map((f) => f.rmse),
        marker: { size: 11, color: colors.accent },
      },
      {
        type: "scatter",
        mode: "markers",
        name: "Random k-fold",
        x: random.map((_, k) => k + 1),
        y: random.map((f) => f.rmse),
        marker: { size: 9, color: colors.muted, symbol: "diamond" },
      },
      ...[
        [rollingSummary.mean, colors.accent, "Rolling mean"],
        [randomSummary.mean, colors.muted, "Random mean"],
      ].map(([value, color, name]) => ({
        type: "scatter",
        mode: "lines",
        name,
        x: [0.5, Math.max(rolling.length, random.length) + 0.5],
        y: [value, value],
        line: { color, dash: "dash" },
      })),
    ],
    [rolling, random, rollingSummary, randomSummary],
  );
  const timelineLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Ratings in time order (equal-count blocks)" } },
      yaxis: {
        title: { text: "Fold" },
        showticklabels: false,
        range: [0.3, folds.length + 0.7],
      },
    }),
    [folds.length],
  );
  const rmseLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Fold" }, dtick: 1 },
      yaxis: { title: { text: "Validation RMSE" } },
    }),
    [],
  );
  const fold = rolling[current];

  return (
    <article className="lab">
      <h3>Technique · Time-aware cross-validation</h3>
      <p>
        Folds subdivide only the training window, before T_val; the validation and test windows
        stay fenced off until the end. The window is cut into blocks of equal row count, not
        equal calendar time, because ratings are front-loaded, and each cut moves to a timestamp
        boundary. Fold k trains on the blocks before block k + 1 and validates on it; the
        scaler, encodings and any PCA are refitted on each fold's training rows.
      </p>
      <Plot traces={timelineTraces} layout={timelineLayout} label="Folds on the timeline" />
      <div className="controls">
        <Slider
          label="Blocks k"
          value={blocks}
          min={3}
          max={8}
          step={1}
          onChange={(value) => {
            setBlocks(value);
            setShown(0);
          }}
          format={String}
        />
        <Slider
          label="Gap before validation, rows"
          value={gap}
          min={0}
          max={60}
          step={5}
          onChange={setGap}
          format={String}
        />
        <label className="control check">
          <input
            type="checkbox"
            checked={sliding}
            onChange={(event) => setSliding(event.target.checked)}
          />
          <span>Sliding window instead of expanding</span>
        </label>
        {sliding && (
          <Slider
            label="Blocks kept, max_train_size"
            value={width}
            min={1}
            max={blocks - 1}
            step={1}
            onChange={setWidth}
            format={String}
          />
        )}
        <button
          type="button"
          className="action"
          onClick={() => setShown((current + 1) % folds.length)}
        >
          Next fold
        </button>
      </div>
      <dl className="readouts">
        <div>
          <dt>Fold {current + 1} of {folds.length}</dt>
          <dd>
            {fold.sizes[0]} training rows, {fold.sizes[1]} dropped as a gap, {fold.sizes[2]}{" "}
            validated; last training day {fold.lastTrain} &lt; first validation day{" "}
            {fold.firstValid} {fold.lastTrain < fold.firstValid ? "✓" : "✗"}
          </dd>
        </div>
        <div>
          <dt>Rows whose features include their own future</dt>
          <dd>
            Rolling folds: {rolling.reduce((s, f) => s + f.leaks, 0)}. Random k-fold:{" "}
            {random.reduce((s, f) => s + f.leaks, 0)}, rows validated with user statistics that
            used that user's later ratings.
          </dd>
        </div>
        <div>
          <dt>Validation RMSE</dt>
          <dd>
            Rolling {fixed(rollingSummary.mean)} ± {fixed(rollingSummary.se)}; random k-fold{" "}
            {fixed(randomSummary.mean)} ± {fixed(randomSummary.se)}; optimism of random folds{" "}
            {fixed(rollingSummary.mean - randomSummary.mean)}
          </dd>
        </div>
      </dl>
      <Plot traces={rmseTraces} layout={rmseLayout} label="RMSE per fold" height={300} />
      <p className="muted">
        Time folds are not independent and later folds train on more data, so the ± 1 standard
        error behind the one-standard-error rule is approximate. Random folds look better because
        a validated rating's user and movie averages can include ratings that came after it, the
        leak that Phase 2's Protocol C measures. Seeded synthetic ratings, {rows.length} in all,
        with T_val and T_test at the 0.8 and 0.9 quantiles of time.
      </p>
      <Provenance
        data="Synthetic time-stamped ratings, generated in this page: timedRatings({ seed: 181 }); no real ratings"
        split="T_val and T_test at the 0.8 and 0.9 quantiles of time; folds in equal-count blocks before T_val"
        method="Shrunk user and movie offsets, refitted on each fold's training rows"
      />
    </article>
  );
}

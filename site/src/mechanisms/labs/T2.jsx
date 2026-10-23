import { useCallback, useMemo, useState } from "react";
import data from "../../data/movielens.json";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { correlation, encodings, smoothed } from "../lib/encoding.js";
import { fixed } from "../lib/format.js";
import { timedRatings } from "../lib/ratings.js";
import { byTime, cutAt } from "../lib/timecv.js";

const SPLIT = data.splits["0.8/0.9"];
const MU = { train: SPLIT.training.mean, all: data.allRowsMean };

export default function T2() {
  const [n, setN] = useState(3);
  const [ybar, setYbar] = useState(4.6);
  const [own, setOwn] = useState(5);
  const [m, setM] = useState(10);
  const [scope, setScope] = useState("train");
  const [encoding, setEncoding] = useState("prior");

  const mu = MU[scope];
  const prior = smoothed(n, ybar, m, mu);
  const naive = smoothed(n + 1, (n * ybar + own) / (n + 1), m, mu);
  const selected = `${scope === "train" ? "training window" : "all rows"}, ` +
    `${encoding === "prior" ? "prior-only" : "naive"}`;
  const shown = encoding === "prior" ? prior : naive;
  const count = encoding === "prior" ? n : n + 1;
  const average = encoding === "prior" ? ybar : (n * ybar + own) / (n + 1);

  const rows = useMemo(() => byTime(timedRatings({ seed: 181 })), []);
  const study = useMemo(() => {
    const cut = cutAt(rows, 0.8);
    const train = rows.slice(0, cut);
    const later = rows.slice(cut);
    const mean = train.reduce((s, r) => s + r.rating, 0) / train.length;
    const coded = encodings(train, m, mean);
    const ys = train.map((r) => r.rating);
    const totals = new Map();
    for (const r of train) {
      const t = totals.get(r.user) ?? { sum: 0, n: 0 };
      totals.set(r.user, { sum: t.sum + r.rating, n: t.n + 1 });
    }
    const forLater = later.map((r) => {
      const t = totals.get(r.user) ?? { sum: 0, n: 0 };
      return smoothed(t.n, t.n ? t.sum / t.n : mean, m, mean);
    });
    return {
      naiveIn: correlation(coded.map((c) => c.naive), ys),
      priorIn: correlation(coded.map((c) => c.prior), ys),
      outside: correlation(forLater, later.map((r) => r.rating)),
    };
  }, [rows, m]);
  const timeline = useMemo(() => {
    const counts = new Map();
    for (const r of rows) counts.set(r.user, (counts.get(r.user) ?? 0) + 1);
    const busiest = [...counts.entries()].reduce((a, b) => (b[1] > a[1] ? b : a))[0];
    const mine = rows.filter((r) => r.user === busiest);
    return { mine, coded: encodings(mine, m, MU.train) };
  }, [rows, m]);
  const gap = study.naiveIn - study.outside;

  const lineTraces = useCallback(
    (colors) => {
      const withOwn = (n * ybar + own) / (n + 1);
      const cells = [
        ["training window", "prior-only", smoothed(n, ybar, m, MU.train)],
        ["training window", "naive", smoothed(n + 1, withOwn, m, MU.train)],
        ["all rows", "prior-only", smoothed(n, ybar, m, MU.all)],
        ["all rows", "naive", smoothed(n + 1, withOwn, m, MU.all)],
      ];
      return [
        {
          type: "scatter",
          mode: "markers+text",
          name: "This user's encoding",
          x: cells.map((c) => c[2]),
          y: cells.map((c) => `${c[0]}, ${c[1]}`),
          text: cells.map((c) => fixed(c[2], 3)),
          textposition: "top center",
          marker: {
            size: 12,
            color: cells.map((c) =>
              `${c[0]}, ${c[1]}` === selected ? colors.accent : colors.muted,
            ),
          },
        },
        {
          type: "scatter",
          mode: "lines",
          name: "μ, training window",
          x: [MU.train, MU.train],
          y: [`${cells[0][0]}, ${cells[0][1]}`, `${cells[3][0]}, ${cells[3][1]}`],
          line: { color: colors.ink, dash: "dot" },
        },
      ];
    },
    [n, ybar, own, m, selected],
  );
  const timelineTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "markers",
        name: "This user's ratings, in time order",
        x: timeline.mine.map((_, i) => i + 1),
        y: timeline.mine.map((r) => r.rating),
        marker: { size: 8, color: colors.muted },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "Naive mean (includes each row's own rating)",
        x: timeline.mine.map((_, i) => i + 1),
        y: timeline.coded.map((c) => c.naive),
        line: { color: colors.ink, dash: "dash" },
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Prior-only mean (earlier ratings only)",
        x: timeline.mine.map((_, i) => i + 1),
        y: timeline.coded.map((c) => c.prior),
        line: { color: colors.accent, shape: "hv" },
      },
    ],
    [timeline],
  );
  const lineLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Encoded value" } },
      yaxis: { automargin: true },
      margin: { l: 170 },
    }),
    [],
  );
  const timelineLayout = useMemo(
    () => ({
      xaxis: { title: { text: "The user's k-th rating" } },
      yaxis: { title: { text: "Rating" }, range: [0.5, 5.5] },
    }),
    [],
  );

  return (
    <article className="lab">
      <h3>Technique · Missingness and imputation</h3>
      <p>
        A user or movie with no history yet has no mean to use. The smoothed encoding fills it
        without a special case: S = (n·ȳ + m·μ) / (n + m) becomes μ when n = 0 and the user's
        own mean as n grows. The bigger danger is not the fallback but the row's own rating: a
        user mean that includes the rating being predicted leaks the target. The design uses
        prior-only means, built from each user's earlier ratings, the time-ordered form of
        out-of-fold encoding.
      </p>
      <Plot traces={lineTraces} layout={lineLayout} label="Encoding values" height={300} />
      <div className="controls">
        <Slider
          label="Earlier ratings n"
          value={n}
          min={0}
          max={50}
          step={1}
          onChange={setN}
          format={String}
        />
        <Slider
          label="Their mean ȳ"
          value={ybar}
          min={1}
          max={5}
          step={0.1}
          onChange={setYbar}
        />
        <Slider
          label="This row's own rating"
          value={own}
          min={1}
          max={5}
          step={1}
          onChange={setOwn}
          format={String}
        />
        <Slider
          label="Prior weight m"
          value={m}
          min={0}
          max={50}
          step={1}
          onChange={setM}
          format={String}
        />
        <label className="control">
          <span>Fit μ on</span>
          <select value={scope} onChange={(event) => setScope(event.target.value)}>
            <option value="train">the training window only</option>
            <option value="all">all rows, including the future</option>
          </select>
        </label>
        <label className="control">
          <span>Encoding</span>
          <select value={encoding} onChange={(event) => setEncoding(event.target.value)}>
            <option value="prior">prior-only (out-of-fold)</option>
            <option value="naive">naive (includes this row)</option>
          </select>
        </label>
      </div>
      <dl className="readouts">
        <div>
          <dt>S, with a count feature beside it</dt>
          <dd>
            S = ({count} × {fixed(average, 2)} + {m} × {fixed(mu, 3)}) / ({count} + {m}) ={" "}
            {fixed(shown, 3)}; count = {n}, so the model knows when S is the prior rather than
            evidence
          </dd>
        </div>
        <div>
          <dt>MovieLens 1M means</dt>
          <dd>
            Training window {fixed(MU.train, 3)}, validation window {fixed(SPLIT.validMean, 3)},
            all rows {fixed(MU.all, 3)}: a shift of {fixed(SPLIT.validMean - MU.train, 3)}, so the
            fallback's leak is small here; the row's own rating is the larger one
          </dd>
        </div>
        <div>
          <dt>Leakage gap, synthetic ratings</dt>
          <dd>
            Correlation with the rating: naive in-sample {fixed(study.naiveIn, 3)}, prior-only{" "}
            {fixed(study.priorIn, 3)}, the training mean on later rows {fixed(study.outside, 3)}.
            The gap of {fixed(gap, 3)} between in-sample and later is the leak.
          </dd>
        </div>
      </dl>
      <Plot
        traces={timelineTraces}
        layout={timelineLayout}
        label="One user's history"
        height={300}
      />
      <p className="muted">
        Two kinds of missing. A cold user or movie is structurally absent, and the smoothed
        encoding plus its count handles that. But ratings are also missing not at random: people
        rate what they chose to watch, mostly what they like, so the observed ratings are a
        biased sample. No imputation fixes that; it is a declared limitation, and the
        conclusions concern ratings users chose to submit. The prior weight m is a
        hyperparameter, tuned on time-ordered folds like any other.
      </p>
      <Provenance
        data="Window means from movielens.json, computed from the verified MovieLens 1M files (ratings.dat SHA-256 506d64ca); the leakage study uses synthetic timedRatings({ seed: 181 })"
        split="Training window before the 0.8 quantile of time"
        method="Smoothed mean S = (n ybar + m mu) / (n + m), naive or prior-only"
      />
    </article>
  );
}

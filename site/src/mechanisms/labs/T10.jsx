import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { crossedRatings, percentile, replicates } from "../lib/inference.js";
import { histogram } from "../lib/knn.js";

const CORRELATIONS = [0, 0.2, 0.4, 0.6, 0.8, 0.95];
const SCHEMES = { user: "users", pigeonhole: "users and films" };

function interval(values) {
  return {
    low: percentile(values, 0.025),
    high: percentile(values, 0.975),
    mean: values.reduce((s, v) => s + v, 0) / values.length,
  };
}

export default function T10() {
  const [shared, setShared] = useState(0.7);
  const [scheme, setScheme] = useState("user");
  const [draws, setDraws] = useState(1000);
  const [threshold, setThreshold] = useState(0.02);

  const data = useMemo(
    () => crossedRatings({ seed: 171, users: 60, films: 40, shared }),
    [shared],
  );
  const runs = useMemo(
    () => replicates(data.rows, scheme, data.users, data.films, draws, 29),
    [data, scheme, draws],
  );
  const a = interval(runs.map((r) => r.a));
  const b = interval(runs.map((r) => r.b));
  const paired = interval(runs.map((r) => r.difference));
  const observed = useMemo(() => {
    const rmse = (key) =>
      Math.sqrt(
        data.rows.reduce((s, r) => s + (r[key] - r.rating) ** 2, 0) / data.rows.length,
      );
    return { a: rmse("a"), b: rmse("b") };
  }, [data]);
  const delta = observed.a - observed.b;

  const sweep = useMemo(
    () =>
      CORRELATIONS.map((value) => {
        const d = crossedRatings({ seed: 171, users: 60, films: 40, shared: value });
        const r = replicates(d.rows, scheme, d.users, d.films, 300, 31);
        const width = (values) => percentile(values, 0.975) - percentile(values, 0.025);
        return {
          value,
          paired: width(r.map((x) => x.difference)),
          marginal: width(r.map((x) => x.b)),
        };
      }),
    [scheme],
  );
  const perUser = useMemo(() => {
    const groups = Array.from({ length: data.users }, () => ({ a: 0, b: 0, n: 0 }));
    data.rows.forEach((r) => {
      groups[r.user].a += (r.a - r.rating) ** 2;
      groups[r.user].b += (r.b - r.rating) ** 2;
      groups[r.user].n += 1;
    });
    return groups.map((g) => Math.sqrt(g.a / g.n) - Math.sqrt(g.b / g.n));
  }, [data]);
  const favouring = perUser.filter((d) => d < 0).length;
  const excludesZero = paired.low > 0 || paired.high < 0;
  const clears = paired.low > threshold;

  const intervalTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "markers",
        name: "Each model's RMSE, 95% interval",
        x: ["Baseline", "Best model"],
        y: [observed.a, observed.b],
        error_y: {
          type: "data",
          symmetric: false,
          array: [a.high - observed.a, b.high - observed.b],
          arrayminus: [observed.a - a.low, observed.b - b.low],
          color: colors.muted,
        },
        marker: { size: 11, color: colors.muted },
      },
    ],
    [observed, a, b],
  );
  const pairedTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "markers",
        name: "Paired ΔRMSE, 95% interval",
        x: ["Baseline − best"],
        y: [delta],
        error_y: {
          type: "data",
          symmetric: false,
          array: [paired.high - delta],
          arrayminus: [delta - paired.low],
          color: colors.accent,
        },
        marker: { size: 12, color: colors.accent },
      },
    ],
    [delta, paired],
  );
  const sweepTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Paired interval width",
        x: sweep.map((s) => s.value),
        y: sweep.map((s) => s.paired),
        line: { color: colors.accent },
      },
      {
        type: "scatter",
        mode: "lines+markers",
        name: "One model's interval width",
        x: sweep.map((s) => s.value),
        y: sweep.map((s) => s.marginal),
        line: { color: colors.muted },
      },
    ],
    [sweep],
  );
  const userTraces = useCallback(
    (colors) => {
      const low = Math.min(...perUser);
      const high = Math.max(...perUser);
      const bins = histogram(perUser, low, high, 20);
      return [
        {
          type: "scatter",
          mode: "lines",
          name: "Users",
          x: [...bins.map((bin) => bin.from), high],
          y: [...bins.map((bin) => bin.count), 0],
          line: { shape: "hv", color: colors.ink },
          fill: "tozeroy",
        },
      ];
    },
    [perUser],
  );
  const line = (x, color) => ({
    type: "line",
    x0: x,
    x1: x,
    yref: "paper",
    y0: 0,
    y1: 1,
    line: { dash: "dot", width: 1.5, color },
  });
  const intervalLayout = useMemo(() => ({ yaxis: { title: { text: "RMSE" } } }), []);
  const pairedLayout = useMemo(
    () => ({
      yaxis: { title: { text: "ΔRMSE" }, zeroline: true },
      shapes: [
        {
          type: "line",
          xref: "paper",
          x0: 0,
          x1: 1,
          y0: threshold,
          y1: threshold,
          line: { dash: "dot", width: 1.5, color: "rgba(127,127,127,0.8)" },
        },
      ],
    }),
    [threshold],
  );
  const sweepLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Shared error between the two models" } },
      yaxis: { title: { text: "95% interval width" }, rangemode: "tozero" },
    }),
    [],
  );
  const userLayout = useMemo(
    () => ({
      xaxis: { title: { text: "One user's ΔRMSE" } },
      yaxis: { title: { text: "Users" } },
      shapes: [line(0, "rgba(127,127,127,0.8)"), line(delta, "rgba(200,90,60,0.9)")],
    }),
    [delta],
  );

  return (
    <article className="lab">
      <h3>Technique · Hypothesis tests and intervals</h3>
      <p>
        Two models scored on the same test ratings make correlated errors. Their separate RMSE
        intervals can overlap heavily while the paired difference, recomputed on each resample
        of the same users, sits clearly away from zero: overlap of marginal intervals is not a
        test of a paired difference, and is badly conservative. The pre-registered test is the
        paired interval, judged against zero and against the smallest difference worth having.
      </p>
      <div className="lab-grid">
        <Plot traces={intervalTraces} layout={intervalLayout} label="Each model's interval" />
        <Plot traces={pairedTraces} layout={pairedLayout} label="The paired interval" />
      </div>
      <div className="controls">
        <Slider
          label="Shared error between the two models"
          value={shared}
          min={0}
          max={0.95}
          step={0.05}
          onChange={setShared}
        />
        <label className="control">
          <span>Resampling</span>
          <select value={scheme} onChange={(event) => setScheme(event.target.value)}>
            {Object.entries(SCHEMES).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <Slider
          label="Replicates B"
          value={draws}
          min={500}
          max={2000}
          step={500}
          onChange={setDraws}
          format={String}
        />
        <Slider
          label="Smallest meaningful difference"
          value={threshold}
          min={0}
          max={0.1}
          step={0.005}
          onChange={setThreshold}
          format={(value) => value.toFixed(3)}
        />
      </div>
      <dl className="readouts">
        <div>
          <dt>Primary comparison, pre-specified</dt>
          <dd>
            ΔRMSE = {fixed(delta)} ({fixed((100 * delta) / observed.a, 1)}% of the baseline's
            RMSE), 95% interval {fixed(paired.low)} to {fixed(paired.high)}, resampling{" "}
            {SCHEMES[scheme]}
          </dd>
        </div>
        <div>
          <dt>Verdict</dt>
          <dd>
            The interval {excludesZero ? "excludes" : "includes"} zero and{" "}
            {clears ? "clears" : "does not clear"} the smallest meaningful difference of{" "}
            {fixed(threshold)}. The marginal intervals{" "}
            {a.low <= b.high && b.low <= a.high ? "overlap" : "do not overlap"}, which on its own
            would decide nothing.
          </dd>
        </div>
        <div>
          <dt>Users are not unanimous</dt>
          <dd>
            {favouring} of {data.users} users are predicted better by the baseline; the test is
            about the mean difference, not every user
          </dd>
        </div>
      </dl>
      <div className="lab-grid">
        <Plot traces={sweepTraces} layout={sweepLayout} label="Width against shared error" />
        <Plot traces={userTraces} layout={userLayout} label="Per-user differences" />
      </div>
      <p className="muted">
        One comparison is pre-specified, so it needs no correction; every other model-against-
        baseline row on the results board is exploratory or Holm-corrected. With thousands of
        test users even a tiny difference can exclude zero, which is why the verdict also asks
        whether it clears a difference worth having. Seeded synthetic test ratings for two
        models with user and film effects.
      </p>
    </article>
  );
}

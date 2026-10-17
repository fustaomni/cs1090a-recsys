import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { crossedRatings, percentile, replicates } from "../lib/inference.js";
import { histogram } from "../lib/knn.js";
import { mulberry32 } from "../lib/random.js";

const SCHEMES = {
  row: "Ratings resampled",
  user: "Users resampled",
  pigeonhole: "Users and movies resampled",
};
const DRAWS = [100, 200, 500, 1000, 2000];

function interval(values) {
  return { low: percentile(values, 0.025), high: percentile(values, 0.975) };
}

export default function T9() {
  const [users, setUsers] = useState(60);
  const [shared, setShared] = useState(0.7);
  const [draws, setDraws] = useState(1000);

  const data = useMemo(
    () => crossedRatings({ seed: 151, users, movies: 40, shared }),
    [users, shared],
  );
  const runs = useMemo(
    () =>
      Object.fromEntries(
        Object.keys(SCHEMES).map((scheme) => [
          scheme,
          replicates(data.rows, scheme, data.users, data.movies, 2000, 23).map(
            (r) => r.difference,
          ),
        ]),
      ),
    [data],
  );
  const intervals = Object.fromEntries(
    Object.keys(SCHEMES).map((scheme) => [scheme, interval(runs[scheme].slice(0, draws))]),
  );
  const width = (scheme) => intervals[scheme].high - intervals[scheme].low;
  const observed = useMemo(() => {
    const rmse = (key) =>
      Math.sqrt(
        data.rows.reduce((s, r) => s + (r[key] - r.rating) ** 2, 0) / data.rows.length,
      );
    return rmse("a") - rmse("b");
  }, [data]);

  const mean = useMemo(() => {
    const rng = mulberry32(5);
    const byUser = Array.from({ length: data.users }, () => []);
    data.rows.forEach((r) => byUser[r.user].push(r.rating));
    const all = data.rows.map((r) => r.rating);
    const centre = all.reduce((s, v) => s + v, 0) / all.length;
    const spread = Math.sqrt(all.reduce((s, v) => s + (v - centre) ** 2, 0) / all.length);
    const means = Array.from({ length: 1000 }, () => {
      let total = 0;
      let count = 0;
      for (let k = 0; k < data.users; k += 1) {
        const picked = byUser[Math.floor(rng() * data.users)];
        total += picked.reduce((s, v) => s + v, 0);
        count += picked.length;
      }
      return total / count;
    });
    return { centre, spread, ...interval(means) };
  }, [data]);

  const histogramTraces = useCallback(
    (colors) => {
      const palette = { row: colors.muted, user: colors.ink, pigeonhole: colors.accent };
      const all = Object.values(runs).flat();
      const low = Math.min(...all);
      const high = Math.max(...all);
      return Object.keys(SCHEMES).flatMap((scheme) => {
        const bins = histogram(runs[scheme].slice(0, draws), low, high, 40);
        return [
          {
            type: "scatter",
            mode: "lines",
            name: SCHEMES[scheme],
            x: [...bins.map((bin) => bin.from), high],
            y: [...bins.map((bin) => bin.count), 0],
            line: { shape: "hv", color: palette[scheme], width: 2 },
          },
        ];
      });
    },
    [runs, draws],
  );
  const endpointTraces = useCallback(
    (colors) =>
      ["low", "high"].map((end) => ({
        type: "scatter",
        mode: "lines+markers",
        name: end === "low" ? "2.5% endpoint" : "97.5% endpoint",
        x: DRAWS,
        y: DRAWS.map((b) => interval(runs.user.slice(0, b))[end]),
        line: { color: end === "low" ? colors.ink : colors.accent },
      })),
    [runs],
  );
  const histogramLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Paired ΔRMSE, baseline − best model" } },
      yaxis: { title: { text: "Bootstrap replicates" } },
    }),
    [],
  );
  const endpointLayout = useMemo(
    () => ({
      xaxis: { type: "log", title: { text: "Bootstrap replicates B (log scale)" } },
      yaxis: { title: { text: "User-clustered endpoint" } },
    }),
    [],
  );

  return (
    <article className="lab">
      <h3>Technique · Bootstrap inference</h3>
      <p>
        Every test rating belongs to one user and one movie, and ratings from the same user, or
        of the same movie, share error. Resampling single ratings treats them as independent and
        makes intervals too narrow. Resampling whole users fixes the first dependence;
        resampling users and movies independently, Owen's pigeonhole bootstrap, also covers the
        second and is mildly conservative. The statistic is the paired difference in RMSE
        between a baseline and the best model, recomputed on each resample.
      </p>
      <div className="lab-grid">
        <Plot traces={histogramTraces} layout={histogramLayout} label="Replicates by scheme" />
        <Plot traces={endpointTraces} layout={endpointLayout} label="Endpoints against B" />
      </div>
      <div className="controls">
        <Slider
          label="Test users"
          value={users}
          min={20}
          max={80}
          step={5}
          onChange={setUsers}
          format={String}
        />
        <Slider
          label="Shared error between the two models"
          value={shared}
          min={0}
          max={0.95}
          step={0.05}
          onChange={setShared}
        />
        <Slider
          label="Replicates B"
          value={draws}
          min={100}
          max={2000}
          step={100}
          onChange={setDraws}
          format={String}
        />
      </div>
      <dl className="readouts">
        <div>
          <dt>Observed difference</dt>
          <dd>
            ΔRMSE = {fixed(observed)} over {data.rows.length} ratings from {data.users} users and{" "}
            {data.movies} movies
          </dd>
        </div>
        {Object.keys(SCHEMES).map((scheme) => (
          <div key={scheme}>
            <dt>{SCHEMES[scheme]}</dt>
            <dd>
              95% interval {fixed(intervals[scheme].low)} to {fixed(intervals[scheme].high)},
              width {fixed(width(scheme))}
              {scheme === "row"
                ? ""
                : `, ${fixed(width(scheme) / width("row"), 2)}× the row width`}
            </dd>
          </div>
        ))}
        <div>
          <dt>A predicted mean is not a prediction</dt>
          <dd>
            The mean rating is {fixed(mean.centre, 2)} with a user-clustered 95% interval{" "}
            {fixed(mean.low, 2)} to {fixed(mean.high, 2)}; one new rating ranges about ±
            {fixed(1.96 * mean.spread, 2)} around it, the noise a prediction interval must add.
          </dd>
        </div>
      </dl>
      <p className="muted">
        Percentile endpoints rest on the replicates in the tails, about 2.5% of B at each end,
        so they settle only with B in the thousands; resampling the metric needs no refitting,
        which makes that cheap. Seeded synthetic test ratings with user and movie effects.
      </p>
    </article>
  );
}

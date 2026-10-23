import { useCallback, useMemo, useState } from "react";
import data from "../../data/movielens.json";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import { fixed } from "../lib/format.js";

const SPLITS = { "0.8/0.9": [0.8, 0.9], "0.85/0.95": [0.85, 0.95] };
const STARS = ["1★", "2★", "3★", "4★", "5★"];
const AGE_ORDER = ["under 18", "18–24", "25–34", "35–44", "45–49", "50–55", "56+"];
const integer = (n) => n.toLocaleString("en-US");
const percent = (part, whole) => `${fixed((100 * part) / whole, 1)}%`;

function dayToDate(day) {
  const start = new Date(`${data.timeline.first}T00:00:00Z`);
  return new Date(start.getTime() + day * 86400000).toISOString().slice(0, 10);
}

function Bars({ rows }) {
  const largest = Math.max(...rows.map(([, value]) => value));
  return (
    <div className="bars">
      {rows.map(([label, value, note]) => (
        <div className="bar-row" key={label}>
          <span>{label}</span>
          <div className="bar-track">
            <div className="bar-fill" style={{ width: `${(value / largest) * 100}%` }} />
          </div>
          <strong>{note ?? integer(value)}</strong>
        </div>
      ))}
    </div>
  );
}

export default function T1() {
  const [key, setKey] = useState("0.8/0.9");
  const [split, setSplit] = useState(false);
  const chosen = SPLITS[key];
  const summary = data.splits[key];
  const training = summary.training;
  const s = data.structure;

  const dates = useMemo(() => data.timeline.cumulative.map((_, day) => dayToDate(day)), []);
  const timelineTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines",
        name: "Ratings so far (all rows)",
        x: dates,
        y: data.timeline.cumulative,
        line: { color: colors.ink, width: 2.5 },
      },
    ],
    [dates],
  );
  const timelineLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Date the rating was submitted" }, type: "date" },
      yaxis: { title: { text: "Cumulative ratings" } },
      shapes: Object.entries(data.quantiles).map(([q, cut]) => {
        const active = chosen.includes(Number(q));
        return {
          type: "line",
          x0: cut.date,
          x1: cut.date,
          yref: "paper",
          y0: 0,
          y1: 1,
          line: {
            dash: active ? "solid" : "dot",
            width: active ? 2.5 : 1,
            color: active ? "rgba(200,90,60,0.95)" : "rgba(127,127,127,0.6)",
          },
        };
      }),
      annotations: Object.entries(data.quantiles).map(([q, cut], k) => ({
        x: cut.date,
        yref: "paper",
        y: 1.02,
        yshift: 12 * k,
        text: q,
        showarrow: false,
        font: { size: 11 },
      })),
    }),
    [chosen],
  );
  const monthlyTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines",
        name: "Ratings per month, training window",
        x: training.monthly.map((m) => `${m.month}-01`),
        y: training.monthly.map((m) => m.count),
        line: { shape: "hvh", color: colors.accent },
        fill: "tozeroy",
      },
    ],
    [training],
  );
  const tailTraces = useCallback(
    (colors) => [
      ...[
        ["users", training.userTail, colors.ink],
        ["movies", training.movieTail, colors.accent],
      ].map(([name, bins, color]) => ({
        type: "scatter",
        mode: "lines+markers",
        name: `Number of ${name}`,
        x: bins.map((b) => b.from),
        y: bins.map((b) => Math.max(b.count, 0.8)),
        line: { color, shape: "hv" },
      })),
    ],
    [training],
  );
  const monthlyLayout = useMemo(
    () => ({
      xaxis: { type: "date", title: { text: "Month" } },
      yaxis: { title: { text: "Ratings" } },
    }),
    [],
  );
  const tailLayout = useMemo(
    () => ({
      xaxis: { type: "log", title: { text: "Ratings per entity (doubling bins, log scale)" } },
      yaxis: { type: "log", title: { text: "Entities (log scale)" } },
    }),
    [],
  );

  const windows = summary.windows;
  const sparse = training.movieTail.filter((b) => b.to < 8).reduce((t, b) => t + b.count, 0);
  const smallestGenre = training.genres.reduce((a, g) => (g.ratings < a.ratings ? g : a));
  const shares = training.counts.map((n) => n / windows.train.rows);
  const pairs = [];
  data.genres.forEach((g, i) =>
    data.genres.forEach((h, j) => {
      if (j > i && training.together[i][j] > 0) pairs.push([g, h, training.together[i][j]]);
    }),
  );
  pairs.sort((a, b) => b[2] - a[2]);
  const cut = data.quantiles[chosen[0]];
  const span = data.timeline.cumulative.length - 1;
  const register = [
    [
      "Ratings are front-loaded in time",
      `${percent(cut.index, s.ratings)} of all ratings were submitted by ${cut.date}, ` +
        `day ${cut.day} of ${span}`,
      "Cut at quantiles of time, never at calendar dates; blocks of equal row count for folds",
      "Phase 2",
    ],
    [
      "The ordinal target is imbalanced",
      `${percent(training.counts[0], windows.train.rows)} of training ratings are 1★ against ` +
        `${percent(training.counts[3], windows.train.rows)} at 4★; skew ${fixed(training.skew, 2)}`,
      "Report macro-averaged error beside pooled error, with the constant floors",
      "Phase 0",
    ],
    [
      "Long tails and cold start",
      `${integer(sparse)} of ${integer(windows.train.movies)} movies have fewer than 8 ` +
        `training ratings; ${integer(summary.testUsersUnseen)} of ` +
        `${integer(summary.testUsers)} test users never appear in training`,
      "Smoothed prior-only encodings, a count feature, and cold-start thresholds",
      "Phases 3 and 12",
    ],
    [
      "Sparse genres",
      `${smallestGenre.genre} has ${integer(smallestGenre.ratings)} training ratings, ` +
        `${percent(smallestGenre.ratings, windows.train.rows)} of the window`,
      "Expect split bias toward dense features; judge importance by permutation",
      "Phase 8",
    ],
    [
      "The movie list is not UTF-8",
      `${s.nonUtf8MovieLines} lines of movies.dat fail UTF-8 decoding`,
      "Read all three files as Latin-1",
      "Phase 1A",
    ],
  ];
  const audit = [
    ["Ratings", integer(s.ratings)],
    ["Users", `${integer(s.users)}, each with at least ${s.fewestRatingsPerUser} ratings`],
    [
      "Movies",
      `${integer(s.moviesRated)} rated, of ${integer(s.moviesListed)} listed in movies.dat`,
    ],
    ["Span", `${s.firstDay} to ${s.lastDay}`],
    ["Encoding", `${s.nonUtf8MovieLines} movie lines are not UTF-8: read as Latin-1`],
    [
      "Integrity",
      `${s.duplicatePairs} duplicate user–movie pairs; ${s.unknownUsers} unknown users; ` +
        `${s.unknownMovies} unknown movies`,
    ],
  ];
  const WINDOW_NAMES = {
    train: "Training window",
    valid: "Validation window",
    test: "Test window",
  };

  return (
    <article className="lab">
      <h3>Technique · EDA and visualisation</h3>
      <p>
        Exploration is split in two, because exploring every row is itself a leak. Phase 1A
        audits the structure of all rows: counts over time, encoding and integrity, never the
        rating values. Phase 1B looks at rating values only inside the training window, and
        only once the split is made. Every number below is computed from MovieLens 1M itself.
      </p>
      <h4>Phase 1A · all rows, structure only</h4>
      <Plot
        traces={timelineTraces}
        layout={timelineLayout}
        label="Cumulative ratings"
        height={320}
      />
      <div className="controls">
        <label className="control">
          <span>Cutoffs T_val / T_test (quantiles of time)</span>
          <select value={key} onChange={(event) => setKey(event.target.value)}>
            {Object.keys(SPLITS).map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="action" onClick={() => setSplit(!split)}>
          {split ? "Lock the rating values again" : "Make the split and open Phase 1B"}
        </button>
      </div>
      <div className="table-wrap">
        <table>
          <tbody>
            {audit.map(([label, value]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                <td>{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <dl className="readouts">
        {["train", "valid", "test"].map((name) => (
          <div key={name}>
            <dt>{WINDOW_NAMES[name]}</dt>
            <dd>
              {integer(windows[name].rows)} ratings, {integer(windows[name].users)} users,{" "}
              {integer(windows[name].movies)} movies
            </dd>
          </div>
        ))}
        <div>
          <dt>Cold start in the test window</dt>
          <dd>
            {integer(summary.testUsersUnseen)} of {integer(summary.testUsers)} test users (
            {percent(summary.testUsersUnseen, summary.testUsers)}) never rated in training;{" "}
            {integer(summary.testUsersUnderFive)} have fewer than 5 training ratings;{" "}
            {integer(summary.testMoviesUnseen)} test movies are new
          </dd>
        </div>
      </dl>
      <h4>Phase 1B · training window only</h4>
      {split ? (
        <>
          <div className="lab-grid">
            <Plot traces={monthlyTraces} layout={monthlyLayout} label="Ratings per month" />
            <Plot traces={tailTraces} layout={tailLayout} label="Long tails" />
          </div>
          <div className="lab-grid">
            <div>
              <h4>Rating distribution</h4>
              <Bars
                rows={training.counts.map((n, k) => [STARS[k], n, percent(n, windows.train.rows)])}
              />
              <p className="muted">
                Mean {fixed(training.mean, 3)}, skew {fixed(training.skew, 2)}: most ratings are
                3★ or 4★, and 1★ is rare ({percent(shares[0], 1)}).
              </p>
            </div>
            <div>
              <h4>Who rated, in aggregate</h4>
              <Bars rows={AGE_ORDER.map((age) => [age, training.age[age] ?? 0])} />
              <p className="muted">
                {integer(training.gender.F ?? 0)} women and {integer(training.gender.M ?? 0)}{" "}
                men;{" "}
                {training.occupations} occupations; zip codes shown only by first digit, across{" "}
                {Object.keys(training.zipRegions).length} regions.
              </p>
            </div>
          </div>
          <h4>Genres: 18 multi-hot columns</h4>
          <Bars
            rows={training.genres
              .slice()
              .sort((a, b) => b.ratings - a.ratings)
              .map((g) => [`${g.genre} (${g.movies} movies)`, g.ratings])}
          />
          <p className="muted">
            Movies carry several genres; the pairs that co-occur most often are{" "}
            {pairs
              .slice(0, 4)
              .map(([g, h, n]) => `${g} with ${h} (${n} movies)`)
              .join(", ")}
            .
          </p>
        </>
      ) : (
        <p className="in-progress">
          Rating values stay locked until the split is made: press the button above.
        </p>
      )}
      <h4>The risk register, generated from these numbers</h4>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Risk</th>
              <th scope="col">Evidence</th>
              <th scope="col">Consequence</th>
              <th scope="col">Handled in</th>
            </tr>
          </thead>
          <tbody>
            {register.map(([risk, evidence, consequence, phase]) => (
              <tr key={risk}>
                <th scope="row">{risk}</th>
                <td>{evidence}</td>
                <td>{consequence}</td>
                <td>{phase}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        Computed from the MovieLens 1M files by site/scripts/movielens-summary.mjs. Changing the
        cutoffs updates every window, count and risk, which is Phase 2's sensitivity analysis.
      </p>
      <Provenance
        data="MovieLens 1M aggregates in movielens.json, computed by site/scripts/movielens-summary.mjs from the files data:fetch verified against the MD5 GroupLens publishes (ratings.dat SHA-256 506d64ca)"
        split="Cutoffs at quantiles of time: 0.8 or 0.85 for validation, 0.9 or 0.95 for test"
        method="Counts and summaries only; rating values come from the training window"
      />
    </article>
  );
}

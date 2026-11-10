import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import {
  CROSSED,
  crossedFit,
  crossedRatings,
  kept,
  movieLabel,
  predict,
  userLabel,
} from "../lib/crossed.js";

const ROW = "#38bdf8";
const COLUMN = "#f43f5e";
const CROSS = "#a78bfa";
const whole = (value) => value.toFixed(0);
const signed = (value) => `${value >= 0 ? "+" : "\u2212"}${Math.abs(value).toFixed(2)}`;
const ids = (size) => Array.from({ length: size }, (_, index) => index);

export default function M13() {
  const [user, setUser] = useState(4);
  const [movie, setMovie] = useState(8);
  const [pooling, setPooling] = useState(2);

  const { rows } = useMemo(() => crossedRatings({ seed: 131 }), []);
  const fit = useMemo(() => crossedFit(rows, { pooling }), [rows, pooling]);
  const raw = useMemo(() => crossedFit(rows, { pooling: 0 }), [rows]);

  const u = user - 1;
  const m = movie - 1;
  const bu = fit.users[u];
  const bm = fit.movies[m];
  const y = predict(fit, u, m);

  const matrix = useCallback(
    (colors) => [
      {
        type: "scatter3d",
        mode: "markers",
        name: "Observed ratings",
        x: rows.map((row) => row.user + 1),
        y: rows.map((row) => row.movie + 1),
        z: rows.map((row) => row.rating),
        marker: { size: 3, color: colors.muted, opacity: 0.6 },
      },
      {
        type: "scatter3d",
        mode: "lines+markers",
        name: `User ${user} row`,
        x: ids(CROSSED.movies).map(() => user),
        y: ids(CROSSED.movies).map((index) => index + 1),
        z: ids(CROSSED.movies).map((index) => predict(fit, u, index)),
        line: { color: ROW, width: 5 },
        marker: { size: 4, color: ROW },
      },
      {
        type: "scatter3d",
        mode: "lines+markers",
        name: `Movie ${movie} column`,
        x: ids(CROSSED.users).map((index) => index + 1),
        y: ids(CROSSED.users).map(() => movie),
        z: ids(CROSSED.users).map((index) => predict(fit, index, m)),
        line: { color: COLUMN, width: 5 },
        marker: { size: 4, color: COLUMN },
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Crossed prediction",
        x: [user],
        y: [movie],
        z: [y],
        marker: { size: 9, color: CROSS, line: { color: colors.ink, width: 1 } },
      },
    ],
    [rows, fit, user, movie, u, m, y],
  );

  const matrixLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User (row)" }, dtick: 1 },
        yaxis: { title: { text: "Movie (column)" }, dtick: 1 },
        zaxis: { title: { text: "Rating" }, range: [1, 5], dtick: 1 },
        camera: { eye: { x: 1.5, y: -1.5, z: 0.9 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  const shrinkage = useCallback(
    (colors) => {
      const xs = fit.userCount;
      const link = { x: [], y: [] };
      xs.forEach((count, index) => {
        link.x.push(count, count, null);
        link.y.push(raw.users[index], fit.users[index], null);
      });
      return [
        {
          type: "scatter",
          mode: "lines",
          name: "Pulled toward zero",
          x: link.x,
          y: link.y,
          line: { color: colors.muted, width: 1 },
          hoverinfo: "skip",
        },
        {
          type: "scatter",
          mode: "markers",
          name: "No pooling (raw offset)",
          x: xs,
          y: raw.users,
          marker: { size: 8, color: colors.muted },
        },
        {
          type: "scatter",
          mode: "markers",
          name: "Partial pooling (model 13)",
          x: xs,
          y: fit.users,
          marker: { size: 9, color: ROW, symbol: "diamond" },
        },
      ];
    },
    [fit, raw],
  );

  const shrinkageLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Ratings the user gave, n" } },
      yaxis: { title: { text: "User offset" }, zeroline: true },
    }),
    [],
  );

  const userKept = kept(fit.userCount[u], pooling);
  const movieKept = kept(fit.movieCount[m], pooling);

  return (
    <article className="lab">
      <p>
        A rating is the grand mean plus an offset for the user and an offset for the movie, the
        two crossed rather than nested. Each offset is partially pooled: a user who rated few
        movies is pulled toward the crowd, one who rated many keeps their own. The pooling
        strength is the ratio of rating noise to how much users and movies truly differ.
      </p>
      <div className="lab-grid">
        <Plot traces={matrix} layout={matrixLayout} label="The user-movie matrix, crossed" />
        <Plot traces={shrinkage} layout={shrinkageLayout} label="Raw against pooled offsets" />
      </div>
      <div className="controls">
        <Slider
          label="Select user (row)"
          value={user}
          min={1}
          max={CROSSED.users}
          step={1}
          onChange={setUser}
          format={whole}
        />
        <Slider
          label="Select movie (column)"
          value={movie}
          min={1}
          max={CROSSED.movies}
          step={1}
          onChange={setMovie}
          format={whole}
        />
        <Slider
          label="Pooling strength σ²/τ²"
          value={pooling}
          min={0}
          max={20}
          step={0.5}
          onChange={setPooling}
        />
      </div>
      <dl className="readouts">
        <div>
          <dt>Crossed prediction</dt>
          <dd>
            Y = μ ({fit.mu.toFixed(2)}) {signed(bu)} (user {user}, {userLabel(bu)}){" "}
            {signed(bm)} (movie {movie}, {movieLabel(bm)}) = {y.toFixed(2)}
          </dd>
        </div>
        <div>
          <dt>User {user}</dt>
          <dd>
            rated {fit.userCount[u]} movies; raw offset {signed(raw.users[u])}, keeps{" "}
            {(100 * userKept).toFixed(0)}% of it as n / (n + σ²/τ²), so {signed(bu)}
          </dd>
        </div>
        <div>
          <dt>Movie {movie}</dt>
          <dd>
            rated by {fit.movieCount[m]} users; raw offset {signed(raw.movies[m])}, keeps{" "}
            {(100 * movieKept).toFixed(0)}% of it, so {signed(bm)}
          </dd>
        </div>
      </dl>
      <p className="muted">
        The prediction is the intersection of this user's identity and this movie's identity,
        each trusted only as far as its own ratings allow. At σ²/τ² = 0 the offsets are raw
        means; as it grows they shrink to zero and every prediction becomes μ.
      </p>
      <Provenance
        data="Synthetic ratings, generated in this page: crossedRatings({ seed: 131 }); no real ratings"
        method="Crossed random intercepts, each the BLUP Σ residual / (n + σ²/τ²), fitted by alternating updates"
      />
    </article>
  );
}

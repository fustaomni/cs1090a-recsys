import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { steps } from "../lib/grid.js";
import {
  euclidean,
  gower,
  histogram,
  kdNearest,
  kdTree,
  manhattan,
  nearest,
  relativeContrast,
} from "../lib/knn.js";
import { rmse } from "../lib/metrics.js";
import { standardiser } from "../lib/penalized.js";
import { mulberry32 } from "../lib/random.js";
import { neighbourRatings } from "../lib/ratings.js";

const KEYS = ["user", "movie", "recency"];
const TRAIN = 240;
const KS = Array.from({ length: 40 }, (_, index) => index + 1);
const DIMENSIONS = [1, 2, 3, 5, 10, 20, 50, 100];
const METRICS = { euclidean: "Euclidean", manhattan: "Manhattan", gower: "Gower" };

function cloud(d) {
  const rng = mulberry32(500 + d);
  return Array.from({ length: 400 }, () => Array.from({ length: d }, () => rng()));
}

// The neighbourhood holding exactly the k nearest rows: a ball for Euclidean, an octahedron for
// Manhattan, and for Gower an octahedron stretched by each feature's range.
function neighbourhood(metric, centre, radius, ranges) {
  if (metric === "euclidean") {
    const theta = steps(0, Math.PI, 16);
    const phi = steps(0, 2 * Math.PI, 24);
    const along = (f) => theta.map((t) => phi.map((p) => f(t, p)));
    return {
      type: "surface",
      x: along((t, p) => centre[0] + radius * Math.sin(t) * Math.cos(p)),
      y: along((t, p) => centre[1] + radius * Math.sin(t) * Math.sin(p)),
      z: along((t) => centre[2] + radius * Math.cos(t)),
    };
  }
  const reach =
    metric === "manhattan" ? [radius, radius, radius] : ranges.map((range) => 4 * radius * range);
  const corners = [0, 1, 2].flatMap((axis) =>
    [1, -1].map((sign) => centre.map((c, j) => c + (j === axis ? sign * reach[axis] : 0))),
  );
  const faces = [];
  for (const a of [0, 1]) for (const b of [2, 3]) for (const c of [4, 5]) faces.push([a, b, c]);
  return {
    type: "mesh3d",
    x: corners.map((point) => point[0]),
    y: corners.map((point) => point[1]),
    z: corners.map((point) => point[2]),
    i: faces.map((face) => face[0]),
    j: faces.map((face) => face[1]),
    k: faces.map((face) => face[2]),
  };
}

export default function M6() {
  const [k, setK] = useState(10);
  const [metric, setMetric] = useState("euclidean");
  const [pick, setPick] = useState(0);
  const [dimension, setDimension] = useState(3);

  const rows = useMemo(() => neighbourRatings({ seed: 71, n: 300 }), []);
  const train = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const later = useMemo(() => rows.slice(TRAIN), [rows]);
  const standard = useMemo(() => standardiser(train, KEYS), [train]);
  const vector = useCallback((row) => [...standard(row), row.group], [standard]);
  const points = useMemo(() => train.map(vector), [train, vector]);
  const numeric = useMemo(() => points.map((point) => point.slice(0, 3)), [points]);
  const ranges = useMemo(
    () =>
      [0, 1, 2].map((j) => {
        const values = numeric.map((p) => p[j]);
        return Math.max(...values) - Math.min(...values);
      }),
    [numeric],
  );
  const distance = useMemo(() => {
    if (metric === "gower") return gower(ranges, [3]);
    const base = metric === "euclidean" ? euclidean : manhattan;
    return (a, b) => base(a.slice(0, 3), b.slice(0, 3));
  }, [metric, ranges]);
  const ratings = useMemo(() => train.map((row) => row.rating), [train]);

  const queryRow = later[pick];
  const query = vector(queryRow);
  const found = nearest(points, query, k, distance);
  const radius = found[found.length - 1].distance;
  const guess = found.reduce((s, hit) => s + ratings[hit.index], 0) / found.length;

  const curve = useMemo(() => {
    const laterPoints = later.map(vector);
    const actual = later.map((row) => row.rating);
    const sorted = laterPoints.map((q) => nearest(points, q, KS.length, distance));
    return KS.map((size) =>
      rmse(
        sorted.map(
          (hits) => hits.slice(0, size).reduce((s, hit) => s + ratings[hit.index], 0) / size,
        ),
        actual,
      ),
    );
  }, [later, vector, points, distance, ratings]);
  const bestK = KS[curve.indexOf(Math.min(...curve))];

  const tree = useMemo(() => kdTree(numeric), [numeric]);
  const search = kdNearest(tree, numeric, query.slice(0, 3), k);
  const timing = useMemo(() => {
    const queries = later.map((row) => vector(row).slice(0, 3));
    const started = performance.now();
    for (let repeat = 0; repeat < 5; repeat += 1) {
      for (const q of queries) nearest(numeric, q, k, euclidean);
    }
    const brute = ((performance.now() - started) / (5 * queries.length)) * 1000;
    const begun = performance.now();
    for (let repeat = 0; repeat < 5; repeat += 1) {
      for (const q of queries) kdNearest(tree, numeric, q, k);
    }
    const indexed = ((performance.now() - begun) / (5 * queries.length)) * 1000;
    return { brute, indexed };
  }, [later, vector, numeric, tree, k]);

  const space = useMemo(() => cloud(dimension), [dimension]);
  const centre = useMemo(() => Array(dimension).fill(0.5), [dimension]);
  const distances = useMemo(() => space.map((p) => euclidean(p, centre)), [space, centre]);
  const contrasts = useMemo(
    () => DIMENSIONS.map((d) => relativeContrast(cloud(d), Array(d).fill(0.5), euclidean)),
    [],
  );
  const contrast = relativeContrast(space, centre, euclidean);
  const edge = 0.1 ** (1 / dimension);

  const spaceTraces = useCallback(
    (colors) => {
      const chosen = new Set(found.map((hit) => hit.index));
      const others = numeric.filter((_, index) => !chosen.has(index));
      const close = found.map((hit) => numeric[hit.index]);
      const shape = neighbourhood(metric, query.slice(0, 3), radius, ranges);
      return [
        {
          ...shape,
          opacity: 0.18,
          color: colors.accent,
          colorscale: [
            [0, colors.accent],
            [1, colors.accent],
          ],
          showscale: false,
          hoverinfo: "skip",
          name: "Neighbourhood",
        },
        {
          type: "scatter3d",
          mode: "markers",
          name: "Training rows",
          x: others.map((p) => p[0]),
          y: others.map((p) => p[1]),
          z: others.map((p) => p[2]),
          marker: { size: 2.5, color: colors.muted, opacity: 0.6 },
        },
        {
          type: "scatter3d",
          mode: "markers",
          name: `${k} nearest`,
          x: close.map((p) => p[0]),
          y: close.map((p) => p[1]),
          z: close.map((p) => p[2]),
          marker: { size: 4.5, color: colors.accent },
        },
        {
          type: "scatter3d",
          mode: "markers",
          name: "Query",
          x: [query[0]],
          y: [query[1]],
          z: [query[2]],
          marker: { size: 8, color: colors.ink, symbol: "diamond" },
        },
      ];
    },
    [found, numeric, metric, query, radius, ranges, k],
  );
  const spaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User history" } },
        yaxis: { title: { text: "Movie history" } },
        zaxis: { title: { text: "Recency" } },
        aspectmode: "cube",
        camera: { eye: { x: 1.5, y: -1.6, z: 0.9 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );
  const curveTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Later-window RMSE",
        x: KS,
        y: curve,
        marker: { size: 4, color: colors.ink },
        line: { color: colors.ink },
      },
      {
        type: "scatter",
        mode: "markers",
        name: "This k",
        x: [k],
        y: [curve[k - 1]],
        marker: { size: 11, color: colors.accent },
      },
    ],
    [curve, k],
  );
  const histogramTraces = useCallback(
    (colors) => {
      const low = Math.min(...distances);
      const high = Math.max(...distances);
      const bins = histogram(distances, low, high, 30);
      return [
        {
          type: "scatter",
          mode: "lines",
          line: { shape: "hv", color: colors.accent },
          fill: "tozeroy",
          name: "Distances from the centre",
          x: [...bins.map((bin) => bin.from), high],
          y: [...bins.map((bin) => bin.count), 0],
        },
      ];
    },
    [distances],
  );
  const contrastTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "(max − min) / min",
        x: DIMENSIONS,
        y: contrasts,
        line: { color: colors.ink },
      },
      {
        type: "scatter",
        mode: "markers",
        name: "This dimension",
        x: [dimension],
        y: [contrast],
        marker: { size: 11, color: colors.accent },
      },
    ],
    [contrasts, dimension, contrast],
  );
  const curveLayout = useMemo(
    () => ({ xaxis: { title: { text: "k" } }, yaxis: { title: { text: "RMSE" } } }),
    [],
  );
  const histogramLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Euclidean distance" } },
      yaxis: { title: { text: "Points" } },
    }),
    [],
  );
  const contrastLayout = useMemo(
    () => ({
      xaxis: { type: "log", title: { text: "Dimension d (log scale)" } },
      yaxis: { type: "log", title: { text: "Relative contrast (log scale)" } },
    }),
    [],
  );

  return (
    <article className="lab">
      <h3>Model 6 · k-nearest-neighbour regression</h3>
      <p>
        kNN learns no equation. To predict a rating it finds the k training rows nearest the
        query and averages their ratings. The shape drawn around the query is the neighbourhood
        that holds exactly those k rows; its radius is the distance to the k-th one, so it grows
        with k. The distance itself is a choice: a ball for Euclidean, an octahedron for
        Manhattan, and Gower for mixed numeric and categorical features.
      </p>
      <Plot traces={spaceTraces} layout={spaceLayout} label="Neighbours in space" height={480} />
      <div className="controls">
        <Slider label="k" value={k} min={1} max={40} step={1} onChange={setK} format={String} />
        <Slider
          label="Query: later rating"
          value={pick}
          min={0}
          max={later.length - 1}
          step={1}
          onChange={setPick}
          format={(value) => `#${value + 1}`}
        />
        <label className="control">
          <span>Distance</span>
          <select value={metric} onChange={(event) => setMetric(event.target.value)}>
            {Object.entries(METRICS).map(([key, label]) => (
              <option key={key} value={key}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <dl className="readouts">
        <div>
          <dt>Prediction for this query</dt>
          <dd>
            Mean of {found.map((hit) => ratings[hit.index]).join(", ")} = {fixed(guess, 2)};
            the user actually gave {queryRow.rating}
          </dd>
        </div>
        <div>
          <dt>Distance to the k-th neighbour</dt>
          <dd>{fixed(radius)}, the radius of the drawn neighbourhood</dd>
        </div>
        <div>
          <dt>Later-window RMSE</dt>
          <dd>
            {fixed(curve[k - 1])} at k = {k}; lowest {fixed(Math.min(...curve))} at k = {bestK}.
            Small k is low bias and high variance; large k averages rows that are far away.
          </dd>
        </div>
        <div>
          <dt>Search cost, Euclidean</dt>
          <dd>
            Brute force measures all {numeric.length} rows ({fixed(timing.brute, 1)} ms per
            1,000 predictions); the k-d tree visited {search.visited} (
            {fixed(timing.indexed, 1)} ms per 1,000). Tree indexes lose that advantage as
            dimensions grow.
          </dd>
        </div>
      </dl>
      <Plot traces={curveTraces} layout={curveLayout} label="RMSE against k" height={300} />
      <h4>The curse of dimensionality, computed</h4>
      <div className="controls">
        <Slider
          label="Dimension d"
          value={dimension}
          min={1}
          max={100}
          step={1}
          onChange={setDimension}
          format={String}
        />
      </div>
      <div className="lab-grid">
        <Plot traces={histogramTraces} layout={histogramLayout} label="Distance histogram" />
        <Plot traces={contrastTraces} layout={contrastLayout} label="Relative contrast" />
      </div>
      <p className="muted">
        At d = {dimension}, 400 uniform points have relative contrast {fixed(contrast, 3)}, and a
        cube capturing 10% of them must span {fixed(edge * 100, 0)}% of every axis (0.1^(1/d)).
        As d grows the histogram narrows into a spike: every point sits at nearly the same
        distance, which is why the pipeline scales features before measuring distance and tests
        how many PCA components to keep rather than assuming. Seeded synthetic data:{" "}
        {train.length} training and {later.length} later ratings on five levels.
      </p>
      <Provenance
        data="Synthetic ratings, generated in this page: neighbourRatings({ seed: 71, n: 300 }); no real ratings"
        split="The first 240 rows train; the remaining 60 are the later window"
        preparation="Standardised with the training rows' means and spreads only"
        method="k nearest neighbours, averaging the neighbours' ratings"
      />
    </article>
  );
}

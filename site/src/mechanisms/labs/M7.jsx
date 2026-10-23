import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { outOfRange, rmse } from "../lib/metrics.js";
import { mulberry32 } from "../lib/random.js";
import { treeRatings } from "../lib/ratings.js";
import {
  atAlpha,
  grow,
  impurityImportance,
  permutationImportance,
  pruningPath,
  splitCurve,
  stepSurface,
  view,
} from "../lib/tree.js";
import { curve, oneStandardError, rollingFolds } from "../lib/tuning.js";

const TRAIN = 300;
const MIN_LEAF = 5;
const READABLE = 100;
const LABELS = { user: "user mean", movie: "movie mean", genre: "genre (binary)", age: "age band" };
const RANGES = { user: [2, 5.2], movie: [2, 5], genre: [0, 1], age: [0, 6] };
const AXES = { true: ["user", "movie"], false: ["age", "genre"] };

function featuresFor(withMeans) {
  return withMeans ? ["user", "movie", "genre", "age"] : ["age", "genre"];
}

export default function M7() {
  const [withMeans, setWithMeans] = useState(true);
  const [steps, setSteps] = useState(3);
  const [prune, setPrune] = useState(0);
  const [genreShown, setGenreShown] = useState(0);

  const features = featuresFor(withMeans);
  const rows = useMemo(() => treeRatings({ seed: 91, n: 360 }), []);
  const train = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const later = useMemo(() => rows.slice(TRAIN), [rows]);
  const tree = useMemo(() => grow(train, features, { minLeaf: MIN_LEAF }), [train, withMeans]);
  const path = useMemo(() => pruningPath(tree), [tree]);
  const pruning = prune > 0;
  const current = pruning
    ? view(tree, { collapsed: path[prune].collapsed })
    : view(tree, { steps });

  const points = useMemo(() => {
    const alphas = path
      .slice(1)
      .map((step, k) => Math.sqrt(step.alpha * (path[k].alpha || step.alpha / 10)));
    return curve([0, ...alphas], rollingFolds(TRAIN, 5), (fold, alpha) => {
      const foldTrain = fold.train.map((i) => train[i]);
      const foldTree = grow(foldTrain, features, { minLeaf: MIN_LEAF });
      const chosen = atAlpha(pruningPath(foldTree), alpha);
      const model = view(foldTree, { collapsed: chosen.collapsed });
      const valid = fold.valid.map((i) => train[i]);
      return rmse(valid.map(model.predict), valid.map((row) => row.rating));
    }).map((point) => ({ ...point, leaves: atAlpha(path, point.lambda).leaves }));
  }, [path, train, withMeans]);
  const { best, simplest } = useMemo(() => oneStandardError(points), [points]);

  const next = pruning ? null : tree.nodes.find((node) => node.order === steps);
  const node = next ?? tree.root;
  const nodeRows = node.indices.map((i) => train[i]);
  const nodeYs = nodeRows.map((row) => row.rating);
  const curves = features.map((feature) => ({
    feature,
    points: splitCurve(nodeRows, nodeYs, feature, MIN_LEAF),
  }));

  const trainGuesses = train.map(current.predict);
  const laterGuesses = later.map(current.predict);
  const genreSplits = current.internal.filter((n) => n.feature === "genre").length;
  const impurity = impurityImportance(
    tree,
    features,
    pruning ? Infinity : steps,
    pruning ? path[prune].collapsed : new Set(),
  );
  const permutation = permutationImportance(current.predict, later, features, mulberry32(5), 10);
  const largest = Math.max(...permutation, 1e-9);

  const [xKey, yKey] = AXES[withMeans];
  const thresholds = current.internal.map((n) => ({ feature: n.feature, value: n.threshold }));
  const surface = stepSurface(
    current.predict,
    xKey,
    yKey,
    RANGES[xKey],
    RANGES[yKey],
    thresholds,
    withMeans ? { genre: genreShown, age: 3 } : {},
  );

  const surfaceTraces = useCallback(
    (colors) => [
      {
        type: "surface",
        ...surface,
        colorscale: "Viridis",
        cmin: 1,
        cmax: 5,
        opacity: 0.9,
        showscale: false,
        name: "Tree prediction",
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Training ratings",
        x: train.map((row) => row[xKey]),
        y: train.map((row) => row[yKey]),
        z: train.map((row) => row.rating),
        marker: { size: 2.5, color: colors.muted, opacity: 0.6 },
      },
    ],
    [surface, train, xKey, yKey],
  );
  const surfaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: LABELS[xKey] } },
        yaxis: { title: { text: LABELS[yKey] } },
        zaxis: { title: { text: "Predicted rating" }, range: [1, 5] },
        camera: { eye: { x: 1.6, y: -1.6, z: 1.0 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [xKey, yKey],
  );
  const splitTraces = useCallback(
    (colors) => {
      const palette = [colors.accent, colors.ink, colors.muted, colors.line];
      return curves.map(({ feature, points: curvePoints }, k) => ({
        type: "scatter",
        mode: curvePoints.length > 1 ? "lines" : "markers",
        name: LABELS[feature],
        x: curvePoints.map((point) => {
          const [low, high] = RANGES[feature];
          return (point.threshold - low) / (high - low);
        }),
        y: curvePoints.map((point) => point.sse),
        line: { color: palette[k], width: 2.5 },
        marker: { size: 9, color: palette[k] },
      }));
    },
    [curves],
  );
  const pruneTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines+markers",
        name: "Validation RMSE ± 1 SE",
        x: points.map((point) => point.leaves),
        y: points.map((point) => point.error),
        error_y: { type: "data", array: points.map((point) => point.se), color: colors.line },
        line: { color: colors.ink, shape: "hv" },
      },
      ...[
        { at: best, name: "Lowest" },
        { at: simplest, name: "1-SE choice" },
      ].map(({ at, name }) => ({
        type: "scatter",
        mode: "markers",
        name,
        x: [at.leaves],
        y: [at.error],
        marker: { size: 11, color: colors.accent, symbol: name === "Lowest" ? "circle" : "star" },
      })),
      {
        type: "scatter",
        mode: "markers",
        name: "Shown now",
        x: [current.leaves.length],
        y: [rmse(laterGuesses, later.map((row) => row.rating))],
        marker: { size: 10, color: colors.muted, symbol: "diamond" },
      },
    ],
    [points, best, simplest, current, laterGuesses, later],
  );
  const splitLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Threshold, as a share of the feature's range" }, range: [0, 1] },
      yaxis: { title: { text: "SSE of the two sides" } },
    }),
    [],
  );
  const pruneLayout = useMemo(
    () => ({
      xaxis: { type: "log", title: { text: "Leaves (log scale)" } },
      yaxis: { title: { text: "RMSE, time-ordered folds" } },
      shapes: [
        {
          type: "line",
          x0: READABLE,
          x1: READABLE,
          yref: "paper",
          y0: 0,
          y1: 1,
          line: { dash: "dot", width: 1, color: "rgba(127,127,127,0.7)" },
        },
      ],
    }),
    [],
  );

  return (
    <article className="lab">
      <h3>Model 7 · Decision tree regression, with pruning</h3>
      <p>
        A regression tree cuts the feature space with one axis-aligned threshold at a time and
        predicts the mean training rating in each box, so its surface is flat steps with vertical
        walls, and a prediction can never leave [1, 5]. Each cut is chosen greedily: the feature
        and threshold that leave the least squared error on the two sides. Grown to the end it
        memorises; cost-complexity pruning removes the splits that buy the least.
      </p>
      <Plot traces={surfaceTraces} layout={surfaceLayout} label="Tree surface" height={480} />
      <div className="controls">
        <Slider
          label="Splits grown"
          value={pruning ? tree.splits : steps}
          min={0}
          max={tree.splits}
          step={1}
          onChange={(value) => {
            setPrune(0);
            setSteps(value);
          }}
          format={String}
        />
        <Slider
          label="Pruning step (weakest link)"
          value={prune}
          min={0}
          max={path.length - 1}
          step={1}
          onChange={setPrune}
          format={(value) =>
            `${value}: α = ${fixed(path[value].alpha, 3)}, ${path[value].leaves} leaves`
          }
        />
        <div className="button-row">
          <button
            type="button"
            className="action"
            onClick={() => {
              setPrune(0);
              setSteps(Math.min(steps + 1, tree.splits));
            }}
          >
            Grow one split
          </button>
          <button
            type="button"
            className="action quiet"
            onClick={() => {
              setPrune(0);
              setSteps(tree.splits);
            }}
          >
            Grow full tree
          </button>
          <button
            type="button"
            className="action quiet"
            onClick={() => setPrune(path.findIndex((step) => step.leaves === simplest.leaves))}
          >
            Prune to the 1-SE choice
          </button>
        </div>
        <label className="control check">
          <input
            type="checkbox"
            checked={withMeans}
            onChange={(event) => {
              setWithMeans(event.target.checked);
              setSteps(3);
              setPrune(0);
            }}
          />
          <span>Include the prior user and movie means</span>
        </label>
        {withMeans && (
          <label className="control check">
            <input
              type="checkbox"
              checked={genreShown === 1}
              onChange={(event) => setGenreShown(event.target.checked ? 1 : 0)}
            />
            <span>Show the surface for the genre</span>
          </label>
        )}
      </div>
      <dl className="readouts">
        <div>
          <dt>Tree shown</dt>
          <dd>
            {current.leaves.length} leaves from {current.internal.length} splits; {genreSplits} of
            them on the genre dummy
          </dd>
        </div>
        <div>
          <dt>RMSE, training and later window</dt>
          <dd>
            {fixed(rmse(trainGuesses, train.map((row) => row.rating)))} and{" "}
            {fixed(rmse(laterGuesses, later.map((row) => row.rating)))}
          </dd>
        </div>
        <div>
          <dt>Pruning chosen on time-ordered folds</dt>
          <dd>
            Lowest error at {best.leaves} leaves; the 1-SE rule picks {simplest.leaves} (α ={" "}
            {fixed(simplest.lambda, 3)}). The readable version must stay under {READABLE}.
          </dd>
        </div>
        <div>
          <dt>Predictions outside [1, 5]</dt>
          <dd>
            {outOfRange([...trainGuesses, ...laterGuesses])}: a leaf mean of ratings cannot leave
            the scale
          </dd>
        </div>
      </dl>
      <div className="lab-grid">
        <Plot traces={splitTraces} layout={splitLayout} label="Split search" />
        <Plot traces={pruneTraces} layout={pruneLayout} label="Pruning curve" />
      </div>
      <p className="muted">
        The split search shows, for the {next ? "next leaf to split" : "root"} ({node.n} rows),
        the squared error left by every threshold of every feature; the binary genre offers a
        single point, a continuous mean hundreds, which is why trees favour continuous features.
      </p>
      <h4>Importance: impurity against permutation on the later window</h4>
      <div className="bars">
        {features.map((feature, j) => (
          <div className="bar-row" key={feature}>
            <span>{LABELS[feature]}</span>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${impurity[j] * 100}%` }} />
            </div>
            <strong>{fixed(impurity[j] * 100, 0)}%</strong>
          </div>
        ))}
      </div>
      <div className="bars permutation">
        {features.map((feature, j) => (
          <div className="bar-row" key={feature}>
            <span>{LABELS[feature]}</span>
            <div className="bar-track">
              <div
                className="bar-fill quiet"
                style={{ width: `${(Math.max(permutation[j], 0) / largest) * 100}%` }}
              />
            </div>
            <strong>+{fixed(Math.max(permutation[j], 0), 3)}</strong>
          </div>
        ))}
      </div>
      <p className="muted">
        The first bars are impurity shares, from training splits; the second are the rise in
        later-window RMSE when that feature is shuffled. Untick the means and the tree must split
        on genre and age alone. Seeded synthetic data: {train.length} training and {later.length}{" "}
        later ratings on five levels.
      </p>
      <Provenance
        data="Synthetic ratings, generated in this page: treeRatings({ seed: 91, n: 360 }); no real ratings"
        split="The first 300 rows train; the remaining 60 are the later window"
        method="Regression tree grown best-first, pruned by cost-complexity"
      />
    </article>
  );
}

import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { adaBoostR2 } from "../lib/boosting.js";
import { blockSurface } from "../lib/ensemble.js";
import { fixed } from "../lib/format.js";
import { rmse } from "../lib/metrics.js";
import { forestRatings } from "../lib/ratings.js";

const FEATURES = ["user", "movie"];
const TRAIN = 200;
const ROUNDS = 30;
const RANGE = [-2.5, 2.5];
const OUTLIER = { user: 1.6, movie: 1.4, genre: 0, noise: 0, rating: 1 };
const LOSSES = ["linear", "square", "exponential"];

export default function M10() {
  const [shown, setShown] = useState(1);
  const [loss, setLoss] = useState("linear");
  const [rate, setRate] = useState(1);
  const [splits, setSplits] = useState(3);
  const [withOutlier, setWithOutlier] = useState(false);

  const rows = useMemo(() => forestRatings({ seed: 131, n: 260 }), []);
  const later = useMemo(() => rows.slice(TRAIN), [rows]);
  const clean = useMemo(() => rows.slice(0, TRAIN), [rows]);
  const options = { rounds: ROUNDS, loss, learningRate: rate, splits, seed: 7 };
  const fitClean = useMemo(
    () => adaBoostR2(clean, FEATURES, options),
    [clean, loss, rate, splits],
  );
  const fitNoisy = useMemo(
    () => adaBoostR2([...clean, OUTLIER], FEATURES, options),
    [clean, loss, rate, splits],
  );
  const fit = withOutlier ? fitNoisy : fitClean;
  const train = withOutlier ? [...clean, OUTLIER] : clean;
  const count = Math.max(1, Math.min(shown, fit.fitted.length));
  const step = fit.fitted[count - 1];
  const predict = useCallback((row) => fit.predict(row, count), [fit, count]);

  const surface = useMemo(
    () => blockSurface(predict, "user", "movie", RANGE, RANGE, 40, {}),
    [predict],
  );
  const curve = (f) =>
    f.fitted.map((_, k) =>
      rmse(
        later.map((row) => f.predict(row, k + 1)),
        later.map((row) => row.rating),
      ),
    );
  const curves = useMemo(
    () => ({ clean: curve(fitClean), noisy: curve(fitNoisy) }),
    [fitClean, fitNoisy, later],
  );
  const outlierIndex = train.length - 1;
  const share = withOutlier ? step.weights[outlierIndex] : 0;
  const rank = withOutlier
    ? step.weights.filter((w) => w > step.weights[outlierIndex]).length + 1
    : null;
  const atOutlier = fit.fitted.slice(0, count).map((s) => s.model.predict(OUTLIER));
  const weights = fit.fitted.slice(0, count).map((s) => s.weight);
  const weightedMean =
    atOutlier.reduce((s, v, k) => s + v * weights[k], 0) / weights.reduce((s, w) => s + w, 0);

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
        name: `Weighted median of ${count} trees`,
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Training ratings, sized by weight",
        x: train.map((row) => row.user),
        y: train.map((row) => row.movie),
        z: train.map((row) => row.rating),
        marker: {
          size: step.weights.map((w) => 2 + Math.min(18, w * train.length * 3)),
          color: train.map((_, i) =>
            withOutlier && i === outlierIndex ? colors.accent : colors.muted,
          ),
          opacity: 0.75,
        },
      },
    ],
    [surface, count, train, step, withOutlier, outlierIndex],
  );
  const curveTraces = useCallback(
    (colors) => [
      {
        type: "scatter",
        mode: "lines",
        name: "Clean training data",
        x: curves.clean.map((_, k) => k + 1),
        y: curves.clean,
        line: { color: colors.ink },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "With one outlier rating",
        x: curves.noisy.map((_, k) => k + 1),
        y: curves.noisy,
        line: { color: colors.accent, dash: "dash" },
      },
    ],
    [curves],
  );
  const surfaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User history" } },
        yaxis: { title: { text: "Movie history" } },
        zaxis: { title: { text: "Rating" }, range: [1, 5] },
        camera: { eye: { x: 1.6, y: -1.6, z: 1.0 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );
  const curveLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Rounds" } },
      yaxis: { title: { text: "Later-window RMSE" } },
    }),
    [],
  );

  return (
    <article className="lab">
      <h3>Model 10 · AdaBoost for regression (AdaBoost.R2)</h3>
      <p>
        Each round draws rows in proportion to their weights and fits a shallow tree. Every
        row's loss is its error over the round's largest error D, the weighted average loss L̄
        sets β = L̄ / (1 − L̄), and rows the tree predicted well are multiplied by β^(1 − L), so
        the poorly predicted ones gain share once weights are renormalised. The ensemble
        predicts the weighted median of its trees, each weighted by log(1 / β).
      </p>
      <Plot traces={surfaceTraces} layout={surfaceLayout} label="Median surface" height={460} />
      <div className="controls">
        <Slider
          label="Rounds shown"
          value={count}
          min={1}
          max={fit.fitted.length}
          step={1}
          onChange={setShown}
          format={String}
        />
        <label className="control">
          <span>Loss</span>
          <select value={loss} onChange={(event) => setLoss(event.target.value)}>
            {LOSSES.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>
        <Slider
          label="Learning rate"
          value={rate}
          min={0.1}
          max={1}
          step={0.1}
          onChange={setRate}
        />
        <Slider
          label="Splits per tree"
          value={splits}
          min={1}
          max={7}
          step={1}
          onChange={setSplits}
          format={String}
        />
        <label className="control check">
          <input
            type="checkbox"
            checked={withOutlier}
            onChange={(event) => setWithOutlier(event.target.checked)}
          />
          <span>Add one outlier: a 1-star rating where both histories are high</span>
        </label>
      </div>
      <dl className="readouts">
        <div>
          <dt>Round {count}</dt>
          <dd>
            D = {fixed(step.largest, 2)}, L̄ = {fixed(step.average)}, β = {fixed(step.beta)}, tree
            weight log(1/β) = {fixed(step.weight)}
            {fit.history.at(-1).stopped
              ? `; boosting stopped after round ${fit.fitted.length} because L̄ reached 0.5`
              : ""}
          </dd>
        </div>
        {withOutlier && (
          <div>
            <dt>The outlier</dt>
            <dd>
              It holds {fixed(share * 100, 1)}% of the weight, rank {rank} of {train.length}. At
              its location the weighted median predicts {fixed(fit.predict(OUTLIER, count), 2)}{" "}
              and a weighted mean would give {fixed(weightedMean, 2)}.
            </dd>
          </div>
        )}
        <div>
          <dt>Later-window RMSE after {count} rounds</dt>
          <dd>
            {fixed(curves.clean[Math.min(count, curves.clean.length) - 1])} clean,{" "}
            {fixed(curves.noisy[Math.min(count, curves.noisy.length) - 1])} with the outlier
          </dd>
        </div>
      </dl>
      <div className="lab-grid">
        <Plot traces={curveTraces} layout={curveLayout} label="Later error against rounds" />
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Round</th>
                <th scope="col">D</th>
                <th scope="col">L̄</th>
                <th scope="col">β</th>
                <th scope="col">log(1/β)</th>
              </tr>
            </thead>
            <tbody>
              {fit.fitted.slice(0, Math.min(count, 12)).map((s, k) => (
                <tr key={k}>
                  <th scope="row">{k + 1}</th>
                  <td>{fixed(s.largest, 2)}</td>
                  <td>{fixed(s.average)}</td>
                  <td>{fixed(s.beta)}</td>
                  <td>{fixed(s.weight)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <p className="muted">
        One huge error sets D, which shrinks every other row's loss toward zero, so L̄ and β fall
        and almost every other row loses weight at once; square and exponential losses amplify
        it. The weighted median keeps the outlier's pull on the final prediction limited. Seeded
        synthetic data: {clean.length} training and {later.length} later ratings on five levels.
      </p>
      <Provenance
        data="Synthetic ratings, generated in this page: forestRatings({ seed: 131, n: 260 }); no real ratings"
        split="The first 200 rows train; the remaining 60 are the later window"
        features="user, movie"
        method="AdaBoost.R2 on shallow trees, weighted median, boosting seed 7"
      />
    </article>
  );
}

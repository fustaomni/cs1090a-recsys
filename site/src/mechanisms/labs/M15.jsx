import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { steps } from "../lib/grid.js";
import { bucketOf } from "../lib/moe.js";
import { gateWeights } from "../lib/moefit.js";
import { EXPERT_NAMES, runMixture } from "../lib/moepipeline.js";

// The gate is fitted, not drawn: runMixture fits it on the validation window, and the surfaces
// below are that fitted gate's weights across the two training-history features.
const COLORS = ["#94a3b8", "#3b82f6", "#4ade80", "#f472b6"];
const USERS = steps(0, Math.log1p(40), 25);
const MOVIES = steps(0, Math.log1p(60), 25);
const percent = (value) => `${(100 * value).toFixed(1)}%`;
const three = (value) => value.toFixed(3);
const whole = (value) => value.toFixed(0);
const fromLog = (value) => Math.expm1(value);

export default function M15() {
  const [userCount, setUserCount] = useState(8);
  const [movieCount, setMovieCount] = useState(20);

  const run = useMemo(() => runMixture({ seed: 191 }), []);
  const weightsAt = useCallback(
    (userTotal, movieTotal) => gateWeights(run.theta, { userCount: userTotal, movieCount: movieTotal }),
    [run],
  );
  const weights = useMemo(
    () => weightsAt(userCount, movieCount),
    [weightsAt, userCount, movieCount],
  );
  const u = Math.log1p(userCount);
  const m = Math.log1p(movieCount);
  const bucket = bucketOf({ userCount, movieCount });
  const bestExpert = run.validation.experts.indexOf(Math.min(...run.validation.experts));

  const space = useCallback(
    (colors) => [
      ...EXPERT_NAMES.map((name, k) => ({
        type: "surface",
        name,
        x: USERS,
        y: MOVIES,
        z: MOVIES.map((my) => USERS.map((ux) => weightsAt(fromLog(ux), fromLog(my))[k])),
        showscale: false,
        opacity: 0.55,
        colorscale: [
          [0, COLORS[k]],
          [1, COLORS[k]],
        ],
        hovertemplate: `${name}<br>weight %{z:.2f}<extra></extra>`,
      })),
      {
        type: "scatter3d",
        mode: "markers",
        name: "This request",
        x: EXPERT_NAMES.map(() => u),
        y: EXPERT_NAMES.map(() => m),
        z: weights,
        marker: {
          size: 6,
          color: COLORS,
          line: { color: colors.ink, width: 1 },
        },
      },
    ],
    [weightsAt, u, m, weights],
  );

  const spaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User's training ratings, log(1 + n)" } },
        yaxis: { title: { text: "Movie's training ratings, log(1 + n)" } },
        zaxis: { title: { text: "Fitted gate weight" }, range: [0, 1] },
        camera: { eye: { x: 1.6, y: -1.6, z: 0.9 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  return (
    <article className="lab">
      <p>
        A mixture of experts lets several models answer at once and a gate decide how much to
        trust each. This gate is soft: a softmax turns each expert's score into a weight, every
        weight stays above zero and they sum to one. It reads two features, how many ratings the
        user and the movie had before the window being predicted, and it is fitted: its scores are
        learned on the validation window by gradient descent on the mixture's squared error, the
        experts held fixed. Move the request across the features and watch where the fitted gate
        sends its weight; then compare it, on the untouched test window, with each expert alone.
      </p>
      <Plot traces={space} layout={spaceLayout} label="The fitted gate's weight for each expert over the two histories" />
      <div className="controls">
        <Slider
          label="The user's ratings before the window"
          value={userCount}
          min={0}
          max={40}
          step={1}
          onChange={setUserCount}
          format={whole}
        />
        <Slider
          label="The movie's ratings before the window"
          value={movieCount}
          min={0}
          max={60}
          step={1}
          onChange={setMovieCount}
          format={whole}
        />
      </div>
      <dl className="readouts">
        <div>
          <dt>Bucket</dt>
          <dd>{bucket}</dd>
        </div>
        {EXPERT_NAMES.map((name, k) => (
          <div key={name} style={{ borderTop: `3px solid ${COLORS[k]}` }}>
            <dt>{name}</dt>
            <dd>
              weight {percent(weights[k])}; average on test {percent(run.utilisation[k])}
            </dd>
          </div>
        ))}
        <div>
          <dt>Validation RMSE, where the gate was fitted</dt>
          <dd>
            fitted mixture {three(run.validation.mixture)}, equal weights{" "}
            {three(run.validation.uniform)}, best single expert{" "}
            {three(run.validation.experts[bestExpert])} ({EXPERT_NAMES[bestExpert]})
          </dd>
        </div>
        <div>
          <dt>Test RMSE, scored once</dt>
          <dd>
            fitted mixture {three(run.tested.mixture)}, equal weights {three(run.tested.uniform)},
            the same single expert {three(run.tested.experts[bestExpert])}
          </dd>
        </div>
        <div>
          <dt>Ratings in each window</dt>
          <dd>
            train {run.windows.train}, validate {run.windows.validate}, test {run.windows.test}
          </dd>
        </div>
      </dl>
      <Provenance
        data="Synthetic ratings from users and movies that arrive over time, generated in this page: arrivingRatings({ seed: 191 }); no real ratings"
        split="Train before time 600 fits the experts; validate, 600 to 800, fits the gate; test, from 800, is scored once after the experts are refit on train and validate"
        features="The user's and the movie's rating counts strictly before the window being predicted, as log(1 + n)"
        method="Soft gate: a max-subtracted softmax over one linear score per expert, fitted from equal weights by 400 steps of gradient descent on validation squared error; experts held fixed"
      />
    </article>
  );
}

import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Slider from "../Slider.jsx";
import { fixed } from "../lib/format.js";
import { steps, surface } from "../lib/grid.js";
import { clip, outOfRange, rmse } from "../lib/metrics.js";
import { historyRatings } from "../lib/ratings.js";
import { fit, predict, vif } from "../lib/regression.js";
import { mean } from "../lib/stats.js";

const USER = steps(-2.5, 2.5, 41);
const COUNT = steps(0.2, 5, 41);

// The model's terms, built from centred or raw user mean and count (in hundreds of ratings).
function termsFor(centre, { square, both }) {
  const u = (row) => row.user - centre.user;
  const c = (row) => row.count - centre.count;
  const terms = [
    { key: "user", label: "user mean", value: u },
    { key: "count", label: "count", value: c },
  ];
  if (square) terms.push({ key: "square", label: "count²", value: (row) => c(row) ** 2 });
  if (both) terms.push({ key: "both", label: "user × count", value: (row) => u(row) * c(row) });
  return terms;
}

// With the curvature and interaction coefficients held where the reader set them, the
// intercept and linear terms are refitted by least squares to what remains.
function conditional(rows, ys, terms, held) {
  const free = terms.filter((term) => !(term.key in held));
  const rest = ys.map(
    (y, index) =>
      y -
      terms
        .filter((term) => term.key in held)
        .reduce((total, term) => total + held[term.key] * term.value(rows[index]), 0),
  );
  const coef = fit(rows, free, rest);
  const byKey = { intercept: coef[0] };
  free.forEach((term, index) => {
    byKey[term.key] = coef[index + 1];
  });
  return { ...byKey, ...held };
}

function shape(square, both) {
  if (both !== 0) {
    const angle = (0.5 * Math.atan(both / (0 - square)) * 180) / Math.PI;
    const turned = Number.isFinite(angle) ? Math.abs(angle) : 45;
    const discriminant = fixed(both * both, 4);
    return (
      `a saddle: the discriminant b₅² − 4·0·b₃ = ${discriminant} is positive, and the ` +
      `interaction turns its axes by ${fixed(turned, 1)}°`
    );
  }
  if (square !== 0) return "a parabolic cylinder: curved along count only, axes unrotated";
  return "a plane: no curvature and no interaction";
}

export default function M3() {
  const [centring, setCentring] = useState(true);
  const [withSquare, setWithSquare] = useState(true);
  const [withBoth, setWithBoth] = useState(true);
  const [b3, setB3] = useState(0);
  const [b5, setB5] = useState(0);

  const train = useMemo(() => historyRatings({ seed: 21, n: 400 }), []);
  const valid = useMemo(() => historyRatings({ seed: 22, n: 400 }), []);
  const ys = useMemo(() => train.map((row) => row.rating), [train]);
  const centre = useMemo(
    () => ({
      user: mean(train.map((row) => row.user)),
      count: mean(train.map((row) => row.count)),
    }),
    [train],
  );
  const options = { square: withSquare, both: withBoth };
  const active = centring ? centre : { user: 0, count: 0 };
  const terms = termsFor(active, options);
  const centredTerms = termsFor(centre, options);
  const rawTerms = termsFor({ user: 0, count: 0 }, options);

  const held = {};
  if (withSquare) held.square = b3;
  if (withBoth) held.both = b5;
  const coef = conditional(train, ys, terms, held);
  const vector = [coef.intercept, ...terms.map((term) => coef[term.key])];
  const at = (row) => predict(vector, terms, row);

  const olsCentred = fit(train, centredTerms, ys);
  const olsRaw = fit(train, rawTerms, ys);
  const vifCentred = vif(train, centredTerms);
  const vifRaw = vif(train, rawTerms);
  const olsHeld = () => {
    const keys = centredTerms.map((term) => term.key);
    if (withSquare) setB3(olsCentred[keys.indexOf("square") + 1]);
    if (withBoth) setB5(olsCentred[keys.indexOf("both") + 1]);
  };

  const grid = surface(USER, COUNT, (user, count) => at({ user, count }));
  const gridValues = grid.flat();
  const trainPredictions = train.map(at);
  const validPredictions = valid.map(at);
  const validActual = valid.map((row) => row.rating);

  const traces = useCallback(
    (colors) => [
      {
        type: "surface",
        x: USER,
        y: COUNT,
        z: grid,
        colorscale: "Viridis",
        opacity: 0.9,
        showscale: false,
        name: "Fitted surface, unclipped",
      },
      ...[1, 5].map((level) => ({
        type: "surface",
        x: [USER[0], USER[USER.length - 1]],
        y: [COUNT[0], COUNT[COUNT.length - 1]],
        z: [
          [level, level],
          [level, level],
        ],
        opacity: 0.18,
        showscale: false,
        colorscale: [
          [0, colors.accent],
          [1, colors.accent],
        ],
        hoverinfo: "skip",
        name: `Rating ${level}`,
      })),
      {
        type: "scatter3d",
        mode: "markers",
        name: "Training ratings",
        x: train.map((row) => row.user),
        y: train.map((row) => row.count),
        z: ys,
        marker: { size: 2.5, color: colors.muted },
      },
    ],
    [grid, train, ys],
  );

  const layout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User mean (standardised)" } },
        yaxis: { title: { text: "Count, hundreds of ratings" } },
        zaxis: { title: { text: "Predicted rating" } },
        camera: { eye: { x: 1.6, y: -1.6, z: 0.9 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  const names = centredTerms.map((term) => term.label);
  return (
    <article className="lab">
      <h3>Model 3 · Polynomial and interaction terms</h3>
      <p>
        A squared count term lets the surface bend, and a user × count term lets the effect of a
        user's mean depend on how much they have rated. The surface is drawn unclipped: the
        shaded planes at 1 and 5 mark where a prediction leaves the possible ratings.
      </p>
      <Plot traces={traces} layout={layout} label="Fitted rating surface" height={500} />
      <div className="controls">
        <label className="control check">
          <input
            type="checkbox"
            checked={withSquare}
            onChange={(event) => setWithSquare(event.target.checked)}
          />
          <span>Count² term</span>
        </label>
        <label className="control check">
          <input
            type="checkbox"
            checked={withBoth}
            onChange={(event) => setWithBoth(event.target.checked)}
          />
          <span>User × count term</span>
        </label>
        <label className="control check">
          <input
            type="checkbox"
            checked={centring}
            onChange={(event) => setCentring(event.target.checked)}
          />
          <span>Centre the predictors</span>
        </label>
        {withSquare && (
          <Slider
            label="Curvature b₃, count²"
            value={b3}
            min={-0.4}
            max={0.4}
            step={0.005}
            onChange={setB3}
            format={(value) => value.toFixed(3)}
          />
        )}
        {withBoth && (
          <Slider
            label="Interaction b₅, user × count"
            value={b5}
            min={-0.4}
            max={0.4}
            step={0.005}
            onChange={setB5}
            format={(value) => value.toFixed(3)}
          />
        )}
        <button type="button" className="action" onClick={olsHeld}>
          Fit by least squares
        </button>
      </div>
      <dl className="readouts">
        <div>
          <dt>Shape of the surface</dt>
          <dd>It is {shape(withSquare ? b3 : 0, withBoth ? b5 : 0)}.</dd>
        </div>
        <div>
          <dt>RMSE, training and validation</dt>
          <dd>
            {fixed(rmse(trainPredictions, ys))} and {fixed(rmse(validPredictions, validActual))}{" "}
            unclipped; {fixed(rmse(validPredictions.map(clip), validActual))} on validation once
            clipped to [1, 5]
          </dd>
        </div>
        <div>
          <dt>Outside [1, 5]</dt>
          <dd>
            {outOfRange(trainPredictions)} of {train.length} training predictions and{" "}
            {fixed((100 * outOfRange(gridValues)) / gridValues.length, 1)}% of the drawn surface
          </dd>
        </div>
      </dl>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">Least squares coefficient</th>
              <th scope="col">Centred</th>
              <th scope="col">Raw</th>
              <th scope="col">VIF centred</th>
              <th scope="col">VIF raw</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th scope="row">intercept</th>
              <td>{fixed(olsCentred[0])}</td>
              <td>{fixed(olsRaw[0])}</td>
              <td>—</td>
              <td>—</td>
            </tr>
            {names.map((name, index) => (
              <tr key={name}>
                <th scope="row">{name}</th>
                <td>{fixed(olsCentred[index + 1])}</td>
                <td>{fixed(olsRaw[index + 1])}</td>
                <td>{fixed(vifCentred[index], 2)}</td>
                <td>{fixed(vifRaw[index], 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="muted">
        Centring changes what the lower coefficients mean and how inflated their variance is, not
        the predictions: the count² and interaction coefficients are identical in both columns,
        and the surface does not move when you toggle it. A high VIF that centring removes was
        created by the scaling; one that survives is real collinearity, the problem ridge
        regression addresses next. Seeded synthetic data, {train.length} training and{" "}
        {valid.length} validation ratings on five levels.
      </p>
    </article>
  );
}

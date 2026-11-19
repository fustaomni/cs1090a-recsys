import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { steps } from "../lib/grid.js";
import { bucketOf, gateFeatures, softmax, usable } from "../lib/moe.js";
import { timedRatings } from "../lib/ratings.js";

// An illustrative gate, not a fitted one: each expert's score rises where its kind of evidence
// is rich, so the soft weights move across the two training-history features.
const EXPERTS = [
  { name: "Shared bias", color: "#94a3b8", score: () => 0 },
  { name: "Movie mean", color: "#3b82f6", score: (u, m) => 1.2 * m - 0.6 * u },
  { name: "Regularised linear", color: "#4ade80", score: (u, m) => 0.8 * u + 0.8 * m - 1.5 },
  { name: "kNN", color: "#f472b6", score: (u, m) => 1.4 * u + 1.0 * m - 3 },
];
const BOUNDARY = 700;
const USERS = steps(0, Math.log1p(40), 25);
const MOVIES = steps(0, Math.log1p(60), 25);
const weightsAt = (u, m) => softmax(EXPERTS.map((expert) => expert.score(u, m)));
const percent = (value) => `${(100 * value).toFixed(1)}%`;
const whole = (value) => value.toFixed(0);

export default function M15() {
  const [userCount, setUserCount] = useState(8);
  const [movieCount, setMovieCount] = useState(20);

  const rows = useMemo(() => timedRatings({ seed: 151 }), []);
  const { before, blocked } = useMemo(() => usable(rows, BOUNDARY), [rows]);
  const buckets = useMemo(() => {
    const counts = { warm: 0, "new user": 0, "new movie": 0, "both new": 0 };
    blocked.forEach((row) => {
      counts[bucketOf(gateFeatures(before, row, BOUNDARY))] += 1;
    });
    return counts;
  }, [before, blocked]);

  const u = Math.log1p(userCount);
  const m = Math.log1p(movieCount);
  const weights = useMemo(() => weightsAt(u, m), [u, m]);
  const bucket = bucketOf({ userCount, movieCount });

  const space = useCallback(
    (colors) => [
      ...EXPERTS.map((expert, k) => ({
        type: "surface",
        name: expert.name,
        x: USERS,
        y: MOVIES,
        z: MOVIES.map((my) => USERS.map((ux) => weightsAt(ux, my)[k])),
        showscale: false,
        opacity: 0.55,
        colorscale: [
          [0, expert.color],
          [1, expert.color],
        ],
        hovertemplate: `${expert.name}<br>weight %{z:.2f}<extra></extra>`,
      })),
      {
        type: "scatter3d",
        mode: "markers",
        name: "This request",
        x: EXPERTS.map(() => u),
        y: EXPERTS.map(() => m),
        z: weights,
        marker: {
          size: 6,
          color: EXPERTS.map((expert) => expert.color),
          line: { color: colors.ink, width: 1 },
        },
      },
    ],
    [u, m, weights],
  );

  const spaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User's training ratings, log(1 + n)" } },
        yaxis: { title: { text: "Movie's training ratings, log(1 + n)" } },
        zaxis: { title: { text: "Gate weight" }, range: [0, 1] },
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
        weight stays above zero and they sum to one, so the shared bias expert always contributes.
        The gate reads only two features, how many ratings the user and the movie had before the
        training cut. Move the request across them and watch the weight pass from the movie mean,
        which needs only the movie, to the neighbour model, which needs both histories.
      </p>
      <Plot traces={space} layout={spaceLayout} label="Each expert's gate weight over the two histories" />
      <div className="controls">
        <Slider
          label="The user's ratings before the cut"
          value={userCount}
          min={0}
          max={40}
          step={1}
          onChange={setUserCount}
          format={whole}
        />
        <Slider
          label="The movie's ratings before the cut"
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
        {EXPERTS.map((expert, k) => (
          <div key={expert.name} style={{ borderTop: `3px solid ${expert.color}` }}>
            <dt>{expert.name}</dt>
            <dd>{percent(weights[k])}</dd>
          </div>
        ))}
        <div>
          <dt>Test ratings by bucket</dt>
          <dd>
            {Object.entries(buckets)
              .map(([name, count]) => `${name} ${count}`)
              .join(", ")}{" "}
            of {blocked.length}
          </dd>
        </div>
      </dl>
      <Provenance
        data="Synthetic ratings, generated in this page: timedRatings({ seed: 151 }); no real ratings"
        split={`Ratings before time ${BOUNDARY} train the gate's features; ratings at or after it are the test window`}
        features="The user's and the movie's rating counts strictly before the cut, as log(1 + n)"
        method="Soft gate: a max-subtracted softmax over illustrative linear scores, one per expert; not fitted"
      />
    </article>
  );
}

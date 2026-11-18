import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { gateFeatures, usable } from "../lib/moe.js";
import { timedRatings } from "../lib/ratings.js";

const SAFE = "#4ade80";
const BLOCKED = "#f87171";
const whole = (value) => value.toFixed(0);

export default function T14() {
  const [boundary, setBoundary] = useState(500);
  const [leak, setLeak] = useState(false);

  const rows = useMemo(() => timedRatings({ seed: 181 }), []);
  const users = useMemo(() => Math.max(...rows.map((row) => row.user)) + 1, [rows]);
  const { before, blocked } = useMemo(() => usable(rows, boundary), [rows, boundary]);
  const sameSecond = blocked.filter((row) => row.time === boundary).length;
  const target = blocked[0];

  const verdict = useMemo(() => {
    if (!target) return "No rating sits at or after this request time.";
    try {
      const found = gateFeatures(leak ? rows : before, target, boundary);
      return `Allowed: the gate reads ${found.userCount} of user ${target.user}'s ratings and ${found.movieCount} of movie ${target.movie}'s, all before the wall.`;
    } catch (error) {
      return `Refused: ${error.message}.`;
    }
  }, [leak, rows, before, target, boundary]);

  const space = useCallback(
    (colors) => [
      {
        type: "scatter3d",
        mode: "markers",
        name: "Usable clues, strictly before",
        x: before.map((row) => row.time),
        y: before.map((row) => row.user),
        z: before.map((row) => row.rating),
        marker: { size: 2.5, color: SAFE, opacity: 0.8 },
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "Blocked, at or after",
        x: blocked.map((row) => row.time),
        y: blocked.map((row) => row.user),
        z: blocked.map((row) => row.rating),
        marker: { size: 2.5, color: BLOCKED, opacity: 0.8 },
      },
      {
        type: "mesh3d",
        name: "Request time",
        x: [boundary, boundary, boundary, boundary],
        y: [0, users, users, 0],
        z: [0.5, 0.5, 5.5, 5.5],
        i: [0, 0],
        j: [1, 2],
        k: [2, 3],
        color: colors.accent,
        opacity: 0.25,
        hoverinfo: "name",
      },
    ],
    [before, blocked, boundary, users],
  );

  const spaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "Time" }, range: [0, 1000] },
        yaxis: { title: { text: "User" } },
        zaxis: { title: { text: "Rating" }, range: [0.5, 5.5] },
        camera: { eye: { x: 1.4, y: -1.8, z: 0.8 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  return (
    <article className="lab">
      <p>
        A feature may only use what was known when the prediction was asked for. The wall is the
        request time: ratings strictly before it are clues the gate may count, and ratings at or
        after it, including one in the same second, are blocked. Slide the wall and the clues
        change; tick the leak box and the gate is handed every rating, which the guard refuses
        rather than silently counting the future.
      </p>
      <Plot traces={space} layout={spaceLayout} label="Ratings by time, user and rating, split by the request time" />
      <div className="controls">
        <Slider label="Request time" value={boundary} min={1} max={999} step={1} onChange={setBoundary} format={whole} />
        <label className="toggle">
          <input type="checkbox" checked={leak} onChange={(event) => setLeak(event.target.checked)} />{" "}
          Hand the gate every rating, the future included
        </label>
      </div>
      <dl className="readouts">
        <div style={{ borderTop: `3px solid ${SAFE}` }}>
          <dt>Usable clues</dt>
          <dd>{before.length}</dd>
        </div>
        <div style={{ borderTop: `3px solid ${BLOCKED}` }}>
          <dt>Blocked</dt>
          <dd>
            {blocked.length}, of which {sameSecond} fall in the request's own second
          </dd>
        </div>
        <div>
          <dt>The guard</dt>
          <dd>{verdict}</dd>
        </div>
      </dl>
      <Provenance
        data="Synthetic ratings, generated in this page: timedRatings({ seed: 181 }); no real ratings"
        split="A rating is usable only when its time is strictly before the request time"
        features="The user's and the movie's rating counts, read by gateFeatures in lib/moe.js"
        method="Strictly-before boundary, the same rule as scripts/moe.py's gate_features, which raises on any later rating"
      />
    </article>
  );
}

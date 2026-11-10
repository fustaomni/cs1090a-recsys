import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import {
  SIGNFLIP,
  blockData,
  exactNull,
  exactP,
  pFloor,
  randomSigns,
  rowLevelP,
  skewness,
  statistic,
  userMeans,
} from "../lib/signflip.js";

const BLOCKS = ["#3b82f6", "#4ade80", "#facc15", "#c4b5fd", "#f472b6", "#fb923c"];
const whole = (value) => value.toFixed(0);

export default function T12() {
  const [users, setUsers] = useState(5);
  const [draw, setDraw] = useState(0);

  const blocks = useMemo(() => blockData({ seed: 171, users }), [users]);
  const means = useMemo(() => userMeans(blocks), [blocks]);
  const signs = useMemo(
    () => (draw === 0 ? means.map(() => 1) : randomSigns(users, 1000 + draw)),
    [draw, users, means],
  );
  const observed = statistic(means, means.map(() => 1));
  const flipped = statistic(means, signs);
  const nullValues = useMemo(() => exactNull(means), [means]);
  const p = useMemo(() => exactP(means), [means]);
  const rowP = useMemo(() => rowLevelP(blocks), [blocks]);

  const space = useCallback(
    (colors) => {
      const traces = [
        {
          type: "surface",
          name: "Δ = 0",
          x: [1, users],
          y: [1, SIGNFLIP.ratings],
          z: [
            [0, 0],
            [0, 0],
          ],
          showscale: false,
          opacity: 0.2,
          colorscale: [
            [0, colors.muted],
            [1, colors.muted],
          ],
          hoverinfo: "skip",
        },
      ];
      blocks.forEach((block, index) => {
        traces.push({
          type: "scatter3d",
          mode: "markers",
          name: `User ${block.user}${signs[index] < 0 ? ", flipped" : ""}`,
          x: block.deltas.map(() => block.user),
          y: block.deltas.map((_, rating) => rating + 1),
          z: block.deltas.map((value) => value * signs[index]),
          marker: { size: 4, color: BLOCKS[index % BLOCKS.length], line: { color: colors.ink, width: 0.5 } },
        });
      });
      return traces;
    },
    [blocks, signs, users],
  );

  const spaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "User (block)" }, dtick: 1 },
        yaxis: { title: { text: "Rating index" }, dtick: 2 },
        zaxis: { title: { text: "Δ error (model A − model B)" }, range: [-1, 1] },
        camera: { eye: { x: 1.5, y: -1.5, z: 0.8 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  const histogram = useCallback(
    (colors) => [
      {
        type: "histogram",
        name: `All ${nullValues.length} sign patterns`,
        x: nullValues,
        nbinsx: 40,
        marker: { color: colors.muted },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "Observed",
        x: [observed, observed],
        y: [0, nullValues.length / 8],
        line: { color: colors.accent, width: 3 },
      },
      {
        type: "scatter",
        mode: "lines",
        name: "This draw",
        x: [flipped, flipped],
        y: [0, nullValues.length / 8],
        line: { color: colors.ink, width: 2, dash: "dash" },
      },
    ],
    [nullValues, observed, flipped],
  );

  const histogramLayout = useMemo(
    () => ({
      xaxis: { title: { text: "Mean of the per-user differences" } },
      yaxis: { title: { text: "Sign patterns" } },
      bargap: 0.05,
    }),
    [],
  );

  return (
    <article className="lab">
      <p>
        Each user contributes a block of paired differences in error, model A minus model B. If the
        two models were equally good, each user's block would be as likely to sit above zero as
        below it, so flipping whole blocks builds the distribution the observed difference is
        judged against. Flipping single ratings instead would pretend each user's ratings were
        independent.
      </p>
      <div className="lab-grid">
        <Plot traces={space} layout={spaceLayout} label="Each user's block of differences" />
        <Plot traces={histogram} layout={histogramLayout} label="The exact sign-flip distribution" />
      </div>
      <div className="controls">
        <Slider label="Users in the test" value={users} min={5} max={12} step={1} onChange={setUsers} format={whole} />
        <button type="button" className="action" onClick={() => setDraw((value) => value + 1)}>
          Execute user-level sign-flip
        </button>
        <button type="button" className="action" onClick={() => setDraw(0)}>
          Reset to baseline
        </button>
      </div>
      <p className="muted">User block states:</p>
      <ul className="chips">
        {blocks.map((block, index) => (
          <li key={block.user}>
            U{block.user}: {signs[index] < 0 ? "flipped (+Z)" : "original (−Z)"}
          </li>
        ))}
      </ul>
      <p className="status-line">
        {draw === 0
          ? `Baseline: the mean difference over ${users} users is ${observed.toFixed(3)}; below zero means model A errs less. Execute a sign-flip to see one draw from the null.`
          : `Draw ${draw}: with these signs the mean difference is ${flipped.toFixed(3)}, against ${observed.toFixed(3)} observed.`}
      </p>
      <dl className="readouts">
        <div>
          <dt>Exact two-sided p</dt>
          <dd>
            {p.toFixed(4)}, the share of all {nullValues.length} sign patterns at least as extreme
            as observed
          </dd>
        </div>
        <div>
          <dt>Smallest possible p</dt>
          <dd>
            2 / 2^{users} = {pFloor(users).toFixed(4)}
            {pFloor(users) > 0.05 ? "; with this few users no result can reach 0.05" : ""}
          </dd>
        </div>
        <div>
          <dt>Ignoring the clustering</dt>
          <dd>
            flipping each rating on its own gives p ≈ {rowP.toFixed(4)}, overstating the certainty
          </dd>
        </div>
        <div>
          <dt>Symmetry the test assumes</dt>
          <dd>skewness of the per-user differences {skewness(means).toFixed(2)}; near zero is what the test needs</dd>
        </div>
      </dl>
      <Provenance
        data="Synthetic paired differences, generated in this page: blockData({ seed: 171 }); no real ratings"
        method="Exact sign-flip permutation test over user blocks, two-sided; a row-level flip by Monte Carlo for contrast"
      />
    </article>
  );
}

import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { steps } from "../lib/grid.js";
import { softmaxT, topK } from "../lib/moefit.js";
import { reweigh, runMixture } from "../lib/moepipeline.js";

const GRID = steps(-6, 6, 41);
const percent = (value) => `${(100 * value).toFixed(1)}%`;
const oneDecimal = (value) => value.toFixed(1);
const twoDecimals = (value) => value.toFixed(2);
const three = (value) => value.toFixed(3);

export default function T13() {
  const [a, setA] = useState(4.2);
  const [b, setB] = useState(1.1);
  const [c, setC] = useState(-2.5);
  const [temperature, setTemperature] = useState(1);
  const [sparse, setSparse] = useState(false);

  const gate = useCallback(
    (scores) => {
      const weights = softmaxT(scores, temperature);
      return sparse ? topK(weights, 2) : weights;
    },
    [temperature, sparse],
  );
  const weights = useMemo(() => gate([a, b, c]), [gate, a, b, c]);
  const top = Math.max(a, b, c);

  // The same knobs on Model 15's fitted gate: no refit, only the temperature and the cut.
  const run = useMemo(() => runMixture({ seed: 191 }), []);
  const fitted = useMemo(
    () => reweigh(run, { temperature, k: sparse ? 2 : null }),
    [run, temperature, sparse],
  );

  const space = useCallback(
    (colors) => [
      {
        type: "surface",
        name: "Expert A's weight",
        x: GRID,
        y: GRID,
        z: GRID.map((sb) => GRID.map((sa) => gate([sa, sb, c])[0])),
        showscale: false,
        opacity: 0.85,
        colorscale: [
          [0, colors.surface],
          [1, colors.accent],
        ],
        hovertemplate: "A %{x:.1f}, B %{y:.1f}<br>A's weight %{z:.2f}<extra></extra>",
      },
      {
        type: "scatter3d",
        mode: "lines",
        name: "Drop line",
        x: [a, a],
        y: [b, b],
        z: [0, weights[0]],
        line: { color: colors.ink, width: 4 },
        hoverinfo: "skip",
      },
      {
        type: "scatter3d",
        mode: "markers",
        name: "The chosen scores",
        x: [a],
        y: [b],
        z: [weights[0]],
        marker: { size: 6, color: colors.accent, line: { color: colors.ink, width: 1 } },
      },
    ],
    [gate, a, b, c, weights],
  );

  const spaceLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "Expert A's raw score" }, range: [-6, 6] },
        yaxis: { title: { text: "Expert B's raw score" }, range: [-6, 6] },
        zaxis: { title: { text: "Expert A's weight" }, range: [0, 1] },
        camera: { eye: { x: 1.6, y: -1.6, z: 0.9 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  return (
    <article className="lab">
      <p>
        The gate gives each expert a raw score, then a softmax turns the scores into weights: each
        is e to its score over the temperature, divided by the sum for all experts. Only
        differences between scores matter, so the page subtracts the largest score first; e to a
        large score would overflow, while e to a score minus the largest never exceeds one. A low
        temperature sharpens the gate toward its top expert and a high one flattens it toward
        equal weights; keeping only the top two experts and renormalising them turns the soft gate
        into a sparse one. The surface shows Expert A's weight as A's and B's scores move with
        C's held at its slider, and the last readout applies the same two knobs to Model 15's
        fitted gate on its test window.
      </p>
      <Plot traces={space} layout={spaceLayout} label="Expert A's softmax weight over two raw scores" />
      <div className="controls">
        <Slider label="Expert A's score" value={a} min={-6} max={6} step={0.1} onChange={setA} format={oneDecimal} />
        <Slider label="Expert B's score" value={b} min={-6} max={6} step={0.1} onChange={setB} format={oneDecimal} />
        <Slider label="Expert C's score" value={c} min={-6} max={6} step={0.1} onChange={setC} format={oneDecimal} />
        <Slider
          label="Temperature"
          value={temperature}
          min={0.1}
          max={5}
          step={0.05}
          onChange={setTemperature}
          format={twoDecimals}
        />
        <label className="toggle">
          <input type="checkbox" checked={sparse} onChange={(event) => setSparse(event.target.checked)} />{" "}
          Keep only the top two experts
        </label>
      </div>
      <dl className="readouts">
        <div>
          <dt>Weights</dt>
          <dd>
            With scores {oneDecimal(a)}, {oneDecimal(b)} and {oneDecimal(c)} at temperature{" "}
            {twoDecimals(temperature)}, the gate gives Expert A {percent(weights[0])}, Expert B{" "}
            {percent(weights[1])} and Expert C {percent(weights[2])}.
          </dd>
        </div>
        <div>
          <dt>Largest score subtracted</dt>
          <dd>{oneDecimal(top)}, so the biggest term computed is e to 0, which is 1</dd>
        </div>
        <div>
          <dt>Model 15's fitted gate, read this way</dt>
          <dd>
            test RMSE {three(fitted.tested.mixture)} against {three(run.tested.mixture)} at
            temperature 1 with every expert
          </dd>
        </div>
      </dl>
      <Provenance
        data="Three raw scores chosen with the sliders; the last readout reuses Model 15's fitted gate on arrivingRatings({ seed: 191 })"
        split="For the last readout, Model 15's windows: the gate fitted on validate, 600 to 800, and read on test, from 800"
        method="Softmax of the scores divided by the temperature, the largest subtracted first as in scripts/moe.py's gate_weights; with the top two kept, the other weights are zeroed and the two renormalised to sum to one"
      />
    </article>
  );
}

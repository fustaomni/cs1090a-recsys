import { useCallback, useMemo, useState } from "react";
import Plot from "../Plot.jsx";
import Provenance from "../Provenance.jsx";
import Slider from "../Slider.jsx";
import { audit, conformalHalfWidth, coverageData } from "../lib/coverage.js";

const PILLAR = "#3b82f6";
const COVERED = "#4ade80";
const MISSED = "#ef4444";
const percent = (value) => `${(100 * value).toFixed(0)}%`;

export default function T11() {
  const [level, setLevel] = useState(0.95);
  const [audited, setAudited] = useState(false);

  const { calibration, test } = useMemo(() => coverageData({ seed: 151 }), []);
  const half = useMemo(() => conformalHalfWidth(calibration, level), [calibration, level]);
  const result = useMemo(() => audit(test, half, level), [test, half, level]);
  const covered = result.rows.filter((row) => row.covered).length;

  const pillars = useCallback(
    (colors) => {
      const link = { x: [], y: [], z: [] };
      for (const row of result.rows) {
        link.x.push(row.id, row.id, null);
        link.y.push(row.center, row.center, null);
        link.z.push(row.lower, row.upper, null);
      }
      const traces = [
        {
          type: "scatter3d",
          mode: "lines+markers",
          name: `${percent(level)} interval bounds`,
          x: link.x,
          y: link.y,
          z: link.z,
          line: { color: PILLAR, width: 5 },
          marker: { size: 2, color: PILLAR },
          hoverinfo: "skip",
        },
      ];
      if (audited) {
        for (const [name, keep, color] of [
          ["True rating, covered", true, COVERED],
          ["True rating, missed", false, MISSED],
        ]) {
          const subset = result.rows.filter((row) => row.covered === keep);
          traces.push({
            type: "scatter3d",
            mode: "markers",
            name,
            x: subset.map((row) => row.id),
            y: subset.map((row) => row.center),
            z: subset.map((row) => row.rating),
            marker: { size: 5, color, line: { color: colors.ink, width: 0.5 } },
          });
        }
      }
      return traces;
    },
    [result, level, audited],
  );

  const pillarsLayout = useMemo(
    () => ({
      scene: {
        xaxis: { title: { text: "Test rating ID" } },
        yaxis: { title: { text: "Predicted centre" }, range: [1, 5] },
        zaxis: { title: { text: "Rating" }, range: [0, 6] },
        camera: { eye: { x: 1.5, y: -1.5, z: 0.8 } },
      },
      margin: { l: 0, r: 0, t: 0, b: 0 },
    }),
    [],
  );

  const gap = result.coverage - level;

  return (
    <article className="lab">
      <h3>Technique 11 · Prediction-interval coverage audit</h3>
      <p>
        Each test rating gets an interval around its prediction, sized on a separate calibration
        set so that, in the long run, the stated share of ratings falls inside. The audit checks
        that promise against the ratings themselves: how many land inside, how far the misses fall,
        and whether the promise holds for every kind of user or only on average.
      </p>
      <Plot traces={pillars} layout={pillarsLayout} label="Interval pillars against the true ratings" />
      <div className="controls">
        <Slider
          label="Nominal coverage level"
          value={level}
          min={0.8}
          max={0.99}
          step={0.01}
          onChange={setLevel}
          format={percent}
        />
        <button type="button" className="action" onClick={() => setAudited(true)}>
          Run coverage audit (empirical test)
        </button>
        <span className="badge">
          Status: {audited ? `audited, ${covered} / ${result.rows.length} covered` : "pending audit"}
        </span>
      </div>
      <p className="status-line">
        {audited
          ? `Audited: ${percent(result.coverage)} of the ${result.rows.length} test ratings fall inside their ${percent(level)} intervals, a gap of ${(100 * gap).toFixed(0)} points from the promise.`
          : `Initial state: ${percent(level)} intervals drawn for ${result.rows.length} test ratings. Run the coverage audit to check them against the ratings.`}
      </p>
      {audited && (
        <dl className="readouts">
          <div>
            <dt>Empirical against nominal</dt>
            <dd>
              {percent(result.coverage)} covered against {percent(level)} promised; {covered} of{" "}
              {result.rows.length}
            </dd>
          </div>
          {result.groups.map((group) => (
            <div key={group.group}>
              <dt>{group.group} raters</dt>
              <dd>
                {percent(group.coverage)} covered, n = {group.n}
              </dd>
            </div>
          ))}
          <div>
            <dt>Width and interval score</dt>
            <dd>
              every interval {result.width.toFixed(2)} wide; mean interval score{" "}
              {result.score.toFixed(2)}, the width plus 2/α times each miss
            </dd>
          </div>
        </dl>
      )}
      <p className="muted">
        Split conformal promises coverage on average over all ratings, not for each group: one
        width for everyone can over-cover steady raters and under-cover noisy ones, which only a
        group-level audit reveals.
      </p>
      <Provenance
        data="Synthetic ratings, generated in this page: coverageData({ seed: 151 }); no real ratings"
        method="Split-conformal intervals from 200 calibration residuals; coverage, width and interval score on 30 test ratings"
      />
    </article>
  );
}

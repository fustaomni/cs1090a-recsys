import { useEffect, useRef, useState } from "react";

// One Plotly figure, themed from the page's own colours. Plotly's 3D bundle is a separate
// chunk loaded on first use, so the page itself stays small.
const loadPlotly = () => import("plotly.js-gl3d-dist-min").then((module) => module.default);
const FONT = '"Inter", system-ui, -apple-system, "Segoe UI", sans-serif';
const DARK = "(prefers-color-scheme: dark)";

export function palette() {
  const style = getComputedStyle(document.documentElement);
  const read = (name) => style.getPropertyValue(name).trim();
  return {
    ink: read("--ink"),
    muted: read("--muted"),
    line: read("--line"),
    surface: read("--surface"),
    accent: read("--accent"),
  };
}

function useScheme() {
  const [dark, setDark] = useState(() => window.matchMedia(DARK).matches);
  useEffect(() => {
    const query = window.matchMedia(DARK);
    const change = (event) => setDark(event.matches);
    query.addEventListener("change", change);
    return () => query.removeEventListener("change", change);
  }, []);
  return dark;
}

function themed(layout, colors) {
  const axis = (extra = {}) => ({
    color: colors.muted,
    gridcolor: colors.line,
    zerolinecolor: colors.line,
    ...extra,
  });
  const result = {
    ...layout,
    autosize: true,
    paper_bgcolor: "rgba(0,0,0,0)",
    plot_bgcolor: "rgba(0,0,0,0)",
    font: { family: FONT, color: colors.ink },
    margin: { l: 55, r: 20, t: 20, b: 50, ...layout.margin },
    legend: { orientation: "h", y: -0.2, ...layout.legend },
  };
  if (layout.scene) {
    const { xaxis, yaxis, zaxis } = layout.scene;
    result.scene = { ...layout.scene, xaxis: axis(xaxis), yaxis: axis(yaxis), zaxis: axis(zaxis) };
  }
  if (layout.xaxis) result.xaxis = axis(layout.xaxis);
  if (layout.yaxis) result.yaxis = axis(layout.yaxis);
  return result;
}

// traces is a function of the palette, so marks follow the light or dark theme.
export default function Plot({ traces, layout, label, height = 420 }) {
  const node = useRef(null);
  const dark = useScheme();

  useEffect(() => {
    let live = true;
    loadPlotly().then((Plotly) => {
      if (!live || !node.current) return;
      const colors = palette();
      Plotly.react(node.current, traces(colors), themed(layout, colors), {
        responsive: true,
        displaylogo: false,
        showSendToCloud: false,
      });
    });
    return () => {
      live = false;
    };
  }, [traces, layout, dark]);

  useEffect(() => {
    const element = node.current;
    return () => {
      loadPlotly().then((Plotly) => Plotly.purge(element));
    };
  }, []);

  return <div ref={node} className="plot" style={{ height }} role="img" aria-label={label} />;
}

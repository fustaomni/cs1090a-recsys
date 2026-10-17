import { Component, Suspense, lazy, useState } from "react";
import project from "../data/project.json";
import registry from "../data/mechanisms.json";

// Every model and technique has a lab; each built one is its own chunk, loaded when opened.
const LABS = {
  M1: lazy(() => import("./labs/M1.jsx")),
  M2: lazy(() => import("./labs/M2.jsx")),
  M3: lazy(() => import("./labs/M3.jsx")),
  M4: lazy(() => import("./labs/M4.jsx")),
  M5: lazy(() => import("./labs/M5.jsx")),
};

class LabBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { failed: false };
  }

  static getDerivedStateFromError() {
    return { failed: true };
  }

  render() {
    if (this.state.failed) {
      return <p className="in-progress">This lab could not load. Reload the page to retry.</p>;
    }
    return this.props.children;
  }
}

function name(lab) {
  const source = lab.kind === "model" ? project.models : project.techniques;
  return source.find((entry) => entry.id === lab.ref).name;
}

export default function Mechanisms() {
  const built = registry.labs.filter((lab) => lab.status === "built");
  const [open, setOpen] = useState(built[0]?.id);
  const Lab = LABS[open];
  return (
    <section id="mechanisms" className="section">
      <h2>Interactive mechanisms</h2>
      <p className="lede">
        One lab per model and technique, each computed live from seeded data: every number,
        curve and surface on screen is the mathematics running, not a drawing of it.
      </p>
      <ul className="lab-index">
        {registry.labs.map((lab) => (
          <li key={lab.id}>
            {lab.status === "built" ? (
              <button
                type="button"
                className={lab.id === open ? "lab-tab open" : "lab-tab"}
                aria-pressed={lab.id === open}
                onClick={() => setOpen(lab.id)}
              >
                <span className="lab-id">{lab.id}</span> {name(lab)}
              </button>
            ) : (
              <span className="lab-tab pending">
                <span className="lab-id">{lab.id}</span> {name(lab)}
                <span className="badge planned">Building</span>
              </span>
            )}
          </li>
        ))}
      </ul>
      {Lab && (
        <LabBoundary key={open}>
          <Suspense fallback={<p className="in-progress">Loading the lab…</p>}>
            <Lab />
          </Suspense>
        </LabBoundary>
      )}
    </section>
  );
}

import data from "./data/project.json";

const SECTIONS = [
  { id: "overview", label: "Overview", ready: true },
  { id: "scope", label: "Scope", ready: false },
  { id: "phases", label: "Phases", ready: false },
  { id: "deploys", label: "Models & techniques", ready: false },
  { id: "mechanisms", label: "Interactive mechanisms", ready: false },
  { id: "results", label: "Results", ready: false },
];

function InProgress({ id, label }) {
  return (
    <section id={id} className="section">
      <h2>{label}</h2>
      <p className="in-progress">Building in progress…</p>
    </section>
  );
}

function Overview() {
  const { overview, milestones, join } = data;
  return (
    <section id="overview" className="section">
      <p className="eyebrow">MovieLens 1M · offline · leakage-safe</p>
      <h1>{data.title}</h1>
      <p className="lede">{overview.question}</p>
      <p>{overview.summary}</p>
      <ul className="stats">
        {overview.stats.map((stat) => (
          <li key={stat.label}>
            <strong>{stat.value}</strong>
            <span>{stat.label}</span>
          </li>
        ))}
      </ul>
      <h2>Roadmap to December</h2>
      <ol className="timeline">
        {milestones.map((milestone) => (
          <li key={milestone.id}>
            <p className="when">{milestone.due}</p>
            <h3>{milestone.name}</h3>
            <p>{milestone.focus}</p>
            <p className="phases">Phases {milestone.phases}</p>
          </li>
        ))}
      </ol>
      <div className="join">
        <h2>{join.title}</h2>
        <p>{join.need}</p>
        <ul>
          {join.roles.map((role) => (
            <li key={role.name}>
              <strong>{role.name}</strong> — {role.owns}
            </li>
          ))}
        </ul>
        <p>
          Contact <a href={`mailto:${data.contact}`}>{data.author}</a>.
        </p>
      </div>
    </section>
  );
}

export default function App() {
  return (
    <>
      <header className="bar">
        <a href="#overview" className="brand">
          Rating recommender
        </a>
        <nav>
          {SECTIONS.map((section) => (
            <a key={section.id} href={`#${section.id}`}>
              {section.label}
            </a>
          ))}
        </nav>
      </header>
      <main>
        {SECTIONS.map((section) =>
          section.id === "overview" ? (
            <Overview key={section.id} />
          ) : (
            <InProgress key={section.id} id={section.id} label={section.label} />
          ),
        )}
      </main>
      <footer className="foot">{data.author} · updated at every milestone</footer>
    </>
  );
}

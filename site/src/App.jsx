import data from "./data/project.json";

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "scope", label: "Scope" },
  { id: "phases", label: "Phases" },
  { id: "deploys", label: "Models & techniques" },
  { id: "mechanisms", label: "Interactive mechanisms" },
  { id: "results", label: "Results" },
];

const STATUS_LABEL = { done: "Done", current: "In progress", planned: "Planned" };

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

function Scope() {
  const { scope } = data;
  return (
    <section id="scope" className="section">
      <h2>Scope, after review</h2>
      <p className="lede">{scope.principle}</p>
      <div className="two-col">
        <div className="panel">
          <h3>Removed by the reviewer</h3>
          <dl>
            {scope.removed.map((entry) => (
              <div key={entry.item}>
                <dt>{entry.item}</dt>
                <dd>{entry.why}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="panel">
          <h3>Retained and reframed</h3>
          <dl>
            {scope.retained.map((entry) => (
              <div key={entry.item}>
                <dt>{entry.item}</dt>
                <dd>{entry.form}</dd>
              </div>
            ))}
          </dl>
        </div>
      </div>
    </section>
  );
}

function Phases() {
  const byId = Object.fromEntries(data.phases.map((phase) => [phase.id, phase]));
  const groups = data.milestones.filter((milestone) => milestone.phase_ids.length > 0);
  const opened = groups[0]?.phase_ids[0];
  return (
    <section id="phases" className="section">
      <h2>The phases</h2>
      <p className="status-line">
        <span className="badge current">Status</span> {data.status}
      </p>
      {groups.map((milestone) => (
        <div key={milestone.id} className="milestone-group">
          <h3>
            {milestone.id} · {milestone.name} <span className="when">{milestone.due}</span>
          </h3>
          <ol className="phase-list">
            {milestone.phase_ids.map((id) => (
              <li key={id}>
                <details open={id === opened}>
                  <summary>
                    <span className="phase-id">Phase {id}</span>
                    <span className="phase-title">{byId[id].title}</span>
                    <span className={`badge ${milestone.status}`}>
                      {STATUS_LABEL[milestone.status]}
                    </span>
                  </summary>
                  <ul>
                    {byId[id].points.map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </details>
              </li>
            ))}
          </ol>
        </div>
      ))}
    </section>
  );
}

function Deploys() {
  const groups = [];
  for (const model of data.models) {
    const last = groups[groups.length - 1];
    if (last && last.phase === model.phase) {
      last.models.push(model);
    } else {
      groups.push({ phase: model.phase, models: [model] });
    }
  }
  return (
    <section id="deploys" className="section">
      <h2>What the project deploys</h2>
      <h3>Twelve predictive models, simplest first</h3>
      <ol className="ladder">
        {groups.map((group) => (
          <li key={group.phase}>
            <p className="eyebrow">
              Phase {group.phase} · {data.families[group.phase]}
            </p>
            <ul className="rungs">
              {group.models.map((model) => (
                <li key={model.id}>
                  <span className="rung-id">{model.id}</span>
                  {model.name}
                </li>
              ))}
            </ul>
          </li>
        ))}
      </ol>
      <div className="opponent">
        <h3>The opponent every model must beat</h3>
        <ul className="chips">
          {data.baselines.map((baseline) => (
            <li key={baseline.name}>{baseline.name}</li>
          ))}
        </ul>
        <p>{data.baseline_note}</p>
      </div>
      <h3>Ten supporting techniques</h3>
      <ul className="cards">
        {data.techniques.map((technique) => (
          <li key={technique.id}>
            <p className="eyebrow">Technique {technique.id}</p>
            <h4>{technique.name}</h4>
            <p className="muted">{technique.where}</p>
          </li>
        ))}
      </ul>
      <h3>Deliberately excluded</h3>
      <ul>
        {data.excluded.map((entry) => (
          <li key={entry}>{entry}</li>
        ))}
      </ul>
    </section>
  );
}

const READY = { overview: Overview, scope: Scope, phases: Phases, deploys: Deploys };

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
        {SECTIONS.map((section) => {
          const Ready = READY[section.id];
          return Ready ? (
            <Ready key={section.id} />
          ) : (
            <InProgress key={section.id} id={section.id} label={section.label} />
          );
        })}
      </main>
      <footer className="foot">{data.author} · updated at every milestone</footer>
    </>
  );
}

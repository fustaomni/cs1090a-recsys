// site/src/bind.js
// Every figure the site's text names, read from its source and never typed in (A.245).
import data from "./data/project.json";
import movielens from "./data/movielens.json";
import results from "./data/results.json";

const NUMBER = new Intl.NumberFormat("en-US");
const MONTH = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" });

// A.350: one value the notebook recorded for Milestone 2, read from Results by its pointer.
function recorded(pointer, sections) {
  const section = sections.find((entry) => entry.milestone === "M2");
  const entry = section?.entries.find((item) => item.pointer === pointer);
  if (!entry) {
    throw new Error(`no Milestone 2 value at ${pointer}`);
  }
  return entry.value;
}

// The cut quantiles: the share of every recorded rating before each cut, to two places.
function cutQuantiles(sections) {
  const [train, validation, test] = ["train", "validation", "test"].map((window) =>
    recorded(`/split_audit/windows/${window}/ratings`, sections),
  );
  const total = train + validation + test;
  const share = (count) => Math.round((count / total) * 100) / 100;
  return {
    ms2ValidationQuantile: share(train),
    ms2TestQuantile: share(train + validation),
  };
}

export function sources(project = data, summary = movielens, recordedResults = results) {
  const { structure } = summary;
  return {
    ...cutQuantiles(recordedResults.milestones),
    ratings: structure.ratings,
    users: structure.users,
    moviesRated: structure.moviesRated,
    moviesListed: structure.moviesListed,
    models: project.models.length,
    techniques: project.techniques.length,
    milestones: project.milestones.length,
    firstMonth: MONTH.format(new Date(structure.firstDay)),
    lastMonth: MONTH.format(new Date(structure.lastDay)),
    firstYear: structure.firstDay.slice(0, 4),
    lastYear: structure.lastDay.slice(0, 4),
  };
}

// A numbered token, {model:N} or {technique:N}, renders that entry as "Model N · name" (A.258).
const NUMBERED = { model: ["Model", "models"], technique: ["Technique", "techniques"] };

export function bind(text, values = sources(), project = data) {
  return text.replace(/\{(\w+)(?::(\d+))?\}/g, (token, name, number) => {
    if (number !== undefined) {
      const [label, key] = NUMBERED[name] ?? [];
      const entry = key && project[key].find((item) => item.id === Number(number));
      if (!entry) {
        throw new Error(`unbound ${token} in: ${text}`);
      }
      return `${label} ${entry.id} · ${entry.name}`;
    }
    if (!(name in values)) {
      throw new Error(`unbound ${token} in: ${text}`);
    }
    const value = values[name];
    return typeof value === "number" ? NUMBER.format(value) : value;
  });
}

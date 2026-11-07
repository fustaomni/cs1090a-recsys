// site/src/bind.js
// Every figure the site's text names, read from its source and never typed in (A.245).
import data from "./data/project.json";
import movielens from "./data/movielens.json";

const NUMBER = new Intl.NumberFormat("en-US");
const MONTH = new Intl.DateTimeFormat("en-US", { month: "long", year: "numeric", timeZone: "UTC" });

export function sources(project = data, summary = movielens) {
  const { structure } = summary;
  return {
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

export function bind(text, values = sources()) {
  return text.replace(/\{(\w+)\}/g, (token, name) => {
    if (!(name in values)) {
      throw new Error(`unbound ${token} in: ${text}`);
    }
    const value = values[name];
    return typeof value === "number" ? NUMBER.format(value) : value;
  });
}

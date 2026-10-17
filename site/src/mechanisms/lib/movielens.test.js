import { describe, expect, it } from "vitest";
import data from "../../data/movielens.json";
import { cutIndex, summarise } from "./movielens.js";

const DAY = 86400;
const ratings = Array.from({ length: 20 }, (_, i) => {
  const user = (i % 4) + 1;
  const movie = (i % 3) + 1;
  return `${user}::${movie}::${(i % 5) + 1}::${1000 + i * DAY}`;
}).join("\n");
const movies = [
  "1::A (2000)::Comedy|Drama",
  "2::B (2000)::Drama",
  "3::C (2000)::Film-Noir",
].join("\n");
const users = [
  "1::F::1::10::48067",
  "2::M::56::16::70072",
  "3::M::25::15::55117",
  "4::F::45::7::02460",
].join("\n");
const small = summarise({ ratings, movies, users, nonUtf8MovieLines: 0 });

describe("summarising the MovieLens files", () => {
  it("counts the structure", () => {
    expect(small.structure.ratings).toBe(20);
    expect(small.structure.moviesListed).toBe(3);
    expect(small.structure.duplicatePairs).toBe(8);
    expect(small.timeline.cumulative.at(-1)).toBe(20);
  });

  it("cuts at a quantile and moves past a shared timestamp", () => {
    expect(cutIndex([1, 2, 3, 4, 5], 0.8)).toBe(4);
    expect(cutIndex([1, 2, 2, 2, 5], 0.4)).toBe(4);
  });

  it("splits into windows that partition the rows", () => {
    const split = small.splits["0.8/0.9"];
    const { train, valid, test } = split.windows;
    expect(train.rows + valid.rows + test.rows).toBe(20);
    expect(split.training.counts.reduce((s, n) => s + n, 0)).toBe(train.rows);
  });
});

describe("the committed MovieLens 1M summary", () => {
  it("matches the dataset's published facts", () => {
    expect(data.structure).toMatchObject({
      ratings: 1000209,
      users: 6040,
      moviesListed: 3883,
      moviesRated: 3706,
      fewestRatingsPerUser: 20,
      unknownUsers: 0,
      unknownMovies: 0,
    });
  });

  it("puts the cutoffs in time order and partitions every split", () => {
    const days = [0.8, 0.85, 0.9, 0.95].map((q) => data.quantiles[q].day);
    for (let k = 1; k < days.length; k += 1) expect(days[k]).toBeGreaterThanOrEqual(days[k - 1]);
    for (const split of Object.values(data.splits)) {
      const { train, valid, test } = split.windows;
      expect(train.rows + valid.rows + test.rows).toBe(1000209);
    }
  });
});

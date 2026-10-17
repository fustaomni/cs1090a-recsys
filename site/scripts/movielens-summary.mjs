// Writes site/src/data/movielens.json from the official MovieLens 1M files:
//   node site/scripts/movielens-summary.mjs <folder with ratings.dat, movies.dat, users.dat>
// The files are Latin-1; the movie list's lines that are not valid UTF-8 are counted from the
// raw bytes before decoding.

import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { summarise } from "../src/mechanisms/lib/movielens.js";

const folder = process.argv[2];
if (!folder) {
  process.stderr.write("usage: node site/scripts/movielens-summary.mjs <ml-1m folder>\n");
  process.exit(2);
}
const read = (name) => readFileSync(join(folder, name));
const strict = new TextDecoder("utf-8", { fatal: true });
const latin1 = (bytes) => new TextDecoder("latin1").decode(bytes);
const movieBytes = read("movies.dat");
let nonUtf8MovieLines = 0;
let start = 0;
for (let i = 0; i <= movieBytes.length; i += 1) {
  if (i === movieBytes.length || movieBytes[i] === 0x0a) {
    try {
      strict.decode(movieBytes.subarray(start, i));
    } catch {
      nonUtf8MovieLines += 1;
    }
    start = i + 1;
  }
}
const summary = summarise({
  ratings: latin1(read("ratings.dat")),
  movies: latin1(movieBytes),
  users: latin1(read("users.dat")),
  nonUtf8MovieLines,
});
const source = {
  dataset: "MovieLens 1M, GroupLens Research (files.grouplens.org/datasets/movielens/ml-1m.zip)",
  files: ["ratings.dat", "movies.dat", "users.dat"],
  script: "site/scripts/movielens-summary.mjs",
};
const target = new URL("../src/data/movielens.json", import.meta.url);
writeFileSync(target, `${JSON.stringify({ source, ...summary })}\n`);

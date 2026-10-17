// MovieLens 1M summaries for the EDA, missingness and imbalance labs, computed from the three
// official files (ratings.dat, movies.dat, users.dat; "::" separated, Latin-1). The time
// cutoffs are quantiles of the rating timestamps, moved to a timestamp boundary. Structure is
// summarised over all rows; every view of rating values uses the training window only.

const DAY = 86400;
const LEVELS = [1, 2, 3, 4, 5];
export const QUANTILES = [0.8, 0.85, 0.9, 0.95];
export const SPLITS = [
  [0.8, 0.9],
  [0.85, 0.95],
];
const AGES = {
  1: "under 18",
  18: "18–24",
  25: "25–34",
  35: "35–44",
  45: "45–49",
  50: "50–55",
  56: "56+",
};

function lines(text) {
  return text.split(/\r?\n/).filter((line) => line.length > 0).map((line) => line.split("::"));
}

function isoDay(seconds) {
  return new Date(seconds * 1000).toISOString().slice(0, 10);
}

function counted(values) {
  const map = new Map();
  for (const value of values) map.set(value, (map.get(value) ?? 0) + 1);
  return map;
}

// The first index at or after the q quantile, moved past any rating sharing its timestamp.
export function cutIndex(times, q) {
  let index = Math.min(times.length, Math.ceil(q * times.length));
  while (index > 0 && index < times.length && times[index] === times[index - 1]) index += 1;
  return index;
}

// Ratings per entity, in doubling bins: 1, 2–3, 4–7, 8–15, ...
function tail(counts) {
  const bins = [];
  for (const count of counts) {
    const bin = Math.floor(Math.log2(count));
    bins[bin] = (bins[bin] ?? 0) + 1;
  }
  return Array.from(bins, (n, bin) => ({
    from: 2 ** bin,
    to: 2 ** (bin + 1) - 1,
    count: n ?? 0,
  }));
}

function levelSummary(values) {
  const counts = LEVELS.map((level) => values.filter((v) => v === level).length);
  const n = values.length;
  const mean = values.reduce((s, v) => s + v, 0) / n;
  const m2 = values.reduce((s, v) => s + (v - mean) ** 2, 0) / n;
  const m3 = values.reduce((s, v) => s + (v - mean) ** 3, 0) / n;
  return { counts, mean, skew: m3 / m2 ** 1.5 };
}

function windowSummary(rows) {
  return {
    rows: rows.length,
    users: new Set(rows.map((r) => r.user)).size,
    movies: new Set(rows.map((r) => r.movie)).size,
  };
}

export function summarise({ ratings, movies, users, nonUtf8MovieLines }) {
  const rows = lines(ratings)
    .map(([user, movie, rating, time]) => ({
      user: Number(user),
      movie: Number(movie),
      rating: Number(rating),
      time: Number(time),
    }))
    .sort((a, b) => a.time - b.time);
  const movieRows = lines(movies).map(([id, title, genres]) => ({
    id: Number(id),
    title,
    genres: genres.split("|"),
  }));
  const userRows = lines(users).map(([id, gender, age, occupation, zip]) => ({
    id: Number(id),
    gender,
    age: Number(age),
    occupation: Number(occupation),
    zip,
  }));
  const movieById = new Map(movieRows.map((m) => [m.id, m]));
  const userById = new Map(userRows.map((u) => [u.id, u]));
  const genres = [...new Set(movieRows.flatMap((m) => m.genres))].sort();
  const times = rows.map((r) => r.time);
  const first = times[0];
  const span = Math.floor((times.at(-1) - first) / DAY);

  const daily = new Array(span + 1).fill(0);
  for (const time of times) daily[Math.floor((time - first) / DAY)] += 1;
  let running = 0;
  const cumulative = daily.map((count) => (running += count));

  const pairs = counted(rows.map((r) => `${r.user}:${r.movie}`));
  const perUser = counted(rows.map((r) => r.user));
  const structure = {
    ratings: rows.length,
    users: userRows.length,
    usersRating: perUser.size,
    moviesListed: movieRows.length,
    moviesRated: new Set(rows.map((r) => r.movie)).size,
    firstDay: isoDay(first),
    lastDay: isoDay(times.at(-1)),
    nonUtf8MovieLines,
    duplicatePairs: [...pairs.values()].filter((n) => n > 1).length,
    unknownUsers: rows.filter((r) => !userById.has(r.user)).length,
    unknownMovies: rows.filter((r) => !movieById.has(r.movie)).length,
    fewestRatingsPerUser: Math.min(...perUser.values()),
  };

  const quantiles = Object.fromEntries(
    QUANTILES.map((q) => {
      const index = cutIndex(times, q);
      const day = Math.floor((times[index] - first) / DAY);
      return [q, { index, day, date: isoDay(times[index]) }];
    }),
  );

  const splits = Object.fromEntries(
    SPLITS.map(([qVal, qTest]) => {
      const a = quantiles[qVal].index;
      const b = quantiles[qTest].index;
      const train = rows.slice(0, a);
      const valid = rows.slice(a, b);
      const test = rows.slice(b);
      const trainUsers = counted(train.map((r) => r.user));
      const trainMovies = new Set(train.map((r) => r.movie));
      const testUsers = new Set(test.map((r) => r.user));
      const monthly = counted(train.map((r) => isoDay(r.time).slice(0, 7)));
      const genreRatings = genres.map(
        (g) => train.filter((r) => movieById.get(r.movie).genres.includes(g)).length,
      );
      const ratedMovies = [...trainMovies].map((id) => movieById.get(id));
      const together = genres.map((g) =>
        genres.map(
          (h) => ratedMovies.filter((m) => m.genres.includes(g) && m.genres.includes(h)).length,
        ),
      );
      const people = [...trainUsers.keys()].map((id) => userById.get(id));
      return [
        `${qVal}/${qTest}`,
        {
          windows: {
            train: windowSummary(train),
            valid: windowSummary(valid),
            test: windowSummary(test),
          },
          testUsersUnseen: [...testUsers].filter((u) => !trainUsers.has(u)).length,
          testUsers: testUsers.size,
          testUsersUnderFive: [...testUsers].filter((u) => (trainUsers.get(u) ?? 0) < 5).length,
          testMoviesUnseen: new Set(
            test.filter((r) => !trainMovies.has(r.movie)).map((r) => r.movie),
          ).size,
          validMean: valid.reduce((s, r) => s + r.rating, 0) / valid.length,
          training: {
            ...levelSummary(train.map((r) => r.rating)),
            monthly: [...monthly.entries()].map(([month, count]) => ({ month, count })),
            userTail: tail(trainUsers.values()),
            movieTail: tail(counted(train.map((r) => r.movie)).values()),
            genres: genres.map((genre, k) => ({
              genre,
              ratings: genreRatings[k],
              movies: together[k][k],
            })),
            together,
            gender: Object.fromEntries(counted(people.map((p) => p.gender))),
            age: Object.fromEntries(
              [...counted(people.map((p) => p.age))].map(([age, n]) => [AGES[age] ?? age, n]),
            ),
            occupations: counted(people.map((p) => p.occupation)).size,
            zipRegions: Object.fromEntries(counted(people.map((p) => p.zip.slice(0, 1)))),
          },
        },
      ];
    }),
  );

  return {
    contract: "movielens-summary/v1",
    structure,
    // A rating-value statistic over all rows, kept only to show what fitting on them leaks.
    allRowsMean: rows.reduce((s, r) => s + r.rating, 0) / rows.length,
    timeline: { first: isoDay(first), cumulative },
    quantiles,
    splits,
    genres,
  };
}

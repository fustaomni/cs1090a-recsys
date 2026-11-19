// site/src/mechanisms/lib/moepipeline.js
// A.359: the experts and the fitted mixture end to end. RED stub: every export exists, so each
// proof fails on its own assertion, never on an unresolved import.
const pending = (name) => () => {
  throw new Error(`${name} is not implemented yet (A.359)`);
};

export const EXPERT_NAMES = [];
export const fitExperts = pending('fitExperts');
export const runMixture = pending('runMixture');
export const reweigh = pending('reweigh');

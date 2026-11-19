// site/src/mechanisms/lib/moefit.js
// A.359: a fitted gate on a three-window time split. RED stub: every export exists, so each
// proof fails on its own assertion, never on an unresolved import.
const pending = (name) => () => {
  throw new Error(`${name} is not implemented yet (A.359)`);
};

export const arrivingRatings = pending('arrivingRatings');
export const threeWindows = pending('threeWindows');
export const windowFeatures = pending('windowFeatures');
export const softmaxT = pending('softmaxT');
export const topK = pending('topK');
export const fitGate = pending('fitGate');
export const mixturePredict = pending('mixturePredict');
export const utilisation = pending('utilisation');

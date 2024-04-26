import makeRegression from "../utils/makeRegression";
import lstsq from "../utils/lstsq";

const HARMONICS = 2;

function setup() {
  return {
    input: ["SR3", "SR4", "dataMask"],
    output: {
      bands: HARMONICS * 2 + 1,
      sampleType: "FLOAT32",
    },
    mosaicking: "ORBIT",
  };
}

function preProcessScenes(collections) {
  // This creates the X (predictors) only once for the entire collection
  // This fullX will be filtered in evaluate pixel depending on clouds
  var dates = collections.scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates, HARMONICS);
  return collections;
}

function evaluatePixel(samples) {
  if (samples.length == 0) {
    return [NaN, NaN, NaN];
  }
  let y = [];
  let X = [];
  const N = HARMONICS * 2 + 1;
  for (let i = 0; i < N; i++) X[i] = [];
  for (let i = 0; i < samples.length; i++) {
    const sample = samples[i];
    if (sample.dataMask == 1) {
      y.push((sample.SR4 - sample.SR3) / (sample.SR4 + sample.SR3));
      for (let j = 0; j < N; j++) {
        X[j].push(fullX[i][j]);
      }
    }
  }
  if (y.length == 0) {
    return [NaN, NaN, NaN];
  }
  const beta = lstsq(X, y);
  return beta;
}

// DISCARD FROM HERE

exports.setup = setup;
exports.preProcessScenes = preProcessScenes;
exports.evaluatePixel = evaluatePixel;

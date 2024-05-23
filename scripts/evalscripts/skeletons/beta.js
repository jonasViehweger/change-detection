import makeRegression from "../utils/makeRegression";
import lstsq from "../utils/lstsq";
import { dataSources } from "../utils/datasources";

const HARMONICS = 2;
const DATASOURCE = "S2L2A";
const INPUT = "NDVI"

function setup() {
  return {
    input: dataSources[DATASOURCE].validBands.concat(dataSources[DATASOURCE].inputs[INPUT].bands),
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
    if (dataSources[DATASOURCE].validate(sample)) {
      y.push(dataSources[DATASOURCE].inputs[INPUT].calculate(sample));
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

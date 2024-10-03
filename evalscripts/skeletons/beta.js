import makeRegression from "../utils/makeRegression";
import lstsq, { vectorMatrixMul } from "../utils/lstsq";
import { dataSources } from "../utils/datasources";
import { metrics } from "../utils/metrics";

const c =
// CONFIG
{
  HARMONICS: 2,
  DATASOURCE: "ARPS",
  INPUT: "NDVI",
  METRIC: "RMSE"
}
// CONFIG

const ds = dataSources[c.DATASOURCE];
// Number of harmonics
const nHarmonics = c.HARMONICS * 2 + 1

function setup() {
  return {
    input: ds.validBands.concat(ds.inputs[c.INPUT].bands),
    output: {
      // +1 for metric
      bands: nHarmonics + 1,
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
  fullX = makeRegression(dates, c.HARMONICS);
  return collections;
}

function evaluatePixel(samples) {
  if (samples.length == 0) {
    return [NaN, NaN, NaN];
  }
  let y = [];
  let X = [];
  for (let i = 0; i < nHarmonics; i++) X[i] = [];
  for (let i = 0; i < samples.length; i++) {
    const sample = samples[i];
    if (ds.validate(sample)) {
      y.push(ds.inputs[c.INPUT].calculate(sample));
      for (let j = 0; j < nHarmonics; j++) {
        X[j].push(fullX[i][j]);
      }
    }
  }
  if (y.length == 0) {
    return [NaN, NaN, NaN];
  }
  const beta = lstsq(X, y);
  // Calculate metric based on the residuals
  const yHat = vectorMatrixMul(X, beta);
  const metric = metrics[c.METRIC](y, yHat)
  return beta.push(metric);
}

// DISCARD FROM HERE

exports.setup = setup;
exports.preProcessScenes = preProcessScenes;
exports.evaluatePixel = evaluatePixel;

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
  for (let i = 0; i < samples.length; i++) {
    const sample = samples[i];
    if (ds.validate(sample)) {
      y.push(ds.inputs[c.INPUT].calculate(sample));
      X.push(fullX[i])
    }
  }
  if (y.length == 0) {
    return [NaN, NaN, NaN];
  }
  const {beta, predicted} = lstsq(X, y);
  // Calculate metric based on the residuals
  const metric = metrics[c.METRIC](y, predicted);
  return beta.concat(metric);
}

// DISCARD FROM HERE

exports.setup = setup;
exports.preProcessScenes = preProcessScenes;
exports.evaluatePixel = evaluatePixel;

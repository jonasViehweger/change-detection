import makeRegression from "../utils/makeRegression";
import lstsq from "../utils/lstsq";
import { dataSources } from "../utils/datasources";

const c =
// CONFIG
{
  HARMONICS: 2,
  DATASOURCE: "ARPS",
  INPUT: "NDVI"
}
// CONFIG

const ds = dataSources[c.DATASOURCE];

function setup() {
  return {
    input: ds.validBands.concat(ds.inputs[c.INPUT].bands),
    output: {
      bands: c.HARMONICS * 2 + 1,
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
  const N = c.HARMONICS * 2 + 1;
  for (let i = 0; i < N; i++) X[i] = [];
  for (let i = 0; i < samples.length; i++) {
    const sample = samples[i];
    if (ds.validate(sample)) {
      y.push(ds.inputs[c.INPUT].calculate(sample));
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

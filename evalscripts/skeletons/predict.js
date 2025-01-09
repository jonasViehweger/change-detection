import makeRegression from "../utils/makeRegression";
import dot from "../utils/dot";
import dateToNumber from "../utils/dateToNumber";
import { dataSources } from "../utils/datasources";

const c =
// CONFIG
{
  HARMONICS: 2,
  DATASOURCE: "ARPS",
  INPUT: "NDVI",
  SENSITIVITY: 5,
  BOUND: 5
}
// CONFIG

const ds = dataSources[c.DATASOURCE];

var bands = new Array(c.HARMONICS * 2 + 1);
for (let i = 0; i < c.HARMONICS * 2 + 1; i++) {
  bands[i] = "c_" + (i + 1);
}
bands.push("process", "metric", "disturbedDate")

function setup() {
  return {
    input: [
      { datasource: "beta", bands: bands, mosaicking: "SIMPLE" },
      {
        datasource: c.DATASOURCE,
        bands: ds.validBands.concat(ds.inputs[c.INPUT].bands),
        mosaicking: "ORBIT",
      },
    ],
    output: [
      {
        id: "default",
        bands: 2,
        sampleType: "FLOAT32",
      },
    ],
  };
}

function preProcessScenes(collections) {
  // This creates the X (predictors) only once for the entire collection
  // This fullX will be filtered in evaluate pixel depending on clouds
  var dates = collections[c.DATASOURCE].scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates, c.HARMONICS);
  return collections;
}

var disturbed = {};

function evaluatePixel(samples, scenes) {
  const b = samples.beta[0];
  var process = b.process;
  var disturbedDate = b.disturbedDate;
  if (samples[c.DATASOURCE].length == 0 || disturbedDate > 0) {
    return [disturbedDate, process];
  }
  var beta = new Array(c.HARMONICS * 2 + 1);
  for (let i = 0; i < beta.length; i++) {
    beta[i] = b["c_" + (i + 1)];
  }
  for (let i = 0; i < samples[c.DATASOURCE].length; i++) {
    const sample = samples[c.DATASOURCE][i];
    if (ds.validate(sample)) {
      const y = ds.inputs[c.INPUT].calculate(sample);
      const X = fullX[i];
      const pred = dot(X, beta);
      process = updateProcessCCDC(pred, y, process, b.metric);
      if (process >= c.BOUND) {
        disturbedDate = dateToNumber(scenes[c.DATASOURCE].scenes.orbits[i].dateFrom);
        const count = disturbed[disturbedDate] || 0;
        disturbed[disturbedDate] = count + 1;
        break;
      }
    }
  }
  return [disturbedDate, process];
}

function updateOutputMetadata(scenes, inputMetadata, outputMetadata){
  outputMetadata.userData = { "newDisturbed":  disturbed }
}

function updateProcessCCDC(pred, actual, process, rmse = 1) {
  const residual = pred - actual;
  if (Math.abs(residual) > c.SENSITIVITY * rmse) {
    return ++process;
  } else {
    return 0;
  }
}

// DISCARD FROM HERE

exports.setup = setup;
exports.preProcessScenes = preProcessScenes;
exports.evaluatePixel = evaluatePixel;

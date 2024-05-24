import makeRegression from "../utils/makeRegression";
import dot from "../utils/dot";
import { dataSources } from "../utils/datasources";

const HARMONICS = 2;
const SENSITIVITY = 5;
const BOUND = 5;
const DATASOURCE = "ARPS";
const INPUT = "NDVI";

var bands = new Array(HARMONICS * 2 + 1);
for (let i = 0; i < HARMONICS * 2 + 1; i++) {
  bands[i] = "c_" + (i + 1);
}
bands.push("process", "metric", "disturbedDate")

function setup() {
  return {
    input: [
      { datasource: "beta", bands: bands, mosaicking: "SIMPLE" },
      {
        datasource: DATASOURCE,
        bands: dataSources[DATASOURCE].validBands.concat(dataSources[DATASOURCE].inputs[INPUT].bands),
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
  var dates = collections[DATASOURCE].scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates, HARMONICS);
  return collections;
}

function evaluatePixel(samples, scenes) {
  const b = samples.beta[0];
  var process = b.process;
  var disturbedDate = b.disturbedDate;
  if (samples[DATASOURCE].length == 0 || disturbedDate > 0) {
    return [disturbedDate, process];
  }
  var beta = new Array(HARMONICS * 2 + 1);
  for (let i = 0; i < beta.length; i++) {
    beta[i] = b["c_" + (i + 1)];
  }
  for (let i = 0; i < samples[DATASOURCE].length; i++) {
    const sample = samples[DATASOURCE][i];
    if (dataSources[DATASOURCE].validate(sample)) {
      const y = dataSources[DATASOURCE].inputs[INPUT].calculate(sample);
      const X = fullX[i];
      const pred = dot(X, beta);
      process = updateProcessCCDC(pred, y, process, b.metric);
      if (process >= BOUND) {
        disturbedDate = dateToInt(scenes[DATASOURCE].scenes.orbits[i].dateFrom);
        break;
      }
    }
  }
  return [disturbedDate, process];
}

function dateToInt(datetimestring) {
  // Converts an ISO datetime string to an int with format YYYYMMDD
  return parseInt(datetimestring.split("T")[0].split("-").join(""));
}

function updateProcessCCDC(pred, actual, process, rmse = 1) {
  const residual = pred - actual;
  if (Math.abs(residual) > SENSITIVITY * rmse) {
    return ++process;
  } else {
    return 0;
  }
}

// DISCARD FROM HERE

exports.setup = setup;
exports.preProcessScenes = preProcessScenes;
exports.evaluatePixel = evaluatePixel;

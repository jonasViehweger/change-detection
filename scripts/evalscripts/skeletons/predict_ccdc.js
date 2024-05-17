import makeRegression from "../utils/makeRegression";
import dot from "../utils/dot";

const HARMONICS = 2;
const SENSITIVITY = 5;
const BOUND = 5;
var bands = new Array(HARMONICS * 2 + 3);
for (let i = 0; i < HARMONICS * 2 + 1; i++) {
  bands[i] = "c" + (i + 1);
}
bands[bands.length - 2] = "process";
bands[bands.length - 1] = "metric1";

function setup() {
  return {
    input: [
      { datasource: "beta", bands: bands, mosaicking: "SIMPLE" },
      {
        datasource: "ARPS",
        bands: ["SR3", "SR4", "dataMask"],
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
  var dates = collections.ARPS.scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates, HARMONICS);
  return collections;
}

function evaluatePixel(samples, scenes) {
  if (samples.ARPS.length == 0) {
    return [0, 0];
  }
  const b = samples.beta[0];
  var process = b.process;
  var beta = new Array(HARMONICS * 2 + 1);
  for (let i = 0; i < beta.length; i++) {
    beta[i] = b["c" + (i + 1)];
  }
  for (let i = 0; i < samples.ARPS.length; i++) {
    const sample = samples.ARPS[i];
    if (sample.dataMask == 1) {
      const y = (sample.SR4 - sample.SR3) / (sample.SR4 + sample.SR3);
      const X = fullX[i];
      const pred = dot(X, beta);
      process = updateProcessCCDC(pred, y, process, b.metric1);
      if (process >= BOUND) {
        var disturbedDate = dateToInt(scenes.ARPS.scenes.orbits[i].dateFrom);
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

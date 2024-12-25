import makeRegression from "../utils/makeRegression";
import dot from "../utils/dot";

const HARMONICS = 2;
var bands = new Array(HARMONICS * 2 + 3);
for (let i = 0; i < HARMONICS * 2 + 1; i++) {
  bands[i] = "c" + (i + 1);
}
bands[bands.length - 2] = "process";
bands[bands.length - 1] = "rmse";

function setup() {
  return {
    input: [
      {
        datasource: "beta",
        bands: bands,
        mosaicking: "SIMPLE",
      },
      {
        datasource: "ARPS",
        bands: ["SR3", "SR4", "dataMask"],
        mosaicking: "ORBIT",
      },
    ],
    output: {
      bands: 0,
      sampleType: "UINT8",
    },
  };
}

function preProcessScenes(collections) {
  // This creates the X (predictors) only once for the entire collection
  // This fullX will be filtered in evaluate pixel depending on clouds
  dates = collections.ARPS.scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates, HARMONICS);
  return collections;
}

userData = {};

function evaluatePixel(samples, scenes) {
  if (samples.ARPS.length == 0) {
    return [NaN];
  }

  const b = samples.beta[0];
  var beta = new Array(HARMONICS * 2 + 1);
  for (let i = 0; i < beta.length; i++) {
    beta[i] = b["c" + (i + 1)];
  }

  userData.pred = [];
  userData.observed = [];
  userData.dates = [];
  userData.rmse = b.rmse;

  for (let i = 0; i < samples.ARPS.length; i++) {
    const sample = samples.ARPS[i];
    if (sample.dataMask == 1) {
      const y = index(sample.SR4, sample.SR3);
      userData.observed.push(y);
      const X = fullX[i];
      const pred = dot(X, beta);
      userData.pred.push(pred);
      userData.dates.push(dates[i].toISOString());
    }
  }
}

function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
  outputMetadata.userData = userData;
}

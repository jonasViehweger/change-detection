import makeRegression from "../utils/makeRegression";
import dot from "../utils/dot";

const HARMONICS = 2;
var bands = new Array(HARMONICS * 2 + 2);
for (let i = 0; i < HARMONICS * 2 + 1; i++) {
  bands[i] = "c" + (i + 1);
}
bands[bands.length - 1] = "process";

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
      bands: 1,
      sampleType: "FLOAT32",
    },
  };
}

function preProcessScenes(collections) {
  // This creates the X (predictors) only once for the entire collection
  // This fullX will be filtered in evaluate pixel depending on clouds
  var dates = collections.ARPS.scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates);
  return collections;
}

function evaluatePixel(samples) {
  if (samples.ARPS.length == 0) {
    return [NaN];
  }
  var mse = 0;
  var valid = 0;
  const b = samples.beta[0];
  var beta = new Array(HARMONICS * 2 + 1);
  for (let i = 0; i < beta.length; i++) {
    beta[i] = b["c" + (i + 1)];
  }
  for (let i = 0; i < samples.ARPS.length; i++) {
    const sample = samples.ARPS[i];
    if (sample.dataMask == 1) {
      const y = index(sample.SR4, sample.SR3);
      const X = fullX[i];
      const pred = dot(X, beta);
      const residual = pred - y;
      mse += Math.pow(residual, 2);
      valid++;
    }
  }
  if (valid == 0) {
    return [NaN, NaN, NaN];
  }
  return [Math.sqrt(mse / valid)];
}

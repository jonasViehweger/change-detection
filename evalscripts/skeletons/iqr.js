import makeRegression from "../utils/makeRegression";
import computeResiduals from "../utils/residuals";
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

var bands = new Array(c.HARMONICS * 2 + 2);
for (let i = 0; i < c.HARMONICS * 2 + 1; i++) {
  bands[i] = "c_" + (i + 1);
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
        datasource: c.DATASOURCE,
        bands: ds.validBands.concat(ds.inputs[c.INPUT].bands),
        mosaicking: "ORBIT",
      },
    ],
    output: {
      bands: 2,
      sampleType: "FLOAT32",
    },
  };
}

function preProcessScenes(collections) {
  var dates = collections[c.DATASOURCE].scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates);
  return collections;
}

function percentile(sorted, p) {
  const idx = p * (sorted.length - 1);
  const lo = Math.floor(idx);
  const hi = Math.ceil(idx);
  return sorted[lo] + (sorted[hi] - sorted[lo]) * (idx - lo);
}

function evaluatePixel(samples) {
  if (samples[c.DATASOURCE].length == 0) {
    return [NaN, NaN];
  }
  const b = samples.beta[0];
  var beta = new Array(c.HARMONICS * 2 + 1);
  for (let i = 0; i < beta.length; i++) {
    beta[i] = b["c_" + (i + 1)];
  }
  const residuals = computeResiduals(samples, c.DATASOURCE, fullX, beta, ds, c.INPUT);
  if (residuals.length == 0) {
    return [NaN, NaN];
  }
  residuals.sort((a, b) => a - b);
  return [percentile(residuals, 0.25), percentile(residuals, 0.75)];
}

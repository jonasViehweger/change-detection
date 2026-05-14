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
  METRIC: "RMSE",
  SENSITIVITY_LOWER: 5,
  SENSITIVITY_UPPER: 5,
  BOUND: 5
}
// CONFIG

const ds = dataSources[c.DATASOURCE];

var bands = new Array(c.HARMONICS * 2 + 1);
for (let i = 0; i < c.HARMONICS * 2 + 1; i++) {
  bands[i] = "c_" + (i + 1);
}
bands.push("process", "metric_lower", "metric_upper", "disturbedDate")

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
  var dates = collections[c.DATASOURCE].scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates, c.HARMONICS);
  dateNrs = collections[c.DATASOURCE].scenes.orbits.map(
    (scene) => dateToNumber(scene.dateFrom)
  );
  return collections;
}

var monitorResults = {};

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
      currentDate = dateNrs[i]
      if(!(currentDate in monitorResults)){
          monitorResults[currentDate] = {"monitoredPixels": 0, "disturbedPixels": 0}
      }
      monitorResults[currentDate]["monitoredPixels"]++
      const y = ds.inputs[c.INPUT].calculate(sample);
      const X = fullX[i];
      const pred = dot(X, beta);
      process = updateProcessCCDC(pred, y, process, b.metric_lower, b.metric_upper);
      if (process >= c.BOUND) {
        disturbedDate = currentDate
        monitorResults[currentDate]["disturbedPixels"]++;
        break;
      }
    }
  }
  return [disturbedDate, process];
}

function updateOutputMetadata(scenes, inputMetadata, outputMetadata){
  outputMetadata.userData = {"monitorResults": monitorResults}
}

function updateProcessCCDC(pred, actual, process, metric_lower, metric_upper) {
  const residual = pred - actual;
  var outlier;
  if (c.METRIC === "IQR") {
    const iqr = metric_upper - metric_lower;
    outlier = residual < metric_lower - c.SENSITIVITY_LOWER * iqr ||
              residual > metric_upper + c.SENSITIVITY_UPPER * iqr;
  } else {
    outlier = residual < -c.SENSITIVITY_LOWER * metric_lower ||
              residual > c.SENSITIVITY_UPPER * metric_upper;
  }
  if (outlier) {
    return ++process;
  }
  return 0;
}

// DISCARD FROM HERE

exports.setup = setup;
exports.preProcessScenes = preProcessScenes;
exports.evaluatePixel = evaluatePixel;

function dateToDecimalDate(date) {
    // Takes a UTM date object and returns doy divided by length of year in days
    // i.e. 0 for first of january, 1 for midnight in December
    const start = new Date(Date.UTC(date.getUTCFullYear(), 0, 0));
    // const end = new Date(Date.UTC(date.getUTCFullYear() + 1, 0, 0));
    // const diffYear = end - start;
    const diffYear = 31622400000;
    return (date - start) / diffYear;
}

function makeRegression(dates, harmonics=1) {
    // This converts dates to decimal dates and those into a harmonic regression of the first order
    // with cos and sin over a year
    let n = dates.length;
    var X = new Array(n);
    for (let i = 0; i < n; i++) {
        let Xi = new Array(harmonics * 2 + 1);
        Xi[0] = 1;
        let decimalDate = dateToDecimalDate(dates[i]);
        for (let harmonic = 1; harmonic <= harmonics; harmonic++) {
            let Xharmon = 2 * Math.PI * decimalDate * harmonic;
            Xi[harmonic * 2 - 1] = Math.sin(Xharmon);
            Xi[harmonic * 2] = Math.cos(Xharmon);
        }
        X[i] = Xi;
    }
    return X;
}

function dot(A, B) {
    let result = 0;
    for (let i = A.length; i--; ) {
      result += A[i] * B[i];
    }
    return result;
  }

var dataSources = {
    ARPS: {
        validBands: ["dataMask"],
        validate: function (sample) {
            return sample.dataMask;
        },
        inputs: {
            NDVI: {
                bands: ["SR3", "SR4"],
                calculate: function (sample) {
                    return (sample.SR4 - sample.SR3) / (sample.SR4 + sample.SR3);
                }
            }
        }
    },
    S2L2A: {
        validBands: ["dataMask", "SCL"],
        validate: function (sample) {
            // Define codes as invalid:
            const invalid = [
                0, // NO_DATA
                1, // SATURATED_DEFECTIVE
                3, // CLOUD_SHADOW
                7, // CLOUD_LOW_PROBA
                8, // CLOUD_MEDIUM_PROBA
                9, // CLOUD_HIGH_PROBA
                10 // THIN_CIRRUS
            ];
            return !invalid.includes(sample.SCL) && sample.dataMask
        },
        inputs: {
            NDVI: {
                bands: ["B04", "B08"],
                calculate: function (sample) {
                    return (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
                }
            }
        }
    }
};

const c =
// CONFIG
{
  HARMONICS: 2,
  DATASOURCE: "ARPS",
  INPUT: "NDVI",
  SENSITIVITY: 5,
  BOUND: 5
};
// CONFIG

const ds = dataSources[c.DATASOURCE];

var bands = new Array(c.HARMONICS * 2 + 1);
for (let i = 0; i < c.HARMONICS * 2 + 1; i++) {
  bands[i] = "c_" + (i + 1);
}
bands.push("process", "metric", "disturbedDate");

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
  outputMetadata.userData = { "newDisturbed":  disturbed };
}

function dateToNumber(datetimestring) {
  // Converts an ISO datetime string to an int with format YYYYMMDD
  return parseFloat(datetimestring.split("T")[0].split("-").join(""));
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

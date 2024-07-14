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
  INPUT: "NDVI"
};
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
      bands: 1,
      sampleType: "FLOAT32",
    },
  };
}

function preProcessScenes(collections) {
  // This creates the X (predictors) only once for the entire collection
  // This fullX will be filtered in evaluate pixel depending on clouds
  var dates = collections[c.DATASOURCE].scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates);
  return collections;
}

function evaluatePixel(samples) {
  if (samples[c.DATASOURCE].length == 0) {
    return [NaN];
  }
  var mse = 0;
  var valid = 0;
  const b = samples.beta[0];
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

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

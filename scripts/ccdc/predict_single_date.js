const HARMONICS = 2;
var bands = new Array(HARMONICS*2+3);
for (let i=0; i<HARMONICS*2+1; i++){
	bands[i] = "c"+(i+1);
}
bands[bands.length-2] = "process";
bands[bands.length-1] = "sigma";

function setup() {
  return {
    input: [
      { datasource: "beta", bands: bands},
      { datasource: "ARPS", bands: ["SR3", "SR4", "dataMask"] },
    ],
    output: {
      bands: 1,
      sampleType: "UINT8",
    },
    mosaicking: "SIMPLE",
  };
}

function evaluatePixel(samples) {
  const b = samples.beta[0];
  if (samples.ARPS.length == 0 || !samples.ARPS[0].dataMask) {
    return [b.process];
  }
  const ndvi = index(samples.ARPS[0].SR4, samples.ARPS[0].SR3);
  // Predict all values for the most recent image
  const Xpred = makeRegression([new Date(INSERT_DATE)]);
  var beta = new Array(HARMONICS*2+1);
  for(let i=0; i<beta.length;i++){
    beta[i] = b["c"+(i+1)]
  }
  const pred = dot(Xpred[0], beta);
  return [updateProcessCCDC(pred, ndvi, b.process, b.sigma)];
}

function updateProcessCCDC(pred, actual, process, rmse = 1) {
  const residual = pred - actual;
  if (Math.abs(residual) > 3 * rmse) {
    return ++process;
  } else {
    return 0;
  }
}

function updateProcess(pred, actual, process, sigma = 1) {
  const residual = pred - actual;
  const standardizedResid = residual / sigma;
  const newProcess = process + standardizedResid;
  return newProcess;
}

function isClear(sample) {
  return sample.dataMask == 1;
}

function dateToDecimalDate(date) {
  // Takes a UTM date object and returns doy divided by lenght of year in days
  // i.e. 0 for first of january, 1 for midnight at 12
  const start = new Date(Date.UTC(date.getUTCFullYear(), 0, 0));
  // const end = new Date(Date.UTC(date.getUTCFullYear() + 1, 0, 0));
  // const diffYear = end - start;
  const diffYear = 31622400000;
  return (date - start) / diffYear;
}

function makeRegression(dates) {
  // This converts dates to decimal dates and those into a harmonic regression of the first order
  // with cos and sin over a year
  let n = dates.length;
  var X = new Array(n);
  for (let i = 0; i < n; i++) {
  	let Xi = new Array(HARMONICS*2+1);
    Xi[0] = 1;
    let decimalDate = dateToDecimalDate(dates[i]);
    for (let harmonic = 1; harmonic <= HARMONICS; harmonic++) {
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
  for (let i = 0; i < A.length; i++) {
    result += A[i] * B[i];
  }
  return result;
}

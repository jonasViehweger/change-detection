function setup() {
  return {
    input: [
      { datasource: "beta", bands: ["c1", "c2", "c3", "process", "rmse"] },
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
  const ndvi = calcNDVI(samples.ARPS[0]);
  // Predict all values for the most recent image
  const Xpred = makeRegression([new Date(INSERT_DATE)]);
  const beta = [[b.c1], [b.c2], [b.c3]];
  const pred = dot(Xpred, beta);
  return [updateProcessCCDC(pred, ndvi, b.process, b.rmse)];
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

function calcNDVI(sample) {
  return index(sample.SR4, sample.SR3);
}

function dateToDecimalDate(date) {
  // Takes a UTM date object and returns doy divided by lenght of year in days
  // i.e. 0 for first of january, 1 for midnight at 12
  const start = new Date(Date.UTC(date.getUTCFullYear(), 0, 0));
  const end = new Date(Date.UTC(date.getUTCFullYear() + 1, 0, 0));
  const diffYear = end - start;
  return (date - start) / diffYear;
}

function makeRegression(dates) {
  // This converts dates to decimal dates and those into a harmonic regression of the first order
  // with cos and sin over a year
  const harmonicOrder = 1;
  let XSin = [];
  let XCos = [];
  let n = dates.length;
  for (let i = 0; i < n; i++) {
    let decimalDate = dateToDecimalDate(dates[i]);
    let Xharmon = 2 * Math.PI * decimalDate * harmonicOrder;
    XSin.push(Math.sin(Xharmon));
    XCos.push(Math.cos(Xharmon));
  }
  let intersect = new Array(n);
  for (let i = 0; i < n; ++i) intersect[i] = 1;
  return [intersect, XSin, XCos];
}

function dot(A, B) {
  let result = 0;
  for (let i = 0; i < A.length; i++) {
    result += A[i] * B[i];
  }
  return result;
}

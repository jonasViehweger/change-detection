function setup() {
  return {
    input: [
      { datasource: "beta", bands: ["c1", "c2", "c3", "process"] },
      { datasource: "ARPS", bands: ["SR3", "SR4", "dataMask"] },
    ],
    output: {
      bands: 1,
      sampleType: "FLOAT32",
    },
    mosaicking: "ORBIT",
  };
}

function evaluatePixel(samples, scene) {
  if (samples.length == 0 && !samples.ARPS[0].dataMask) {
    return [NaN];
  }
  const b = samples.beta[0];
  const ndvi = calcNDVI(samples.ARPS[0]);
  // Predict all values for the most recent image
  const Xpred = makeRegression([new Date("2022-01-03T00:00:00.000Z")]);
  const beta = [b.c1, b.c2, b.c3];
  const pred = dot(Xpred, beta);
  return [updateProcess(pred, ndvi, b.process)];
}

function updateProcess(pred, actual, process) {
  const residual = pred - actual;
  const newProcess = process + residual;
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

var s6 = 0,
  l6 = v.length;
for (var i6 = 0; i6 < l6; i6++) s6 += v[i6] * w[i6];

function dot(a, b) {
  let result = 0;
  for (let i = 0; i < a.length; i++) {
    result += a[i] * b[i];
  }
  return result;
}

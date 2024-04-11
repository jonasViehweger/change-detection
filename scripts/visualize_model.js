function setup() {
  return {
    input: [
      {
        datasource: "beta",
        bands: ["c1", "c2", "c3", "process"],
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
  dates = collections.ARPS.scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates);
  return collections;
}

userData = {};

function evaluatePixel(samples, scenes) {
  if (samples.ARPS.length == 0) {
    return [NaN];
  }
  const b = samples.beta[0];
  const clear = samples.ARPS.map((sample) => isClear(sample));
  const clearTs = samples.ARPS.filter((item, i) => clear[i]);
  if (clearTs.length == 0) {
    return [NaN];
  }
  let X = new Array(fullX.length);
  for (let i = 0; i < fullX.length; i++) {
    let clearX = fullX[i].filter((item, i) => clear[i]);
    X[i] = clearX;
  }
  const y = clearTs.map((sample) => calcNDVI(sample));
  var pred = new Array(y.length);
  const beta = [b.c1, b.c2, b.c3];
  for (let i = 0; i < y.length; i++) {
    pred[i] = dot([[X[0][i]], [X[1][i]], [X[2][i]]], beta);
  }
  const clearDates = dates.filter((item, i) => clear[i]);
  userData.pred = pred;
  userData.observed = y;
  userData.dates = clearDates.map((date) => date.toISOString());
  return [pred[0]];
}

function updateOutputMetadata(scenes, inputMetadata, outputMetadata) {
  outputMetadata.userData = userData;
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

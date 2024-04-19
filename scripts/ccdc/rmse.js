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
  for (let i = 0; i < samples.ARPS.length; i++) {
    const sample = samples.ARPS[i];
    if (sample.dataMask == 1) {
      const y = index(sample.SR4, sample.SR3);
      var X = [[], [], []];
      for (let j = 0; j < fullX.length; j++) {
        X[j][0] = fullX[j][i];
      }
      const b = samples.beta[0];
      const beta = [b.c1, b.c2, b.c3];
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
  const harmonicOrder = 1;
  let n = dates.length;
  let XSin = new Float32Array(n);
  let XCos = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    let decimalDate = dateToDecimalDate(dates[i]);
    let Xharmon = 2 * Math.PI * decimalDate * harmonicOrder;
    XSin[i] = Math.sin(Xharmon);
    XCos[i] = Math.cos(Xharmon);
  }
  let intersect = new Uint8Array(n);
  for (let i = 0; i < n; ++i) intersect[i] = 1;
  return [intersect, XSin, XCos];
}

function dot(A, B) {
  let result = 0;
  for (let i = A.length; i--; ) {
    result += A[i] * B[i];
  }
  return result;
}

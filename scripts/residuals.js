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
  const b = samples.beta[0];
  const clear = samples.ARPS.map((sample) => isClear(sample));
  const clearTs = samples.ARPS.filter((item, i) => clear[i]);
  if (clearTs.length == 0) {
    return [NaN];
  }
  let X = [];
  for (let i = 0; i < fullX.length; i++) {
    let clearX = fullX[i].filter((item, i) => clear[i]);
    X[i] = clearX;
  }
  const y = clearTs.map((sample) => calcNDVI(sample));
  var residuals = [];
  const beta = [b.c1, b.c2, b.c3];
  for (let i = 0; i < y.length; i++) {
    var pred = dot([[X[0][i]], [X[1][i]], [X[2][i]]], beta);
    residuals[i] = pred - y[i];
  }
  return [rmse(residuals)];
}

function sum(array) {
  let sum = 0;
  for (let i = array.length; i--; ) {
    sum += array[i];
  }
  return sum;
}

function mean(array) {
  return sum(array) / array.length;
}

function rmse(residuals) {
  let sum = 0;
  for (let i = 0; i < residuals.length; i++) {
    sum += Math.pow(residuals[i], 2);
  }
  return Math.sqrt(sum / residuals.length);
}

function std(array, mean) {
  let sum = 0;
  for (let i = 0; i < array.length; i++) {
    sum += Math.pow(array[i] - mean, 2);
  }
  return Math.sqrt(sum / array.length);
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

function lstsq(X, y) {
  const Xt = transpose(X);
  const Xdot = matrixDot(X, Xt);
  const XTX = inv(Xdot);
  const XTY = vectorMatrixMul(X, y);
  return vectorMatrixMul(XTX, XTY);
}

function dot(A, B) {
  let result = 0;
  for (let i = 0; i < A.length; i++) {
    result += A[i] * B[i];
  }
  return result;
}

function transpose(a) {
  return a[0].map((_, colIndex) => a.map((row) => row[colIndex]));
}

//The chosen one
function matrixDot(A, B) {
  var result = new Array(A.length)
    .fill(0)
    .map((row) => new Array(B[0].length).fill(0));

  return result.map((row, i) => {
    return row.map((val, j) => {
      return A[i].reduce((sum, elm, k) => sum + elm * B[k][j], 0);
    });
  });
}

function vectorMatrixMul(A, B) {
  let result_len = A.length;
  let result = new Array(result_len).fill(0);
  for (let i = 0; i < B.length; i++) {
    for (let j = 0; j < result_len; j++) {
      result[j] += A[j][i] * B[i];
    }
  }
  return result;
}

// Returns the inverse of matrix `_A`.
// taken from here: https://gist.github.com/husa/5652439
function inv(_A) {
  var temp,
    N = _A.length,
    E = [];

  for (var i = 0; i < N; i++) E[i] = [];

  for (i = 0; i < N; i++)
    for (var j = 0; j < N; j++) {
      E[i][j] = 0;
      if (i == j) E[i][j] = 1;
    }

  for (var k = 0; k < N; k++) {
    temp = _A[k][k];

    for (var j = 0; j < N; j++) {
      _A[k][j] /= temp;
      E[k][j] /= temp;
    }

    for (var i = k + 1; i < N; i++) {
      temp = _A[i][k];

      for (var j = 0; j < N; j++) {
        _A[i][j] -= _A[k][j] * temp;
        E[i][j] -= E[k][j] * temp;
      }
    }
  }

  for (var k = N - 1; k > 0; k--) {
    for (var i = k - 1; i >= 0; i--) {
      temp = _A[i][k];

      for (var j = 0; j < N; j++) {
        _A[i][j] -= _A[k][j] * temp;
        E[i][j] -= E[k][j] * temp;
      }
    }
  }

  for (var i = 0; i < N; i++) for (var j = 0; j < N; j++) _A[i][j] = E[i][j];
  return _A;
}

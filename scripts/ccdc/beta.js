function setup() {
  return {
    input: ["SR3", "SR4", "dataMask"],
    output: {
      bands: 3,
      sampleType: "FLOAT32",
    },
    mosaicking: "ORBIT",
  };
}

function preProcessScenes(collections) {
  // This creates the X (predictors) only once for the entire collection
  // This fullX will be filtered in evaluate pixel depending on clouds
  var dates = collections.scenes.orbits.map(
    (scene) => new Date(scene.dateFrom)
  );
  fullX = makeRegression(dates);
  return collections;
}

function evaluatePixel(samples, scene) {
  if (samples.length == 0) {
    return [NaN, NaN, NaN];
  }
  let y = [];
  let X = [[], [], []];
  for (let i = 0; i < samples.length; i++) {
    const sample = samples[i];
    if (sample.dataMask == 1) {
      y.push(index(sample.SR4, sample.SR3));
      for (let j = 0; j < fullX.length; j++) {
        X[j].push(fullX[j][i]);
      }
    }
  }
  if (y.length == 0) {
    return [NaN, NaN, NaN];
  }
  // const clear = samples.map((sample) => isClear(sample));
  // const clearTs = samples.filter((item, i) => clear[i]);
  // if (clearTs.length == 0) {
  //   return [NaN, NaN, NaN];
  // }
  // let X = [];
  // for (let i = 0; i < fullX.length; i++) {
  //   let clearX = fullX[i].filter((item, i) => clear[i]);
  //   X[i] = clearX;
  // }
  // const y = clearTs.map((sample) => calcNDVI(sample));
  const beta = lstsq(X, y);
  return beta;
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

function transpose(matrix) {
  const rows = matrix.length,
    cols = matrix[0].length;
  const grid = [];
  for (let j = 0; j < cols; j++) {
    grid[j] = Array(rows);
  }
  for (let i = 0; i < rows; i++) {
    for (let j = 0; j < cols; j++) {
      grid[j][i] = matrix[i][j];
    }
  }
  return grid;
}

function matrixDot(a, b) {
  var aNumRows = a.length,
    aNumCols = a[0].length,
    bNumRows = b.length,
    bNumCols = b[0].length,
    m = new Array(aNumRows); // initialize array of rows
  for (var r = 0; r < aNumRows; ++r) {
    m[r] = new Array(bNumCols); // initialize the current row
    for (var c = 0; c < bNumCols; ++c) {
      m[r][c] = 0; // initialize the current cell
      for (var i = 0; i < aNumCols; ++i) {
        m[r][c] += a[r][i] * b[i][c];
      }
    }
  }
  return m;
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

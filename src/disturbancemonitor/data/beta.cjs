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

function lstsq(X, y) {
    const Xt = transpose(X);
    const Xdot = matrixDot(X, Xt);
    const XTX = inv(Xdot);
    const XTY = vectorMatrixMul(X, y);
    return vectorMatrixMul(XTX, XTY);
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

function setup() {
  return {
    input: ds.validBands.concat(ds.inputs[c.INPUT].bands),
    output: {
      bands: c.HARMONICS * 2 + 1,
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
  fullX = makeRegression(dates, c.HARMONICS);
  return collections;
}

function evaluatePixel(samples) {
  if (samples.length == 0) {
    return [NaN, NaN, NaN];
  }
  let y = [];
  let X = [];
  const N = c.HARMONICS * 2 + 1;
  for (let i = 0; i < N; i++) X[i] = [];
  for (let i = 0; i < samples.length; i++) {
    const sample = samples[i];
    if (ds.validate(sample)) {
      y.push(ds.inputs[c.INPUT].calculate(sample));
      for (let j = 0; j < N; j++) {
        X[j].push(fullX[i][j]);
      }
    }
  }
  if (y.length == 0) {
    return [NaN, NaN, NaN];
  }
  const beta = lstsq(X, y);
  return beta;
}

// DISCARD FROM HERE

exports.setup = setup;
exports.preProcessScenes = preProcessScenes;
exports.evaluatePixel = evaluatePixel;

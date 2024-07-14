export default function lstsq(X, y) {
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

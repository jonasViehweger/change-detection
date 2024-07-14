import makeRegression from './makeRegression'

const day = [new Date("2020-12-31")]

test('testing with two harmonics', () => {
  expect(makeRegression(day, 2)[0]).toEqual([1, -2.4492935982947064e-16, 1, -4.898587196589413e-16, 1]);
});

test('testing with single harmonic', () => {
  expect(makeRegression(day, 1)).toEqual([[1, -2.4492935982947064e-16, 1]]);
});

test('testing with two harmonics, three days', () => {
  expect(
    makeRegression([new Date("2020-12-31"), new Date("2024-02-29"), new Date("2000-01-01")], 2)
  ).toEqual([
    [1, -2.4492935982947064e-16, 1, -4.898587196589413e-16, 1],
    [1, 0.8573146280763322, 0.5147928015098309, 0.8826787983255476, -0.4699767430273197],
    [1, 0.01716632975470737, 0.9998526477050269, 0.034327600513243496, 0.9994106342455052]]);
});

const manyHarmonics = 10;

test('testing with very many harmonics', () => {
  expect(
    makeRegression([new Date("2020-12-31"), new Date("2024-02-29"), new Date("2000-01-01")], manyHarmonics)[0].length
  ).toEqual(manyHarmonics*2+1);
});

test('empty list', () => {
  expect(makeRegression([], 1)).toEqual([]);
});

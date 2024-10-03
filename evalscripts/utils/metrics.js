export var metrics = {
  RMSE: rmse,
};

export function rmse(actual, pred) {
  let mse = 0;
  for (let i = 0; i < actual.length; i++) {
    mse += Math.pow(actual[i] - pred[i], 2);
  }
  return Math.sqrt(mse / actual.length);
}

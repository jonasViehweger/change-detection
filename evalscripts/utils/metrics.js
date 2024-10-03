export var metrics = {
  RMSE: rmse,
};

export function rmse(y, pred) {
  var mse = 0;
  for (let i = 0; i < y.length; i++) {
    mse += Math.pow(y[i]-pred[i], 2);
  }
  return Math.sqrt(mse / y.length);
}

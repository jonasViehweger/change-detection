import dot from "./dot";

export default function computeResiduals(samples, datasource, fullX, beta, ds, input) {
  var residuals = [];
  for (let i = 0; i < samples[datasource].length; i++) {
    const sample = samples[datasource][i];
    if (ds.validate(sample)) {
      const y = ds.inputs[input].calculate(sample);
      const pred = dot(fullX[i], beta);
      residuals.push(pred - y);
    }
  }
  return residuals;
}

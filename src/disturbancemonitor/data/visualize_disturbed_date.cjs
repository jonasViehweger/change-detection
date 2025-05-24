//VERSION=3
var start = 1;
var end = Infinity;

function setup() {
  return {
    input: ["disturbedDate", "dataMask"],
    output: [
      { id: "default", bands: 4 },
      { id: "index", bands: 1, sampleType: "FLOAT32" },
      { id: "eobrowserStats", bands: 2, sampleType: "FLOAT32" },
      { id: "dataMask", bands: 1 },
    ],
  };
}

function evaluatePixel(sample) {
  let opacity = 0;
  if (sample.disturbedDate >= start && sample.disturbedDate <= end) opacity = 1;
  return {
    default: [1,0,0].concat(opacity),
    index: [sample.disturbedDate],
    eobrowserStats: [sample.disturbedDate],
    dataMask: [sample.dataMask],
  };
}

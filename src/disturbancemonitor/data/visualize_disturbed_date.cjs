function dateToNumber(datetimestring) {
    // Converts an ISO datetime string to an int with format YYYYMMDD
    return parseFloat(datetimestring.split("T")[0].slice(2).split("-").join(""));
  }

//VERSION=3
var lastMonitored = "2024-01-01";

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

const end = dateToNumber(lastMonitored);
const start = end - 10000;

const ramp = [
  [start, 0xffffd9],
  // [20230215, 0xedf8b1],
  // [20230401, 0xc7e9b4],
  // [20230519, 0x7fcdbb],
  // [20230703, 0x41b6c4],
  // [20230817, 0x1d91c0],
  // [20231001, 0x225ea8],
  // [20231115, 0x253494],
  [end, 0x081d58],
];

const visualizer = new ColorRampVisualizer(ramp);

function evaluatePixel(sample) {
  // Return RGB
  let opacity = sample.dataMask;
  if(sample.disturbedDate == 0) opacity = 0;
  return {
    default: visualizer.process(sample.disturbedDate).concat(opacity),
    index: [sample.disturbedDate],
    eobrowserStats: [sample.disturbedDate],
    dataMask: [sample.dataMask],
  };
}

//VERSION=3
function setup() {
  return {
    input: ["disturbedDate", "dataMask"],
    output: { bands: 4 },
  };
}

const ramp = [
  [20220101, 0xffffd9],
  [20220215, 0xedf8b1],
  [20220401, 0xc7e9b4],
  [20220519, 0x7fcdbb],
  [20220703, 0x41b6c4],
  [20220817, 0x1d91c0],
  [20221001, 0x225ea8],
  [20221115, 0x253494],
  [20221231, 0x081d58],
];

const visualizer = new ColorRampVisualizer(ramp);

function evaluatePixel(sample) {
  // Return RGB
  return visualizer.process(sample.disturbedDate).concat(sample.dataMask);
}

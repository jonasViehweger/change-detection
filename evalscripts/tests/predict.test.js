import { evaluatePixel, preProcessScenes } from "../predict";
import { collections } from "./collections.scenes.orbits";
import { samples, beta } from "./samples";
import "../utils/eval_utils";

const dataFusion = {
  ARPS: samples,
  beta: [
    {
      c1: beta[0],
      c2: beta[1],
      c3: beta[2],
      c4: beta[3],
      c5: beta[4],
      rmse: 0.051718,
      process: 0,
    },
  ],
};

const collectionsDf = { ARPS: collections };

const scenes = {
  ARPS: { scenes: { orbits: collections.scenes.orbits } },
};

function predictTest(preProcessScenes, evaluatePixel) {
  preProcessScenes(collectionsDf);
  return evaluatePixel(dataFusion, scenes);
}

test("Test monitoring over a time series. Result should be ignored", () => {
  expect(predictTest(preProcessScenes, evaluatePixel)).toEqual(-8);
});

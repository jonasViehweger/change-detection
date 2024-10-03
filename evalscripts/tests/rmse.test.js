import {
  evaluatePixel,
  preProcessScenes,
} from "../../src/disturbancemonitor/data/rmse";
import { collections } from "./collections.scenes.orbits";
import { samples, beta } from "./samples";

const dataFusion = {
  ARPS: samples,
  beta: [
    {
      c_1: beta[0],
      c_2: beta[1],
      c_3: beta[2],
      c_4: beta[3],
      c_5: beta[4],
    },
  ],
};

const collectionsDf = { ARPS: collections };

const scenes = {
  ARPS: { scenes: { orbits: collections.scenes.orbits } },
};

function rmseTest(preProcessScenes, evaluatePixel) {
  preProcessScenes(collectionsDf);
  return evaluatePixel(dataFusion);
}

test("Testing RMSE", () => {
  expect(rmseTest(preProcessScenes, evaluatePixel)).toEqual([0.14216365527336153]);
});

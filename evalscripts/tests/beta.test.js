import {evaluatePixel, preProcessScenes} from "../../src/disturbancemonitor/data/beta"
import {collections} from "./collections.scenes.orbits"
import {samples, beta, rmse} from "./samples"

function betaTest(preProcessScenes, evaluatePixel){
    preProcessScenes(collections)
    return evaluatePixel(samples)
}

test("Testing with two harmonics", () => {
    expect(betaTest(preProcessScenes, evaluatePixel)).toEqual(beta.concat(rmse));
  });

import {evaluatePixel, preProcessScenes} from "../beta"
import {collections} from "./collections.scenes.orbits"
import {samples, beta} from "./samples"

function betaTest(preProcessScenes, evaluatePixel){
    preProcessScenes(collections)
    return evaluatePixel(samples)
}

test('testing with two harmonics', () => {
    expect(betaTest(preProcessScenes, evaluatePixel)).toEqual(beta);
  });

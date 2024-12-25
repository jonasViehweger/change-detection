export class ColorGradientVisualizer {
	constructor(valColPairs, minVal = 0.0, maxVal = 1.0) {
		let vals = valColPairs.map(valCol => valCol[0]);
		this.minVal = minVal === undefined ? Math.min(...vals) : minVal;
		this.maxVal = maxVal === undefined ? Math.max(...vals) : maxVal;
		this.valColPairs = valColPairs.map(valCol => [this.minVal * valCol[0] + this.maxVal * (1 - valCol[0]), valCol[1]]);
	}

	getColor(val) {
		let n = this.valColPairs.length;

		if (val <= this.minVal) {
			return this.valColPairs[0][1];
		} else if (val >= this.maxVal) {
			return this.valColPairs[n - 1][1];
		}

		let preVal = this.valColPairs[0][0];
		for (let i = 1; i < n; i++) {
			let valCol = this.valColPairs[i];
			if (val > preVal && val <= valCol[0]) {
				let alpha = (val - preVal) / (valCol[0] - preVal);
				return combine(valCol[1], this.valColPairs[i - 1][1], alpha);
			}
			preVal = valCol[0];
		}

		return this.valColPairs[n - 1][1];
	}

	process(val) {
		let hex = this.getColor(val);
		return hex2rgb(hex).map(x => x / 0xFF);
	}

	processList(components) {
		return components.map(v => this.process(v));
	}

	static createRedTemperature(minVal, maxVal) {
		return new ColorGradientVisualizer(redTemperature, minVal, maxVal);
	}

	static createWhiteGreen(minVal, maxVal) {
		return new ColorGradientVisualizer(greenWhite, minVal, maxVal);
	}

	static createBlueRed(minVal, maxVal) {
		return new ColorGradientVisualizer(blueRed, minVal, maxVal);
	}
} export class ColorMapVisualizer {
	constructor(valColPairs) {
		this.valColPairs = valColPairs;
	}

	process(val) {
		let col = this.getColorFromValue(val);
		return [col >>> 16, col >>> 8, col].map(x => (x & 0xFF) / 0xFF);
	}

	getColorFromValue(value) {
		let curColor = this.valColPairs[0][1];
		for (let i = 0; i < this.valColPairs.length; i++) {
			if (value < this.valColPairs[i][0]) {
				break;
			}
			curColor = this.valColPairs[i][1];
		}
		return curColor;
	}

	static createDefaultColorMap() {
		return new ColorMapVisualizer([
			[-1.0, 0x000000],
			[-0.2, 0xFF0000],
			[-0.1, 0x9A0000],
			[0.0, 0x660000],
			[0.1, 0xFFFF33],
			[0.2, 0xCCCC33],
			[0.3, 0x666600],
			[0.4, 0x33FFFF],
			[0.5, 0x33CCCC],
			[0.6, 0x006666],
			[0.7, 0x33FF33],
			[0.8, 0x33CC33],
			[0.9, 0x006600]
		]);
	}
}
const JAVA_DOUBLE_MAX_VAL = 1.7976931348623157E308;

const blueRed = [
	[1.000, 0x000080],
	[0.875, 0x0000FF],
	[0.625, 0x00FFFF],
	[0.375, 0xFFFF00],
	[0.125, 0xFF0000],
	[0.000, 0x800000]
];

const redTemperature = [
	[1.000, 0x000000],
	[0.525, 0xAE0000],
	[0.300, 0xFF6E00],
	[0.250, 0xFF8600],
	[0.000, 0xFFFFFF]
];

const greenWhite = [
	[1.000, 0x000000],
	[0.600, 0x006600],
	[0.300, 0x80B300],
	[0.000, 0xFFFFFF]
];


var gainOverride;
var offsetOverride;
var gammaOverride; export class DefaultVisualizer {
	constructor(minValue = 0.0, maxValue = 1.0, gain = 1.0, offset = 0.0, gamma = 1.0) {
		this.minValue = minValue;
		this.maxValue = maxValue;
		this.gain = gainOverride || gain;
		this.offset = offsetOverride || offset;
		this.gamma = gammaOverride || gamma;

		this.highlightPoint = 0.92;
		this.highlightAdjust = 0 < maxValue && maxValue < 1;

		this.factor = 1.0 / (maxValue - minValue);
		this.clipPoint = 2.0;
		this.highlightFactor = (1.0 - this.highlightPoint) / (this.clipPoint - this.highlightPoint);
	}

	clamp(num, min, max) {
		return Math.max(Math.min(num, max), min);
	}

	process(val, i) {
		let v = this.gain * (val - this.minValue) * this.factor + this.offset
		/**
		 * RGB manipulation
		 *
		 * This is a temporary solution for image manipulation.
		 * Permanent solution will be implemented on frontend no later than the end of september 2019.
		 * After frontend implementation is completed, this should be removed.
		 *
		 * Used by EO Browser for correcting images of layers that use DefaultVisualizer.
		 *
		 * rangeOverrides is an array of 3 arrays which contain lower and upper range value and
		 * must be set in evalscriptoverrides in order to be used here.
		 * Lowest possible value is 0 and highest possible value is 1.
		 *
		 * Visualizer's process() must be called with both value and index: process(value, index).
		 * In most cases the map() will be used on components, example: components.map((v, i) => process(v, i)).
		 */
		if (typeof rangeOverrides !== 'undefined' && rangeOverrides !== null && rangeOverrides[i] !== undefined) {
			v = colorBlend(
				v,
				[rangeOverrides[i][0], rangeOverrides[i][1]],
				[0, 1]
			);
		}
		if (this.gamma != 1.0) {
			return Math.pow(Math.max(0, v), this.gamma);
		}
		return this.clamp(v, 0.0, 1.0);
	}

	processList(components) {
		return components.map((v, i) => process(v, i));
	}
}
export let hex2rgb = hex => [hex >>> 16, hex >>> 8, hex].map(x => x & 0xFF);
export let rgb2hex = rgb => (rgb[0] << 16) + (rgb[1] << 8) + rgb[2];

export let index = (x, y) => x + y != 0 ? (x - y) / (x + y) : 0;
export let inverse = x => x != 0 ? 1.0 / x : JAVA_DOUBLE_MAX_VAL;

export function combine(col1, col2, alpha) {
	let rgb1 = hex2rgb(col1);
	let rgb2 = hex2rgb(col2);
	return rgb2hex([0, 1, 2].map(i => Math.round(rgb1[i] * alpha + rgb2[i] * (1 - alpha))));
}
export class HighlightCompressVisualizer {
	constructor(minValue = 0.0, maxValue = 1.0, gain = 1.0, offset = 0.0, gamma = 1.0) {
		this.minValue = minValue;
		this.maxValue = maxValue;
		this.gain = gainOverride || gain;
		this.offset = offsetOverride || offset;
		this.gamma = gammaOverride || gamma;

		this.highlightPoint = 0.92;
		this.highlightAdjust = 0 < maxValue && maxValue < 1;

		this.factor = 1.0 / (maxValue - minValue);
		this.clipPoint = 2.0;
		this.highlightFactor = (1.0 - this.highlightPoint) / (this.clipPoint - this.highlightPoint);
	}

	clamp(num, min, max) {
		return Math.max(Math.min(num, max), min);
	}

	process(val, i) {
		let v = this.gain * (val - this.minValue) * this.factor + this.offset
		/**
		 * RGB manipulation
		 *
		 * This is a temporary solution for image manipulation.
		 * Permanent solution will be implemented on frontend no later than september 2019.
		 * After frontend implementation is completed, this should be removed.
		 *
		 * Used by EO Browser for correcting images of layers that use DefaultVisualizer (e.g. S2 L2A True color).
		 *
		 * rangeOverrides is an array of 3 arrays which contain lower and upper range value and
		 * must be set in evalscriptoverrides in order to be used here.
		 * Lowest possible value is 0 and highest possible value is 1.
		 *
		 * Visualizer's process() must be called with both value and index: process(value, index).
		 * In most cases the map() will be used on components, example: components.map((v, i) => process(v, i)).
		 */
		if (typeof rangeOverrides !== 'undefined' && rangeOverrides !== null && rangeOverrides[i] !== undefined) {
			v = colorBlend(
				v,
				[rangeOverrides[i][0], rangeOverrides[i][1]],
				[0, 1]
			);
		}
		if (this.gamma != 1.0) {
			v = Math.pow(Math.max(0, v), this.gamma);
		}

		if (this.highlightAdjust && v > this.highlightPoint) {
			v = this.clamp(this.highlightPoint + (v - this.highlightPoint) * this.highlightFactor, 0.0, 1.0);
		}
		return this.clamp(v, 0.0, 1.0);
	}

	processList(components) {
		return components.map((v, i) => process(v, i));
	}
}
export class HighlightCompressVisualizerSingle {
	constructor(minValue = 0.0, maxValue = 1.0, gain = 1.0, offset = 0.0, gamma = 1.0) {
		this.minValue = minValue;
		this.maxValue = maxValue;
		this.gain = gainOverride || gain;
		this.offset = offsetOverride || offset;
		this.gamma = gammaOverride || gamma;

		this.highlightPoint = 0.92;
		this.highlightAdjust = 0 < maxValue && maxValue < 1;

		this.factor = 1.0 / (maxValue - minValue);
		this.clipPoint = 2.0;
		this.highlightFactor = (1.0 - this.highlightPoint) / (this.clipPoint - this.highlightPoint);
	}

	clamp(num, min, max) {
		return Math.max(Math.min(num, max), min);
	}

	process(val) {
		let v = this.gain * (val - this.minValue) * this.factor + this.offset
		if (this.gamma != 1.0) {
			v = Math.pow(Math.max(0, v), this.gamma);
		}

		if (this.highlightAdjust && v > this.highlightPoint) {
			v = this.clamp(this.highlightPoint + (v - this.highlightPoint) * this.highlightFactor, 0.0, 1.0);
		}
		return [this.clamp(v, 0.0, 1.0)];
	}

	processList(components) {
		return components.map(v => process(v));
	}
}
export class Identity {
	process(val) {
		if (Array.isArray(val)) {
			return val;
		}
		return [val];
	}
}

export function colorMap(value, limits, colors) {
	if ((limits == null) || (colors == null) || (limits.constructor !== Array) || (colors.constructor !== Array)) {
		return value;
	}
	for (var i = 0; i < limits.length; i++) {
		if (value < limits[i]) {
			return colors[i];
		}
	}
	return colors[colors.length - 1];
}


export function colorBlend(value, limits, colors) {
	if ((limits == null) || (colors == null) || (limits.constructor !== Array) || (colors.constructor !== Array)) {
		return value;
	}

	var prevLimit = (limits.length > 0) ? limits[0] : 0;
	if (value <= prevLimit) {
		return colors[0];
	}

	for (var limitIndex = 1; limitIndex < limits.length; limitIndex++) {
		var nextLimit = limits[limitIndex];
		if (value <= nextLimit) {
			var ratio = (value - prevLimit) / (nextLimit - prevLimit);

			var color = colors[limitIndex - 1];
			var color2 = colors[limitIndex];

			if (!isNaN(color)) {
				color = color * (1 - ratio) + color2 * ratio;
			}
			else if (color.constructor === Array) {
				for (var compIndex = 0; compIndex < color.length; compIndex++) {
					color[compIndex] = color[compIndex] * (1 - ratio) + color2[compIndex] * ratio;
				}
			}
			else {
				throw "\"colors\" must be an array containing either numbers, or arrays of numbers";
			}

			return color;
		}
		else {
			prevLimit = nextLimit;
		}
	}
	return colors[colors.length - 1];
}

export function decodeLs8Qa(value) {
	var designatedFill = value & 1
	var terrainOcclusion = (value >> 1) & 1
	var radiometricSaturation = (value >> 2) & 3
	var cloud = (value >> 4) & 1
	var cloudConfidence = (value >> 5) & 3
	var cloudShadowConfidence = (value >> 7) & 3
	var snowIceConfidence = (value >> 9) & 3
	var cirrusConfidence = (value >> 11) & 3

	return {
		designatedFill,
		terrainOcclusion,
		radiometricSaturation,
		cloud,
		cloudConfidence,
		cloudShadowConfidence,
		snowIceConfidence,
		cirrusConfidence
	}
}

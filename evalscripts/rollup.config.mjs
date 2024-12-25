import { globSync } from 'glob';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

let input = Object.fromEntries(
	globSync('skeletons/*.js').map(file => [
		// This remove `src/` as well as the file extension from each
		// file, so e.g. src/nested/foo.js becomes nested/foo
		path.relative(
			'skeletons',
			file.slice(0, file.length - path.extname(file).length)
		),
		// This expands the relative paths to absolute paths, so e.g.
		// src/nested/foo becomes /project/src/nested/foo.js
		fileURLToPath(new URL(file, import.meta.url))
	]))
var out = []
for (const [key, value] of Object.entries(input)) {
	out.push({
		input: {[key]: value},
		output: {
			dir: '../src/disturbancemonitor/data',
			format: 'cjs',
			strict: false,
			entryFileNames: "[name].cjs",
		},
		treeshake: false
	})
  }

// rollup.config.mjs
export default out;

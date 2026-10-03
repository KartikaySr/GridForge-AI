import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import assert from 'node:assert/strict';
import openapiTS, { astToString, COMMENT_HEADER } from 'openapi-typescript';
import prettier from 'prettier';

for (const name of ['runtime', 'cloud']) {
  const output = fileURLToPath(
    new URL(`./${name}.generated.ts`, import.meta.url),
  );
  const schema = new URL(`./${name}.openapi.json`, import.meta.url);
  const generated = COMMENT_HEADER + astToString(await openapiTS(schema));
  const formatted = await prettier.format(generated, {
    ...(await prettier.resolveConfig(output)),
    filepath: output,
  });
  assert.equal(
    await readFile(output, 'utf8'),
    formatted,
    `Generated ${name} types drifted; run npm run contracts:generate`,
  );
}
console.log('Generated runtime and cloud contract types match OpenAPI.');

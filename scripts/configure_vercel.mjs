// Run before deployment once the separately hosted portal origin is known.
import { readFileSync, writeFileSync } from 'node:fs';
const input = process.env.GRIDFORGE_PORTAL_ORIGIN;
if (!input)
  throw new Error(
    'Set GRIDFORGE_PORTAL_ORIGIN to the hosted HTTPS portal origin.',
  );
const origin = new URL(input);
if (
  origin.protocol !== 'https:' ||
  origin.username ||
  origin.password ||
  origin.pathname !== '/' ||
  origin.search ||
  origin.hash
)
  throw new Error(
    'Use an HTTPS origin without credentials, path, query, or fragment.',
  );
const file = new URL('../vercel.json', import.meta.url);
const config = JSON.parse(readFileSync(file, 'utf8'));
if (config.services) {
  throw new Error(
    'Services mode routes directly to portal. Do not configure an external API rewrite.',
  );
}
config.rewrites = [
  { source: '/api/:path*', destination: `${origin.origin}/api/:path*` },
  { source: '/((?!api/).*)', destination: '/index.html' },
];
writeFileSync(file, JSON.stringify(config, null, 2) + '\n');
console.log(
  'Configured same-origin API forwarding in vercel.json. Review before deploying.',
);

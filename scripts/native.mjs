// Use normal rustup by default, or this checkout's isolated toolchain if present.
import { existsSync } from 'node:fs';
import { delimiter, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('../', import.meta.url));
const cargoHome = join(root, '.tooling', 'cargo');
const rustupHome = join(root, '.tooling', 'rustup');
const environment = { ...process.env };
if (
  existsSync(
    join(
      cargoHome,
      'bin',
      process.platform === 'win32' ? 'cargo.exe' : 'cargo',
    ),
  )
) {
  environment.CARGO_HOME = cargoHome;
  environment.RUSTUP_HOME = rustupHome;
  environment.PATH = `${join(cargoHome, 'bin')}${delimiter}${environment.PATH ?? ''}`;
}
function run(command, args) {
  const result = spawnSync(command, args, {
    cwd: root,
    env: environment,
    stdio: 'inherit',
  });
  if (result.error) {
    console.error(
      'Native tooling could not start. Install the pinned Rust toolchain; see DEVELOPMENT.md.',
    );
    process.exit(1);
  }
  if (result.status !== 0) process.exit(result.status ?? 1);
}
const mode = process.argv[2];
if (mode === 'audit') {
  run('cargo', ['audit', '--file', 'apps/desktop/src-tauri/Cargo.lock']);
} else if (mode === 'check') {
  const manifest = ['--manifest-path', 'apps/desktop/src-tauri/Cargo.toml'];
  run('cargo', ['fmt', ...manifest, '--check']);
  run('cargo', [
    'clippy',
    ...manifest,
    '--locked',
    '--all-targets',
    '--',
    '-D',
    'warnings',
  ]);
  run('cargo', ['test', ...manifest, '--locked']);
} else if (mode === 'dev' || mode === 'build' || mode === 'package') {
  if (!process.env.npm_execpath)
    throw new Error('Use npm run desktop:native or npm run desktop:build');
  if (mode === 'package')
    run('uv', ['run', 'python', '-m', 'scripts.package_runtime']);
  const args =
    mode === 'dev'
      ? ['dev']
      : mode === 'package'
        ? ['build', '--config', 'src-tauri/tauri.release.conf.json']
        : ['build', '--debug', '--no-bundle'];
  run(process.execPath, [
    process.env.npm_execpath,
    '--workspace',
    'apps/desktop',
    'run',
    'tauri',
    '--',
    ...args,
  ]);
} else {
  throw new Error('Expected native command: dev, build or check');
}

// Fails when a fresh build of the source differs from the chrome-extension/ folder in Git.
import { execSync } from 'node:child_process';

const git = (args) => execSync(`git ${args} -- ../chrome-extension`, { encoding: 'utf8' }).trim();

execSync('npm run build:extension', { stdio: 'inherit' });
// Files the build changed or removed, then files it added that Git does not know.
const changed = [git('diff --name-only'), git('ls-files --others --exclude-standard')]
  .filter(Boolean)
  .join('\n');
if (changed) {
  console.error(`chrome-extension/ is out of date. Commit the rebuilt files:\n${changed}`);
  process.exit(1);
}
console.log('chrome-extension/ matches the source.');

"""Opt-in disposable AM2 entry-disable/re-enable release patch rehearsal; no DB access."""
import argparse
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
PAGE = 'apps/desktop/src/renderer/domains/android/pages/AndroidPage.tsx'
TEST = 'apps/desktop/src/renderer/domains/android/tests/AndroidPage.test.tsx'
CANDIDATES = [f'apps/desktop/src/renderer/domains/android/{name}' for name in [
    'components/BulkActions.tsx', 'components/ImageManager.tsx',
    'tests/ManagementTools.test.tsx', 'tests/ImageManager.test.tsx',
]]
CHECK = '''

it('QA AM2 forward entry rollback retains basic management', async () => {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(<QueryClientProvider client={client}><AndroidPage /></QueryClientProvider>)
  await screen.findByText('实例管理')
  await waitFor(() => expect(client.isFetching()).toBe(0))
  const disabled = process.env.AUTOFLOW_QA_ENTRY_DISABLED === '1'
  for (const name of ['镜像管理', '设备模板']) {
    if (disabled) expect(screen.queryByRole('heading', { name })).not.toBeInTheDocument()
    else expect(screen.getByRole('heading', { name })).toBeVisible()
  }
  expect(screen.getByRole('button', { name: /打开测试设备 01/ })).toBeEnabled()
  expect(mocks.client.request.mock.calls.some(([, init]) => init?.method && init.method !== 'GET')).toBe(false)
})
'''


def exercise(output):
    parent = Path(tempfile.mkdtemp(prefix='autoflow-am2-forward-entry-'))
    checkout = parent / 'checkout'
    report = {'status': 'started', 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'checkout': str(checkout), 'databaseAccess': False, 'commands': []}

    def run(name, args, expected=0, disabled=None, cwd=checkout):
        env = {**os.environ}
        if disabled is not None:
            env['AUTOFLOW_QA_ENTRY_DISABLED'] = '1' if disabled else '0'
        with (output / f'{name}.log').open('w') as log:
            completed = subprocess.run(args, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT, check=False)
        report['commands'].append({'name': name, 'argv': args, 'exit': completed.returncode})
        assert completed.returncode == expected, (name, completed.returncode, expected)

    test = ['npm', 'exec', '--offline', '--yes', '--package=node@22.23.2', '-c', 'npm test -w @autoflow/desktop -- src/renderer/domains/android/tests/AndroidPage.test.tsx -t "QA AM2 forward entry rollback"']
    build = ['npm', 'exec', '--offline', '--yes', '--package=node@22.23.2', '-c', 'npm run typecheck && npm run build']
    added = False
    try:
        run('checkout', ['git', 'worktree', 'add', '--detach', str(checkout), report['head']], cwd=ROOT)
        added = True
        for directory in ['node_modules', 'apps/desktop/node_modules']:
            (checkout / directory).symlink_to(ROOT / directory, target_is_directory=True)
        candidate = subprocess.check_output(['git', 'diff', '--binary', 'HEAD', '--', *CANDIDATES], cwd=ROOT)
        (output / 'candidate.patch').write_bytes(candidate)
        if candidate:
            run('candidate-apply', ['git', 'apply', str(output / 'candidate.patch')])
        report['candidateHashes'] = {name: hashlib.sha256((checkout / name).read_bytes()).hexdigest() for name in CANDIDATES}
        assert all(value == hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name, value in report['candidateHashes'].items())
        original = (checkout / PAGE).read_bytes()
        report['pageHashBefore'] = hashlib.sha256(original).hexdigest()
        migrations = {str(path.relative_to(checkout)): hashlib.sha256(path.read_bytes()).hexdigest() for path in (checkout / 'apps/backend/src/autoflow/infrastructure/database/migrations').rglob('*.py')}
        with (checkout / TEST).open('a') as stream:
            stream.write(CHECK)
        (output / 'component-check.tsx').write_text(CHECK)
        run('enabled-before', test, disabled=False)
        run('disabled-red', test, expected=1, disabled=True)
        changed = original.decode()
        for line in ["import { ImageManager } from '../components/ImageManager'\n", "import { TemplateManager } from '../components/TemplateManager'\n", '<ImageManager api={managementApi} />', '<TemplateManager api={{ ...fleet, images: managementApi.images, archiveProfile: managementApi.archiveProfile }} />']:
            assert changed.count(line) == 1, line
            changed = changed.replace(line, '')
        (checkout / PAGE).write_text(changed)
        patch = subprocess.check_output(['git', 'diff', '--binary', '--', PAGE], cwd=checkout)
        (output / 'disable-am2-entry.patch').write_bytes(patch)
        run('disabled-green', test, disabled=True)
        run('disabled-build', build)
        run('restore-check', ['git', 'apply', '--reverse', '--check', str(output / 'disable-am2-entry.patch')])
        run('restore', ['git', 'apply', '--reverse', str(output / 'disable-am2-entry.patch')])
        assert (checkout / PAGE).read_bytes() == original
        run('restored-green', test, disabled=False)
        run('restored-build', build)
        assert all(hashlib.sha256((checkout / name).read_bytes()).hexdigest() == value for name, value in migrations.items())
        assert all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value for name, value in report['candidateHashes'].items())
        report.update(status='passed', pageHashAfter=hashlib.sha256((checkout / PAGE).read_bytes()).hexdigest(), originalMigrationFilesUnchanged=len(migrations), candidateFilesUnchanged=len(CANDIDATES))
    except BaseException as error:
        report.update(status='failed', errorType=type(error).__name__)
        raise
    finally:
        try:
            if added:
                run('remove-owned-checkout', ['git', 'worktree', 'remove', '--force', str(checkout)], cwd=ROOT)
        except BaseException as error:
            report.update(status='cleanup_failed', cleanupErrorType=type(error).__name__)
            raise
        finally:
            report['ownedCheckoutRemoved'] = not checkout.exists()
            (output / 'result.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--allow-rehearsal', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.allow_rehearsal:
        parser.error('--allow-rehearsal is required to create a disposable checkout')
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    exercise(destination)

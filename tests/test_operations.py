"""Offline regression checks for publishing safeguards and delivery integrity."""
import base64
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import subprocess
import tempfile
import unittest
import zipfile
from datetime import date
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts'


def module(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


push = module('push_via_api')
package = module('package_release')
collector = module('collect')


class RepositoryCase(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for target in (push, package):
            mocked = patch.object(target, 'ROOT', self.root)
            mocked.start()
            self.addCleanup(mocked.stop)
        self.git('init', '-b', 'main')
        self.git('config', 'user.name', 'Offline Test')
        self.git('config', 'user.email', 'offline@example.invalid')
        self.git('config', 'core.autocrlf', 'false')
        self.git('remote', 'add', 'origin', 'https://github.com/uestc-aic/uestc-aic.github.io.git')
        for name in sorted(push.ESSENTIAL_FILES | {'notes.txt', '.github/workflows/pages.yml'}):
            self.write(name, 'original\n')
        self.git('add', '.')
        self.git('commit', '-m', 'fixture')
        self.head = self.git('rev-parse', 'HEAD').strip()
        self.remote = copy.deepcopy(push.collect_local())
        self.calls = []

    def git(self, *args):
        result = subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)
        return result.stdout.decode('utf-8')

    def write(self, name, content):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='\n')

    def api(self, args, body=None):
        self.calls.append((args, body))
        endpoint = args[0]
        if endpoint.endswith('/git/ref/heads/main'):
            return {'object': {'sha': self.head}}
        if endpoint.endswith('/git/commits/' + self.head):
            return {'tree': {'sha': 'old-tree'}}
        if '/git/trees/old-tree?' in endpoint:
            return {'truncated': False, 'tree': [dict(item, path=name, type='blob') for name, item in self.remote.items()]}
        if endpoint.endswith('/git/blobs'):
            data = base64.b64decode(body['content'])
            return {'sha': hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()}
        if endpoint.endswith('/git/trees'):
            return {'sha': 'new-tree'}
        if endpoint.endswith('/git/commits'):
            return {'sha': 'new-commit'}
        if endpoint.endswith('/git/refs/heads/main'):
            return {'object': {'sha': body['sha']}}
        raise AssertionError(endpoint)

    def run_push(self, *args, api=None):
        with patch.object(push, 'gh', side_effect=api or self.api), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return push.main(['--message', 'offline test', *args])

    def mutations(self):
        return [body for args, body in self.calls if body is not None]


class PushSafeguards(RepositoryCase):
    def test_archive_without_git_stops_before_network(self):
        other = self.root / 'archive'
        other.mkdir()
        with patch.object(push, 'ROOT', other):
            self.assertEqual(self.run_push(), 1)
        self.assertEqual(self.calls, [])

    def test_empty_repository_stops_before_network(self):
        other = self.root / 'empty'
        other.mkdir()
        subprocess.run(['git', 'init', '-b', 'main', str(other)], check=True, capture_output=True)
        with patch.object(push, 'ROOT', other):
            self.assertEqual(self.run_push(), 1)
        self.assertEqual(self.calls, [])

    def test_git_query_failure_cannot_become_empty_list(self):
        original = push.git
        def failing(args):
            if args[0] == 'ls-files':
                raise RuntimeError('fixture: Git query failed')
            return original(args)
        with patch.object(push, 'git', side_effect=failing):
            self.assertEqual(self.run_push(), 1)
        self.assertEqual(self.calls, [])

    def test_stale_local_commit_prevents_upload(self):
        def api(args, body=None):
            response = self.api(args, body)
            if args[0].endswith('/git/ref/heads/main'):
                response['object']['sha'] = 'newer-remote-commit'
            return response
        self.assertEqual(self.run_push(api=api), 1)
        self.assertEqual(self.mutations(), [])

    def test_wrong_origin_prevents_network(self):
        self.git('remote', 'set-url', 'origin', 'https://github.com/another/repository.git')
        self.assertEqual(self.run_push(), 1)
        self.assertEqual(self.calls, [])

    def test_truncated_remote_tree_prevents_upload(self):
        def api(args, body=None):
            response = self.api(args, body)
            if 'truncated' in response:
                response['truncated'] = True
            return response
        self.assertEqual(self.run_push(api=api), 1)
        self.assertEqual(self.mutations(), [])

    def test_critical_file_cannot_be_deleted_even_with_flag(self):
        self.git('rm', 'docs/index.html')
        self.assertEqual(self.run_push('--allow-delete'), 1)
        self.assertEqual(self.calls, [])

    def test_deletion_requires_explicit_flag(self):
        self.git('rm', 'notes.txt')
        self.assertEqual(self.run_push(), 0)
        self.assertEqual(self.mutations(), [])
        self.assertEqual(self.run_push('--allow-delete'), 0)
        trees = [body for args, body in self.calls if args[0].endswith('/git/trees')]
        self.assertEqual(trees[-1]['tree'], [{'path': 'notes.txt', 'mode': '100644', 'type': 'blob', 'sha': None}])

    def test_only_staged_version_is_uploaded(self):
        self.write('notes.txt', 'approved staged version\n')
        self.git('add', 'notes.txt')
        self.write('notes.txt', 'later unstaged edits\n')
        self.write('untracked.txt', 'not approved for upload\n')
        self.assertEqual(self.run_push(), 0)
        blobs = [body for args, body in self.calls if args[0].endswith('/git/blobs')]
        self.assertEqual(len(blobs), 1)
        self.assertEqual(base64.b64decode(blobs[0]['content']), b'approved staged version\n')
        updates = [body for args, body in self.calls if args[0].endswith('/git/refs/heads/main')]
        self.assertIs(updates[-1]['force'], False)

    def test_workflow_files_are_preserved(self):
        self.git('rm', '.github/workflows/pages.yml')
        self.assertEqual(self.run_push('--allow-delete'), 0)
        self.assertEqual(self.mutations(), [])

    def test_dry_run_performs_no_mutations(self):
        self.write('notes.txt', 'new\n')
        self.git('add', 'notes.txt')
        self.assertEqual(self.run_push('--dry-run'), 0)
        self.assertEqual(self.mutations(), [])

    def test_bad_blob_hash_never_updates_branch(self):
        self.write('notes.txt', 'new\n')
        self.git('add', 'notes.txt')
        def api(args, body=None):
            response = self.api(args, body)
            return {'sha': 'incorrect'} if args[0].endswith('/git/blobs') else response
        self.assertEqual(self.run_push(api=api), 1)
        self.assertFalse(any(args[0].endswith('/git/refs/heads/main') for args, _ in self.calls))


class DeliveryIntegrity(RepositoryCase):
    def test_round_trip_excludes_untracked_files_and_git_history(self):
        self.write('private-untracked.txt', 'fixture only')
        archive = self.root / 'delivery.zip'
        count = package.make_package(archive)
        self.assertEqual(package.verify_package(archive), count)
        with zipfile.ZipFile(archive) as source:
            self.assertNotIn(package.PREFIX + 'private-untracked.txt', source.namelist())
            self.assertFalse(any('/.git/' in name for name in source.namelist()))
        self.assertTrue(archive.with_name('delivery.zip.sha256').exists())

    def test_modified_file_fails_verification(self):
        good, bad = self.root / 'good.zip', self.root / 'bad.zip'
        package.make_package(good)
        with zipfile.ZipFile(good) as source, zipfile.ZipFile(bad, 'w') as target:
            for name in source.namelist():
                target.writestr(name, b'tampered' if name.endswith('/notes.txt') else source.read(name))
        with self.assertRaises(ValueError):
            package.verify_package(bad)

    def test_unlisted_extra_file_fails_verification(self):
        archive = self.root / 'delivery.zip'
        package.make_package(archive)
        with zipfile.ZipFile(archive, 'a') as target:
            target.writestr(package.PREFIX + 'extra.txt', 'not in manifest')
        with self.assertRaises(ValueError):
            package.verify_package(archive)


class CollectorBehavior(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        for attr, value in [('COLLECTED_DIR', str(self.root)), ('STATE_FILE', str(self.root / '_state.json')), ('ANOMALY_FILE', str(self.root / '_anomalies.json')), ('STATS', {})]:
            mocked = patch.object(collector, attr, value)
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_unchanged_items_do_not_rewrite_published_json(self):
        source = {'id': 'fixture', 'name': 'Fixture', 'url': 'https://example.invalid/news', 'enabled': True}
        old = {'source_id': 'fixture', 'source_name': 'Fixture', 'source_url': source['url'], 'fetched_at': 'original timestamp', 'items': []}
        output = self.root / 'fixture.json'
        output.write_text(json.dumps(old), encoding='utf-8')
        before = output.read_bytes()
        args = type('Args', (), {'dry_run': False, 'verbose': False})()
        with patch.object(collector, 'load_robots', return_value=(None, 0)), patch.object(collector, 'fetch', return_value=(b'fixture', 200, {})), patch.object(collector, 'decode_html', return_value=('fixture', 'utf-8')), patch.object(collector, 'container_present', return_value=True), patch.object(collector, 'compile_patterns', return_value={}), patch.object(collector, 'parse_items', return_value=[]), contextlib.redirect_stdout(io.StringIO()):
            collector.process_source(source, {}, args, date(2026, 10, 16), set(), set())
        self.assertEqual(output.read_bytes(), before)

    def test_all_sources_failed_stops_automatic_publish(self):
        config = {'sources': [{'id': 'fixture', 'enabled': True}]}
        def failed(source, *_):
            collector.STATS[source['id']] = {'health': 'failing'}
        with patch.object(collector, 'load_json', return_value=config), patch.object(collector, 'build_locked_index', return_value=(set(), set())), patch.object(collector, 'process_source', side_effect=failed), patch.object(collector, 'print_summary'), patch.object(collector, 'update_state'), contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(collector.main([]), 1)

    def test_new_item_is_written_once_and_dry_run_is_read_only(self):
        source = {'id': 'fixture', 'name': 'Fixture', 'url': 'https://example.invalid/news', 'enabled': True}
        item = {'title': 'New public notice', 'url': source['url'] + '/1', 'date_text': '2026-10-15', 'category': 'campus'}
        args = type('Args', (), {'dry_run': True, 'verbose': False})()
        with patch.object(collector, 'load_robots', return_value=(None, 0)), patch.object(collector, 'fetch', return_value=(b'fixture', 200, {})), patch.object(collector, 'decode_html', return_value=('fixture', 'utf-8')), patch.object(collector, 'container_present', return_value=True), patch.object(collector, 'compile_patterns', return_value={}), patch.object(collector, 'parse_items', side_effect=lambda *a, **k: [copy.deepcopy(item)]), contextlib.redirect_stdout(io.StringIO()):
            collector.process_source(source, {}, args, date(2026, 10, 16), set(), set())
            self.assertEqual(list(self.root.iterdir()), [])
            args.dry_run = False
            collector.process_source(source, {}, args, date(2026, 10, 16), set(), set())
            output = self.root / 'fixture.json'
            initial = output.read_bytes()
            self.assertEqual(len(json.loads(initial)['items']), 1)
            collector.process_source(source, {}, args, date(2026, 10, 16), set(), set())
            self.assertEqual(output.read_bytes(), initial)

    def test_one_healthy_source_allows_build(self):
        config = {'sources': [{'id': 'fixture', 'enabled': True}]}
        def healthy(source, *_):
            collector.STATS[source['id']] = {'health': 'ok'}
        with patch.object(collector, 'load_json', return_value=config), patch.object(collector, 'build_locked_index', return_value=(set(), set())), patch.object(collector, 'process_source', side_effect=healthy), patch.object(collector, 'print_summary'), patch.object(collector, 'update_state'), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(collector.main([]), 0)


if __name__ == '__main__':
    unittest.main()

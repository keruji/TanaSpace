"""Check the read-only VPS inspection using mocked Docker and HTTP commands."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class ProductionInspectionTests(unittest.TestCase):
    def inspect(self, mode):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            state = root / "state"
            state.mkdir()
            image_id = "sha256:" + "a" * 64
            (state / "current-image").write_text("tanaspace:current\n")
            (state / "current-image-id").write_text(image_id + "\n")
            script = Path(__file__).with_name("inspect-production.sh").read_text()
            script = script.replace("release_state=/home/keruji/.local/state/tanaspace",
                                    "release_state=" + str(state))
            (root / "inspect.sh").write_text(script)
            binaries = root / "bin"
            binaries.mkdir()
            mock_script = '''#!/usr/bin/env python3
import os, pathlib, sys
name = pathlib.Path(sys.argv[0]).name
mode = os.environ['INSPECTION_MODE']
with open(os.environ['CALL_LOG'], 'a') as log:
    log.write(name + ' ' + ' '.join(sys.argv[1:]) + '\\n')
if name == 'docker':
    assert sys.argv[1] in ('inspect', 'image'), 'Unexpected Docker mutation'
    template = sys.argv[-1]
    if 'revision' in template:
        print('missing' if mode == 'unknown_commit' else 'b' * 40)
    elif '.State.Running' in template:
        print('false' if mode == 'stopped' else 'true')
    else:
        value = 'c' if mode == 'image_mismatch' and sys.argv[1] == 'inspect' else 'a'
        print('sha256:' + value * 64)
else:
    if mode == 'network_failure': sys.exit(7)
    bad = mode == 'health_failure' and sys.argv[-1].endswith('/health/')
    bad = bad or mode == 'asset_failure' and sys.argv[-1].endswith('/static/app.css')
    print('503' if bad else '200', end='')
'''
            for name in ["docker", "curl"]:
                executable = binaries / name
                executable.write_text(mock_script)
                executable.chmod(0o700)
            env = dict(os.environ, PATH=str(binaries) + ":" + os.environ["PATH"],
                       INSPECTION_MODE=mode, CALL_LOG=str(root / "calls"))
            result = subprocess.run(
                ["bash", str(root / "inspect.sh"), "d" * 40, str(root),
                 "https://example.invalid"], env=env, text=True, capture_output=True,
                timeout=10,
            )
            calls = (root / "calls").read_text()
            self.assertNotIn("docker compose", calls)
            self.assertNotIn("docker run", calls)
            return result

    def test_healthy_production_emits_matching_metadata(self):
        result = self.inspect("healthy")
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["outcome"], "unchanged_healthy")
        self.assertEqual(report["current_commit"], "b" * 40)
        self.assertTrue(report["health_ok"])
        self.assertTrue(report["assets_ok"])

    def test_unhealthy_or_unknown_production_emits_no_report(self):
        for mode in ["stopped", "image_mismatch", "unknown_commit",
                     "health_failure", "asset_failure", "network_failure"]:
            with self.subTest(mode=mode):
                result = self.inspect(mode)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()

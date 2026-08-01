import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parents[1]


class ProjectStatePushGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tempdir = tempfile.TemporaryDirectory(prefix="project state 门禁 ")
        cls.root = Path(cls.tempdir.name)
        cls.base_env = os.environ.copy()
        cls.base_env["GIT_CONFIG_NOSYSTEM"] = "1"
        cls.base_env["GIT_CONFIG_GLOBAL"] = str(cls.root / "empty-global.gitconfig")
        (cls.root / "empty-global.gitconfig").write_text("")

    @classmethod
    def tearDownClass(cls):
        cls.tempdir.cleanup()

    def run_command(self, command, cwd, *, input_text="", env=None):
        return subprocess.run(
            command,
            cwd=cwd,
            input=input_text,
            text=True,
            capture_output=True,
            env=env or self.base_env,
            check=False,
        )

    def git(self, repo, *args, env=None):
        result = self.run_command(["git", *args], repo, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def create_repo(self, name="repo"):
        repo = Path(tempfile.mkdtemp(prefix=f"{name}-", dir=self.root))
        self.git(repo, "init", "-q")
        self.git(repo, "config", "user.name", "Push Gate Fixture")
        self.git(repo, "config", "user.email", "push-gate@example.test")
        for relative in [
            ".githooks/pre-push",
            "scripts/check-project-state-push.sh",
            "scripts/install-git-hooks.sh",
        ]:
            source = SOURCE_ROOT / relative
            target = repo / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            target.chmod(0o755)
        self.write(repo, "docs/PROJECT_STATE.md", "# Project\n\nFixture\n")
        self.write(repo, "README.md", "fixture\n")
        self.git(repo, "add", ".")
        self.git(repo, "commit", "-qm", "baseline\n\nProject-State-Review: updated")
        return repo

    def write(self, repo, relative, content):
        target = repo / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)

    def commit(self, repo, message, changes):
        for relative, content in changes.items():
            target = repo / relative
            if content is None:
                target.unlink()
            else:
                self.write(repo, relative, content)
        self.git(repo, "add", "-A")
        self.git(repo, "commit", "-qm", message)
        return self.git(repo, "rev-parse", "HEAD")

    def oid(self, repo, ref="HEAD"):
        return self.git(repo, "rev-parse", ref)

    @staticmethod
    def zero_oid(oid):
        return "0" * len(oid)

    @staticmethod
    def ref_line(local_ref, local_oid, remote_ref, remote_oid):
        return f"{local_ref} {local_oid} {remote_ref} {remote_oid}"

    def check(self, repo, lines):
        input_text = "\n".join(lines)
        if input_text:
            input_text += "\n"
        return self.run_command(["sh", "scripts/check-project-state-push.sh"], repo, input_text=input_text)

    def assert_ok(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)

    def assert_rejected(self, result, message):
        self.assertNotEqual(result.returncode, 0, message)

    def test_existing_branch_without_state_diff_requires_verified_current(self):
        repo = self.create_repo()
        baseline = self.oid(repo)
        tip = self.commit(
            repo,
            "non-state change\n\nProject-State-Review: verified-current",
            {"README.md": "updated\n"},
        )
        self.assert_ok(self.check(repo, [self.ref_line("refs/heads/main", tip, "refs/heads/main", baseline)]))

    def test_state_add_modify_and_delete_require_updated(self):
        for name, baseline_state, next_state in [
            ("added", None, "new state\n"),
            ("modified", "old state\n", "new state\n"),
            ("deleted", "old state\n", None),
        ]:
            with self.subTest(name=name):
                repo = self.create_repo(name)
                if baseline_state is None:
                    (repo / "docs/PROJECT_STATE.md").unlink()
                    self.git(repo, "add", "-A")
                    self.git(repo, "commit", "-qm", "remove state\n\nProject-State-Review: verified-current")
                else:
                    self.write(repo, "docs/PROJECT_STATE.md", baseline_state)
                    self.git(repo, "add", "docs/PROJECT_STATE.md")
                    self.git(repo, "commit", "-qm", "set state\n\nProject-State-Review: verified-current")
                baseline = self.oid(repo)
                tip = self.commit(
                    repo,
                    f"{name}\n\nProject-State-Review: updated",
                    {"docs/PROJECT_STATE.md": next_state},
                )
                self.assert_ok(self.check(repo, [self.ref_line("refs/heads/main", tip, "refs/heads/main", baseline)]))

    def test_rejects_missing_repeated_invalid_and_mis_cased_trailers(self):
        for name, message in [
            ("missing", "missing trailer"),
            ("repeated", "repeat\n\nProject-State-Review: updated\nProject-State-Review: updated"),
            ("invalid", "invalid\n\nProject-State-Review: stale"),
            ("mis-cased", "case\n\nproject-state-review: updated"),
        ]:
            with self.subTest(name=name):
                repo = self.create_repo(name)
                baseline = self.oid(repo)
                tip = self.commit(repo, message, {"docs/PROJECT_STATE.md": f"{name}\n"})
                result = self.check(repo, [self.ref_line("refs/heads/main", tip, "refs/heads/main", baseline)])
                self.assert_rejected(result, name)
                self.assertIn("Project-State-Review", result.stderr)

    def test_accepts_git_normalized_whitespace(self):
        repo = self.create_repo()
        baseline = self.oid(repo)
        tip = self.commit(repo, "spaces\n\nProject-State-Review:   updated", {"docs/PROJECT_STATE.md": "changed\n"})
        self.assert_ok(self.check(repo, [self.ref_line("refs/heads/main", tip, "refs/heads/main", baseline)]))

    def test_rejects_mismatch_and_body_trailer_spoofing(self):
        repo = self.create_repo("mismatch")
        baseline = self.oid(repo)
        mismatch = self.commit(
            repo,
            "wrong\n\nProject-State-Review: verified-current",
            {"docs/PROJECT_STATE.md": "changed\n"},
        )
        result = self.check(repo, [self.ref_line("refs/heads/main", mismatch, "refs/heads/main", baseline)])
        self.assert_rejected(result, "mismatch")
        self.assertIn("expected updated", result.stderr)

        spoof_repo = self.create_repo("spoof")
        spoof_base = self.oid(spoof_repo)
        spoof = self.commit(
            spoof_repo,
            "body\n\nProject-State-Review: updated\n\nnot a trailer block",
            {"docs/PROJECT_STATE.md": "changed\n"},
        )
        result = self.check(spoof_repo, [self.ref_line("refs/heads/main", spoof, "refs/heads/main", spoof_base)])
        self.assert_rejected(result, "body spoof")
        self.assertIn("Project-State-Review", result.stderr)

    def test_checks_only_the_tip_trailer(self):
        repo = self.create_repo()
        baseline = self.oid(repo)
        self.commit(repo, "earlier\n\nProject-State-Review: updated", {"docs/PROJECT_STATE.md": "first\n"})
        tip = self.commit(repo, "tip without trailer", {"README.md": "changed\n"})
        result = self.check(repo, [self.ref_line("refs/heads/main", tip, "refs/heads/main", baseline)])
        self.assert_rejected(result, "tip trailer")
        self.assertIn("Project-State-Review", result.stderr)

    def test_uses_empty_tree_for_first_push_and_skips_branch_delete_and_empty_input(self):
        repo = self.create_repo()
        tip = self.oid(repo)
        zero = self.zero_oid(tip)
        self.assert_ok(self.check(repo, [self.ref_line("refs/heads/main", tip, "refs/heads/main", zero)]))
        self.assert_ok(self.check(repo, [self.ref_line("refs/heads/main", zero, "refs/heads/main", tip)]))
        self.assert_ok(self.check(repo, []))

    def test_accepts_lightweight_and_annotated_commit_tags(self):
        repo = self.create_repo()
        head = self.oid(repo)
        self.git(repo, "tag", "lightweight", head)
        self.git(repo, "tag", "-a", "annotated", "-m", "annotated", head)
        lightweight = self.oid(repo, "refs/tags/lightweight")
        annotated = self.oid(repo, "refs/tags/annotated")
        zero = self.zero_oid(lightweight)
        self.assert_ok(self.check(repo, [
            self.ref_line("refs/tags/lightweight", lightweight, "refs/tags/lightweight", zero),
            self.ref_line("refs/tags/annotated", annotated, "refs/tags/annotated", zero),
        ]))

    def test_rejects_non_commit_tags_and_skips_tag_deletion(self):
        repo = self.create_repo()
        tree = self.oid(repo, "HEAD^{tree}")
        self.git(repo, "tag", "-a", "tree-tag", "-m", "tree", tree)
        tag = self.oid(repo, "refs/tags/tree-tag")
        zero = self.zero_oid(tag)
        result = self.check(repo, [self.ref_line("refs/tags/tree-tag", tag, "refs/tags/tree-tag", zero)])
        self.assert_rejected(result, "non-commit tag")
        self.assertIn("commit", result.stderr)
        self.assert_ok(self.check(repo, [self.ref_line("refs/tags/tree-tag", zero, "refs/tags/tree-tag", tag)]))

    def test_fails_closed_for_unknown_namespace_missing_remote_and_bad_multi_ref(self):
        repo = self.create_repo()
        head = self.oid(repo)
        unknown = self.check(repo, [self.ref_line("refs/notes/test", head, "refs/notes/test", self.zero_oid(head))])
        self.assert_rejected(unknown, "unknown namespace")
        missing = self.check(repo, [self.ref_line("refs/heads/main", head, "refs/heads/main", "f" * len(head))])
        self.assert_rejected(missing, "missing remote object")
        self.assertIn("synchronize local Git objects", missing.stderr)
        bad_tip = self.commit(repo, "bad tip", {"docs/PROJECT_STATE.md": "changed\n"})
        multi = self.check(repo, [
            self.ref_line("refs/heads/good", head, "refs/heads/good", head),
            self.ref_line("refs/heads/bad", bad_tip, "refs/heads/bad", head),
        ])
        self.assert_rejected(multi, "multi ref failure")

    def test_rejects_conflicting_branch_expectations_regardless_of_input_order(self):
        for reverse in [False, True]:
            with self.subTest(reverse=reverse):
                repo = self.create_repo("conflict")
                baseline = self.oid(repo)
                tip = self.commit(repo, "changed\n\nProject-State-Review: updated", {"docs/PROJECT_STATE.md": "changed\n"})
                lines = [
                    self.ref_line("refs/heads/current", tip, "refs/heads/current", tip),
                    self.ref_line("refs/heads/updated", tip, "refs/heads/updated", baseline),
                ]
                if reverse:
                    lines.reverse()
                result = self.check(repo, lines)
                self.assert_rejected(result, "conflicting branch expectations")
                self.assertIn("conflicting Project-State-Review expectations", result.stderr)
                self.assertIn("refs/heads/current", result.stderr)
                self.assertIn("refs/heads/updated", result.stderr)

    def test_accepts_compliant_multi_ref_branch_and_tag_push(self):
        repo = self.create_repo()
        baseline = self.oid(repo)
        tip = self.commit(repo, "state\n\nProject-State-Review: updated", {"docs/PROJECT_STATE.md": "changed\n"})
        self.git(repo, "tag", "release", tip)
        tag = self.oid(repo, "refs/tags/release")
        self.assert_ok(self.check(repo, [
            self.ref_line("refs/heads/main", tip, "refs/heads/main", baseline),
            self.ref_line("refs/heads/release", tip, "refs/heads/release", baseline),
            self.ref_line("refs/tags/release", tag, "refs/tags/release", self.zero_oid(tag)),
        ]))

    def test_rejects_whole_multi_ref_push_when_one_branch_fails(self):
        repo = self.create_repo()
        baseline = self.oid(repo)
        valid = self.commit(repo, "valid\n\nProject-State-Review: verified-current", {"README.md": "valid\n"})
        failing = self.commit(repo, "bad\n\nProject-State-Review: verified-current", {"docs/PROJECT_STATE.md": "changed\n"})
        result = self.check(repo, [
            self.ref_line("refs/heads/valid", valid, "refs/heads/valid", baseline),
            self.ref_line("refs/heads/failing", failing, "refs/heads/failing", valid),
        ])
        self.assert_rejected(result, "invalid multi ref")
        self.assertIn("refs/heads/failing", result.stderr)
        self.assertIn("expected updated", result.stderr)

    def test_uses_final_tree_comparison_for_force_pushes(self):
        repo = self.create_repo()
        baseline = self.oid(repo)
        tip = self.commit(repo, "force\n\nProject-State-Review: updated", {"docs/PROJECT_STATE.md": "force tree\n"})
        self.assert_ok(self.check(repo, [self.ref_line("refs/heads/main", tip, "refs/heads/main", baseline)]))

    def test_real_pre_push_accepts_then_rejects_in_unicode_space_path(self):
        repo = self.create_repo("真实 push 验证")
        remote = self.root / "bare remote.git"
        self.git(self.root, "init", "--bare", "-q", str(remote))
        self.git(repo, "config", "core.hooksPath", ".githooks")
        self.git(repo, "remote", "add", "origin", str(remote))
        pushed = self.run_command(["git", "push", "origin", "HEAD:refs/heads/main"], repo)
        self.assert_ok(pushed)
        pushed_head = self.oid(repo)
        rejected = self.commit(repo, "bad\n\nProject-State-Review: verified-current", {"docs/PROJECT_STATE.md": "changed\n"})
        result = self.run_command(["git", "push", "origin", "HEAD:refs/heads/main"], repo)
        self.assert_rejected(result, "real pre-push rejection")
        self.assertIn("expected updated", result.stderr)
        self.assertEqual(self.git(remote, "rev-parse", "refs/heads/main"), pushed_head)
        self.assertNotEqual(rejected, pushed_head)

    def test_install_script_is_safe_idempotent_and_refuses_conflicts(self):
        installed = self.create_repo("install")
        default_hooks = list((installed / ".git/hooks").iterdir())
        first = self.run_command(["sh", "scripts/install-git-hooks.sh"], installed)
        second = self.run_command(["sh", "scripts/install-git-hooks.sh"], installed)
        self.assertTrue(all(path.name.endswith(".sample") for path in default_hooks))
        self.assert_ok(first)
        self.assertEqual(self.git(installed, "config", "--local", "--get", "core.hooksPath"), ".githooks")
        self.assert_ok(second)

        configured = self.create_repo("configured")
        self.git(configured, "config", "--local", "core.hooksPath", "custom-hooks")
        result = self.run_command(["sh", "scripts/install-git-hooks.sh"], configured)
        self.assert_rejected(result, "local hooksPath conflict")
        self.assertIn("hooksPath", result.stderr)

        global_repo = self.create_repo("global-config")
        global_config = self.root / "conflicting-global.gitconfig"
        global_config.write_text("[core]\n\thooksPath = global-hooks\n")
        global_env = self.base_env.copy()
        global_env["GIT_CONFIG_GLOBAL"] = str(global_config)
        result = self.run_command(["sh", "scripts/install-git-hooks.sh"], global_repo, env=global_env)
        self.assert_rejected(result, "global hooksPath conflict")
        self.assertIn("hooksPath", result.stderr)

        non_executable = self.create_repo("non-executable")
        (non_executable / "scripts/check-project-state-push.sh").chmod(stat.S_IRUSR | stat.S_IWUSR)
        result = self.run_command(["sh", "scripts/install-git-hooks.sh"], non_executable)
        self.assert_rejected(result, "non executable checker")
        self.assertIn("check script is not executable", result.stderr)

        custom_hook = self.create_repo("default-hook")
        hook = custom_hook / ".git/hooks/pre-commit"
        hook.write_text("#!/bin/sh\nexit 0\n")
        hook.chmod(0o755)
        result = self.run_command(["sh", "scripts/install-git-hooks.sh"], custom_hook)
        self.assert_rejected(result, "default hook conflict")
        self.assertIn("custom hook", result.stderr)


if __name__ == "__main__":
    unittest.main()

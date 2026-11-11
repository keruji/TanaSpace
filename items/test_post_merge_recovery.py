import os

from django.test import SimpleTestCase


class PostMergeRecoveryTest(SimpleTestCase):
    def test_intentional_post_merge_failure(self):
        is_main_push = (
            os.environ.get("GITHUB_EVENT_NAME") == "push"
            and os.environ.get("GITHUB_REF") == "refs/heads/main"
        )

        self.assertFalse(
            is_main_push,
            "Intentional post-merge failure to test repository recovery.",
        )
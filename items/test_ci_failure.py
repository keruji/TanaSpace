from django.test import SimpleTestCase


class CIPipelineFailureTest(SimpleTestCase):
    def test_intentional_failure(self):
        self.fail("Intentional failure to verify that CI blocks merging.")

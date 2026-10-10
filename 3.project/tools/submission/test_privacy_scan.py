import unittest
from tools.submission.privacy_scan import inspect_emails


class EmailPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.policy = {
            'example_domains': ['example.com', 'company.local'],
            'service_examples': [{'path': 'service.py', 'local_part': 'onboarding', 'domain': 'resend.dev'}],
        }

    def test_personal_and_arbitrary_public_addresses_are_flagged_and_redacted(self):
        addresses = ['developer' + '@' + 'gmail.com', 'person' + '@' + 'customer.co.kr']
        count, findings = inspect_emails('\n'.join(addresses), 'screen.tsx', self.policy)
        self.assertEqual(count, 2)
        self.assertEqual([item['line'] for item in findings], [1, 2])
        self.assertTrue(all(item['rule'] == 'NON_EXAMPLE_EMAIL' for item in findings))
        self.assertNotIn(addresses[0], str(findings))

    def test_declared_examples_and_subdomains_are_allowed(self):
        count, findings = inspect_emails('name@example.com\nuser@sub.example.com\nowner@company.local', 'fixture.py', self.policy)
        self.assertEqual(count, 3)
        self.assertEqual(findings, [])

    def test_example_domain_substring_is_not_an_allowlist_bypass(self):
        _, findings = inspect_emails('name' + '@' + 'example.com.attacker.co.kr', 'screen.tsx', self.policy)
        self.assertEqual(len(findings), 1)

    def test_service_example_exception_is_scoped_to_its_file(self):
        address = 'onboarding' + '@' + 'resend.dev'
        self.assertEqual(inspect_emails(address, 'service.py', self.policy)[1], [])
        self.assertEqual(len(inspect_emails(address, 'screen.tsx', self.policy)[1]), 1)


if __name__ == '__main__':
    unittest.main()

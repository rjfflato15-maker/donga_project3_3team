"""Flag undeclared literal email addresses without exposing their values."""
import re

EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@([A-Za-z0-9.-]+\.[A-Za-z]{2,})\b")


def inspect_emails(text, path, policy):
    examples = {domain.lower() for domain in policy['example_domains']}
    service_examples = {
        (item['path'], item['local_part'].lower() + '@' + item['domain'].lower())
        for item in policy['service_examples']
    }
    matches, findings = 0, []
    for match in EMAIL.finditer(text):
        matches += 1
        domain = match.group(1).lower()
        allowed_domain = any(domain == example or domain.endswith('.' + example) for example in examples)
        if allowed_domain or (path, match.group(0).lower()) in service_examples:
            continue
        findings.append({'path': path, 'line': text.count('\n', 0, match.start()) + 1, 'rule': 'NON_EXAMPLE_EMAIL'})
    return matches, findings

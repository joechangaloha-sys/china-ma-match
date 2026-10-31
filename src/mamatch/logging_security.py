"""Keep activation bearer tokens out of HTTP access logs without disabling access logs."""
import logging
import re


class SensitivePathFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple) and len(record.args) == 5:
            values = list(record.args)
            values[2] = re.sub(r'/account/activate/[A-Za-z0-9_-]+', '/account/activate/[redacted]', str(values[2]))
            record.args = tuple(values)
        return True

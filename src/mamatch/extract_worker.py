"""Private bounded text-parser process. Not a web route or a scanner."""
import resource
import sys
from pathlib import Path


def main():
    if sys.platform == "linux":
        resource.setrlimit(resource.RLIMIT_AS, (512 * 1024 * 1024, 512 * 1024 * 1024))
    resource.setrlimit(resource.RLIMIT_CPU, (10, resource.getrlimit(resource.RLIMIT_CPU)[1]))
    from .documents import _read_text_untrusted
    sys.stdout.write(_read_text_untrusted(Path(sys.argv[1]))[:200000])


if __name__ == '__main__':
    main()

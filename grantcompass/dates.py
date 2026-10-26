"""Date formatting that works on every operating system.

strftime's "%-d" (day without a leading zero) works on macOS and Linux but raises an error on Windows,
so dates are formatted through dfmt, which fills in the day itself."""


def dfmt(d, fmt: str) -> str:
    """d.strftime(fmt), where %-d means the day of the month without a leading zero."""
    return d.strftime(fmt.replace("%-d", str(d.day)))

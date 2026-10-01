"""A test is an `it(` or `test(` call, never a method that happens to end in one."""

from desloppify.languages.typescript.test_coverage import TEST_FUNCTION_RE


def test_counts_it_and_test_calls():
    source = "it('adds', () => {})\n  test(\"subtracts\", () => {})\n"
    assert len(TEST_FUNCTION_RE.findall(source)) == 2


def test_ignores_split_and_regexp_test():
    source = "sql.split('--> statement-breakpoint')\n/^\\d/.test('1')\nsubmit('x')\n"
    assert TEST_FUNCTION_RE.findall(source) == []

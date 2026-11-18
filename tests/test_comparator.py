from app.modules.judge.sandbox.comparator import compare_output, normalize_output


def test_normalize_output_strips_trailing_spaces_and_crlf():
    assert normalize_output("3  \r\n4\t\r\n\r\n") == "3\n4"


def test_compare_output_ignores_trailing_whitespace():
    assert compare_output("3   \n4\n", "3\n4")


def test_compare_output_detects_difference():
    assert not compare_output("3\n5\n", "3\n4\n")


def test_compare_output_keeps_inner_spaces():
    assert not compare_output("3  4\n", "3 4\n")

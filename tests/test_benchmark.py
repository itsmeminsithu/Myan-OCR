from scripts.benchmark import edit_distance, normalized

def test_distance():
    assert edit_distance('abc','abc') == 0
    assert edit_distance('abc','abd') == 1
    assert edit_distance('','abc') == 3
    assert normalized('e\u0301') == 'é'

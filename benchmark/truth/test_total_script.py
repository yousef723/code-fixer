import runpy

def test_it(capsys):
    runpy.run_path("solution.py")
    assert capsys.readouterr().out == "Total: 10\n"

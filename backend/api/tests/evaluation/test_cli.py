from evaluation.cli import main
from openpyxl import load_workbook


def test_template_command(tmp_path):
    assert main(["template", "--output", str(tmp_path)]) == 0
    assert load_workbook(tmp_path / "report.xlsx").sheetnames
    assert load_workbook(tmp_path / "dataset.xlsx")["Dataset"].max_row == 1


def test_missing_dataset_is_error(tmp_path):
    assert main(["validate", "--dataset", str(tmp_path / "absent.json")]) == 2

"""Проверки CSV-ассемблера по спецификации варианта 15."""

import subprocess
import tempfile
import unittest
from pathlib import Path

from src.assembler import AssemblyError, Instruction, assemble


ROOT = Path(__file__).resolve().parents[1]
SPECIFICATION = ROOT / "tests" / "specification.csv"
EXPECTED = [(5, 338), (9, 722), (1, 123), (7, 577)]


class AssemblerTests(unittest.TestCase):
    def test_specification_program(self):
        with SPECIFICATION.open(encoding="utf-8", newline="") as source:
            self.assertEqual(assemble(source), EXPECTED)

    def test_csv_quotes_spaces_and_empty_lines(self):
        program = ['"LOAD_CONST","338"\n', " \n", " NEG , 0 \n"]
        expected = [Instruction(5, 338), Instruction(7, 0)]
        self.assertEqual(assemble(program), expected)

    def test_field_limits(self):
        limits = [
            ("LOAD_CONST", 5, 131071),
            ("READ_MEM", 9, 8191),
            ("WRITE_MEM", 1, 8191),
            ("NEG", 7, 262143),
        ]
        for name, opcode, maximum in limits:
            with self.subTest(command=name):
                self.assertEqual(
                    assemble([f"{name},{maximum}"]),
                    [Instruction(opcode, maximum)],
                )
                with self.assertRaisesRegex(AssemblyError, "вне диапазона"):
                    assemble([f"{name},{maximum + 1}"])

    def test_invalid_program(self):
        bad_operand = "поле B должно быть целым числом без знака"
        cases = [
            ("UNKNOWN,1", "неизвестная команда"),
            ("LOAD_CONST", "ожидаются два поля"),
            ("NEG,1,2", "ожидаются два поля"),
            ("WRITE_MEM,", bad_operand),
            ("READ_MEM,-1", bad_operand),
            ("READ_MEM,1.5", bad_operand),
            ('NEG,"577', "неверный CSV"),
        ]
        for line, message in cases:
            with self.subTest(line=line):
                with self.assertRaisesRegex(
                    AssemblyError, f"строка 3: {message}"
                ):
                    assemble(["LOAD_CONST,1\n", "\n", line])

    def test_cli_in_test_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "program.bin"
            result = subprocess.run(
                [ROOT / "run.sh", SPECIFICATION, destination, "--test"],
                cwd=directory,
                capture_output=True,
                text=True,
                check=True,
            )
            expected = [f"A={a}, B={b}" for a, b in EXPECTED]
            self.assertEqual(result.stdout.splitlines(), expected)
            self.assertEqual(result.stderr, "")
            self.assertFalse(destination.exists())

    def test_cli_in_normal_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "program.bin"
            destination.write_bytes(b"existing")
            result = subprocess.run(
                [ROOT / "run.sh", SPECIFICATION, destination],
                cwd=directory,
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(result.stdout, "")
            self.assertEqual(result.stderr, "")
            self.assertEqual(destination.read_bytes(), b"existing")

    def test_cli_rejects_invalid_program(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "invalid.csv"
            source.write_text("LOAD_CONST,1\nNEG,262144\n", encoding="utf-8")
            result = subprocess.run(
                [ROOT / "run.sh", source, "program.bin", "--test"],
                cwd=directory,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout, "")
            self.assertIn("строка 2: поле B вне диапазона", result.stderr)

"""Проверки интерпретатора через командную строку."""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUN = ROOT / "run.sh"
COPY_ARRAY = ROOT / "tests" / "copy_array.csv"
NEGATION = ROOT / "tests" / "negation.csv"


class InterpreterTests(unittest.TestCase):
    """Собирает и выполняет программы во временной папке."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.directory = Path(directory.name)
        self.source = self.directory / "program.csv"
        self.program = self.directory / "program.bin"
        self.dump = self.directory / "memory.json"

    def assemble(self, source: Path) -> None:
        """Запустить ассемблер через общий скрипт запуска."""
        subprocess.run(
            [RUN, source, self.program.name],
            cwd=self.directory,
            capture_output=True,
            check=True,
        )

    def assemble_text(self, source: str) -> None:
        """Записать исходный текст программы и собрать его."""
        self.source.write_text(source, encoding="utf-8")
        self.assemble(self.source)

    def interpret(
        self, start: int, end: int
    ) -> subprocess.CompletedProcess[str]:
        """Выполнить двоичный файл и сохранить дамп выбранных адресов."""
        return subprocess.run(
            [
                RUN, "--interpret", self.program.name, self.dump.name,
                str(start), str(end),
            ],
            cwd=self.directory,
            capture_output=True,
            text=True,
            check=False,
        )

    def assert_memory(self, expected: dict[str, int]) -> None:
        """Сравнить содержимое JSON с ожидаемым снимком памяти."""
        data = json.loads(self.dump.read_text(encoding="utf-8"))
        self.assertEqual(data, expected)

    def test_copy_array(self):
        self.assemble(COPY_ARRAY)
        result = self.interpret(100, 107)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_memory({
            "100": 37, "101": 0, "102": 338, "103": 131071,
            "104": 37, "105": 0, "106": 338, "107": 131071,
        })

    def test_negation_program(self):
        self.assemble(NEGATION)
        result = self.interpret(200, 203)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_memory({"200": -37, "201": 0, "202": 37, "203": -131071})

    def test_negation_uses_full_address_and_pops_one_value(self):
        for address in (0, 262143):
            with self.subTest(address=address):
                self.assemble_text(
                    f"LOAD_CONST,100\nLOAD_CONST,33\nNEG,{address}\n"
                    "LOAD_CONST,7\nWRITE_MEM,0\n"
                )
                result = self.interpret(address, address)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_memory({str(address): -33})
                result = self.interpret(100, 100)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_memory({"100": 7})

    def test_negates_vector_examples_in_place(self):
        """Сравнить дампы до и после вычисления для трёх векторов."""
        vectors = {
            "positive": [1, 2, 3, 4, 5, 6, 131071],
            "negative": [-9, -1, -34, -128, -577, -12, -131071],
            "mixed": [0, -14, 21, -338, 0, 57, -2],
        }
        for kind, values in vectors.items():
            with self.subTest(vector=kind):
                source = ROOT / "tests" / f"negate_vector_{kind}.csv"
                program = source.read_text(encoding="utf-8")
                setup = program.split("\n\n", maxsplit=1)[0]
                addresses = map(str, range(99, 108))
                before = dict(zip(addresses, [0, *values, 0]))
                after = {address: -value for address, value in before.items()}

                self.assemble_text(setup)
                result = self.interpret(99, 107)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_memory(before)

                self.assemble(source)
                result = self.interpret(99, 107)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assert_memory(after)

    def test_reads_and_executes_words_in_shared_memory(self):
        self.assemble_text(
            "LOAD_CONST,100\nLOAD_CONST,0\nREAD_MEM,0\nWRITE_MEM,0\n"
            "LOAD_CONST,101\nLOAD_CONST,8\nLOAD_CONST,117\nWRITE_MEM,0\n"
            "NEG,0\nWRITE_MEM,0\n"
        )
        result = self.interpret(100, 101)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_memory({"100": 1605, "101": 7})

    def test_maximum_read_and_write_offsets(self):
        self.assemble_text(
            "LOAD_CONST,100\nLOAD_CONST,42\nWRITE_MEM,8191\n"
            "LOAD_CONST,101\nLOAD_CONST,100\nREAD_MEM,8191\nWRITE_MEM,8191\n"
        )
        result = self.interpret(8290, 8292)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_memory({"8290": 0, "8291": 42, "8292": 42})

    def test_empty_program_and_single_address(self):
        self.program.write_bytes(b"")
        result = self.interpret(0, 0)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assert_memory({"0": 0})

    def test_invalid_dump_range(self):
        self.program.write_bytes(b"")
        for start, end in [(-1, 0), (4, 3)]:
            with self.subTest(start=start, end=end):
                result = self.interpret(start, end)
                self.assertEqual(result.returncode, 1)
                self.assertIn("диапазон адресов", result.stderr)
                self.assertFalse(self.dump.exists())

    def test_invalid_program_preserves_dump(self):
        cases = [
            ("05", "файл заканчивается неполной командой"),
            ("00 00 00", "адрес команды 0: неизвестный код операции"),
            ("05 00 20", "адрес команды 0: старшие биты команды"),
            ("09 00 00", "адрес команды 0: недостаточно элементов стека"),
            ("05 00 00 01 00 00", "адрес команды 1: недостаточно элементов"),
            ("17 24 00", "адрес команды 0: недостаточно элементов стека"),
        ]
        previous_dump = "{}\n"
        self.dump.write_text(previous_dump, encoding="utf-8")
        for hex_bytes, message in cases:
            with self.subTest(machine_code=hex_bytes):
                self.program.write_bytes(bytes.fromhex(hex_bytes))
                result = self.interpret(0, 0)
                self.assertEqual(result.returncode, 1)
                self.assertIn(message, result.stderr)
                self.assertEqual(self.dump.read_text(), previous_dump)

    def test_dump_path_cannot_replace_program(self):
        program = bytes.fromhex("25 15 00")
        self.program.write_bytes(program)
        self.dump = self.program
        result = self.interpret(0, 0)
        self.assertEqual(result.returncode, 1)
        self.assertIn(
            "пути программы и дампа должны различаться", result.stderr
        )
        self.assertEqual(self.program.read_bytes(), program)

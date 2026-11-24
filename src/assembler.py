"""Ассемблер учебной виртуальной машины, вариант 15.

В таблице COMMANDS каждой мнемонике соответствуют код операции A
и разрядность поля B.
"""

import argparse
import csv
from pathlib import Path
from typing import Iterable, NamedTuple


FIELDS_PER_INSTRUCTION = 2
COMMANDS = {
    "LOAD_CONST": (5, 17),
    "READ_MEM": (9, 13),
    "WRITE_MEM": (1, 13),
    "NEG": (7, 18),
}


class Instruction(NamedTuple):
    """Поля A (код операции) и B (операнд) одной команды."""

    a: int
    b: int


class AssemblyError(ValueError):
    """Ошибка в тексте программы."""


def parse_operand(text: str, bit_width: int) -> int:
    """Разобрать десятичный операнд и проверить разрядность поля B."""
    if not text.isascii() or not text.isdecimal():
        raise AssemblyError("поле B должно быть целым числом без знака")

    maximum = (1 << bit_width) - 1
    digits = text.lstrip("0") or "0"
    if len(digits) <= len(str(maximum)):
        value = int(digits)
        if value <= maximum:
            return value
    raise AssemblyError(f"поле B вне диапазона 0..{maximum}")


def parse_instruction(line: str) -> Instruction:
    """Преобразовать одну строку CSV в пару полей A и B."""
    try:
        fields = next(csv.reader([line], strict=True))
    except csv.Error as error:
        raise AssemblyError("неверный CSV") from error
    if len(fields) != FIELDS_PER_INSTRUCTION:
        raise AssemblyError("ожидаются два поля: команда,операнд")

    name, operand = (field.strip() for field in fields)
    if name not in COMMANDS:
        raise AssemblyError(f"неизвестная команда {name!r}")

    opcode, bit_width = COMMANDS[name]
    return Instruction(opcode, parse_operand(operand, bit_width))


def assemble(lines: Iterable[str]) -> list[Instruction]:
    """Разобрать программу, сохранив порядок команд из исходного файла."""
    instructions = []
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            instructions.append(parse_instruction(line))
        except AssemblyError as error:
            raise AssemblyError(f"строка {line_number}: {error}") from error
    return instructions


def main(argv: list[str] | None = None) -> int:
    """Запустить ассемблер из командной строки."""
    parser = argparse.ArgumentParser(description="Ассемблер УВМ, вариант 15.")
    parser.add_argument("source", type=Path, help="исходная программа в CSV")
    parser.add_argument(
        "output", type=Path, help="путь для бинарного файла с этапа 2"
    )
    parser.add_argument(
        "--test", action="store_true", help="вывести поля A и B каждой команды"
    )
    args = parser.parse_args(argv)

    try:
        with args.source.open(encoding="utf-8-sig", newline="") as source:
            instructions = assemble(source)
    except (AssemblyError, OSError, UnicodeError) as error:
        parser.exit(1, f"Ошибка: {error}\n")

    if args.test:
        for instruction in instructions:
            print(f"A={instruction.a}, B={instruction.b}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

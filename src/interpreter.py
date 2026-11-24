"""Интерпретатор учебной виртуальной машины, вариант 15."""

import argparse
import json
from pathlib import Path

from assembler import (
    BYTE_ORDER,
    COMMANDS,
    INSTRUCTION_SIZE,
    LOAD_CONST,
    NEG,
    OPCODE_BITS,
    READ_MEM,
    WRITE_MEM,
    Instruction,
    write_binary,
)


FIRST_ADDRESS = 0
OPCODE_MASK = (1 << OPCODE_BITS) - 1
OPERAND_WIDTHS = {opcode: width for opcode, width in COMMANDS.values()}


class ExecutionError(ValueError):
    """Ошибка машинной программы, операции с памятью или аргументов."""


def decode_instruction(word: int) -> Instruction:
    """Выделить поля A и B и проверить код операции и старшие биты."""
    opcode = word & OPCODE_MASK
    if opcode not in OPERAND_WIDTHS:
        raise ExecutionError(f"неизвестный код операции {opcode}")

    operand = word >> OPCODE_BITS
    if operand not in range(1 << OPERAND_WIDTHS[opcode]):
        raise ExecutionError("старшие биты команды должны быть нулевыми")
    return Instruction(opcode, operand)


def pop_address(stack: list[int], offset: int) -> int:
    """Снять базовый адрес со стека и прибавить смещение."""
    address = stack.pop() + offset
    if address < FIRST_ADDRESS:
        raise ExecutionError(f"отрицательный адрес памяти {address}")
    return address


def execute_instruction(
    instruction: Instruction, memory: dict[int, int], stack: list[int]
) -> None:
    """Выполнить одну команду над общей памятью и стеком."""
    opcode, operand = instruction
    if opcode == LOAD_CONST:
        stack.append(operand)
    elif opcode == READ_MEM:
        address = pop_address(stack, operand)
        stack.append(memory.get(address, 0))
    elif opcode == WRITE_MEM:
        value = stack.pop()
        address = pop_address(stack, operand)
        memory[address] = value
    elif opcode == NEG:
        memory[operand] = -stack.pop()
    else:
        raise ExecutionError(f"неизвестный код операции {opcode}")


def execute(program: bytes) -> dict[int, int]:
    """Загрузить машинные слова с адреса 0 и вернуть память после исполнения."""
    command_count, remainder = divmod(len(program), INSTRUCTION_SIZE)
    if remainder:
        raise ExecutionError("двоичный файл заканчивается неполной командой")

    offsets = range(0, len(program), INSTRUCTION_SIZE)
    memory = {
        address: int.from_bytes(
            program[offset : offset + INSTRUCTION_SIZE], byteorder=BYTE_ORDER
        )
        for address, offset in enumerate(offsets)
    }
    stack: list[int] = []
    for address in range(command_count):
        try:
            instruction = decode_instruction(memory[address])
            execute_instruction(instruction, memory, stack)
        except IndexError as error:
            message = f"адрес команды {address}: недостаточно элементов стека"
            raise ExecutionError(message) from error
        except ExecutionError as error:
            raise ExecutionError(f"адрес команды {address}: {error}") from error
    return memory


def main(argv: list[str] | None = None) -> int:
    """Выполнить программу из файла и сохранить выбранный диапазон в JSON."""
    parser = argparse.ArgumentParser(description="Интерпретатор УВМ.")
    parser.add_argument("program", type=Path, help="двоичный файл программы")
    parser.add_argument("dump", type=Path, help="выходной JSON-файл")
    parser.add_argument("start", type=int, help="начальный адрес дампа")
    parser.add_argument(
        "end", type=int, help="конечный адрес дампа включительно"
    )
    args = parser.parse_args(argv)

    try:
        if not FIRST_ADDRESS <= args.start <= args.end:
            raise ExecutionError(
                "ожидается диапазон адресов 0 <= начало <= конец"
            )
        if args.program.resolve() == args.dump.resolve():
            raise ExecutionError("пути программы и дампа должны различаться")
        memory = execute(args.program.read_bytes())
        addresses = range(args.start, args.end + 1)
        dump = {address: memory.get(address, 0) for address in addresses}
        text = json.dumps(dump, indent=2) + "\n"
        write_binary(args.dump, text.encode("utf-8"))
    except (ExecutionError, OSError) as error:
        parser.exit(1, f"Ошибка: {error}\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

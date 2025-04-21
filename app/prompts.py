is_v2 = True


def load_prompt_template():
    with open(
        f"prompt_template{is_v2 and '_v2' or ''}.txt", "r", encoding="utf-8"
    ) as file:
        return file.read()


def load_multi_character_prompt_template():
    with open(
        f"prompt_multi_character_template{is_v2 and '_v2' or ''}.txt",
        "r",
        encoding="utf-8",
    ) as file:
        return file.read()


def load_character_prompt():
    with open("prompt_character.txt", "r", encoding="utf-8") as file:
        return file.read()


def load_long_memory_summary_prompt():
    with open("prompt_long_memory_summary.txt", "r", encoding="utf-8") as file:
        return file.read()


def load_relationship_summary_prompt():
    with open("prompt_relationship_summary.txt", "r", encoding="utf-8") as file:
        return file.read()


def load_important_memory_extract_prompt():
    with open("prompt_important_memory_extract.txt", "r", encoding="utf-8") as file:
        return file.read()

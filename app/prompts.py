def load_prompt_template():
    with open("prompt_template.txt", "r", encoding="utf-8") as file:
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

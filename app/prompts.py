def load_prompt_template():
    with open("prompt_template.txt", "r", encoding="utf-8") as file:
        return file.read()

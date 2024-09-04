from typing import Optional, Union


class DialogueOption:
    next: Optional["DialogueNode"] = None
    chat: Optional[int] = None


def parse_option(
    option: dict,
    chats: dict[str, int],
    # Контекст (для ссылок)
    trees: dict[str, dict],
    tree_context: dict[str, "DialogueNode"],
) -> tuple[str, DialogueOption]:
    res = DialogueOption()
    if chat := option.get("chat"):
        res.chat = chats[chat]
    if next := option.get("next"):
        res.next = parse_tree(next, chats, trees, tree_context)
    return option["text"], res


class DialogueNode:
    question: str
    resend_question: Optional[str] = None
    result_type: Optional[str] = None
    field: Optional[str] = None
    next: Optional["DialogueNode"] = None

    options: Optional[dict[str, DialogueOption]] = None


def parse_tree(
    tree: Union[dict, str],
    chats: dict[str, int],
    # Контекст (для ссылок)
    trees: dict[str, dict],
    tree_context: dict[str, "DialogueNode"],
) -> DialogueNode:
    node = DialogueNode()
    if isinstance(tree, str):
        if tree_node := tree_context.get(tree):
            return tree_node
        else:
            tree_context[tree] = node

        tree_dict = trees[tree]
    else:
        tree_dict = tree

    node.question = tree_dict["question"]
    node.resend_question = tree_dict.get("resend_question")
    node.result_type = tree_dict.get("type")
    node.field = tree_dict.get("field")

    if next := tree_dict.get("next"):
        node.next = parse_tree(next, chats, trees, tree_context)

    if opts := tree_dict.get("options"):
        options = [parse_option(option, chats, trees, tree_context) for option in opts]
        node.options = {option[0]: option[1] for option in options}

    return node

user_conversations = {}

def append_to_history(user_id, role, content):
    """
    Maintains a short conversation history per user.
    """
    if user_id not in user_conversations:
        user_conversations[user_id] = []

    user_conversations[user_id].append({"role": role, "content": content})

    MAX_HISTORY_SIZE = 3
    if len(user_conversations[user_id]) > MAX_HISTORY_SIZE:
        user_conversations[user_id] = user_conversations[user_id][-MAX_HISTORY_SIZE:]

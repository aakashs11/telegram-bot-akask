from utils.screening import screen_message
from utils.common import append_to_history
from utils.openai_client import client
from functions.notes import get_notes
from functions.videos import get_videos
import json




tools = [
    {
        "type": "function",
        "function": {
            "name": "get_notes",
            "description": "Retrieve the link to required notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "class": {
                        "type": "string",
                        "enum": ["Class 10", "Class 11", "Class 12"],
                    },
                    "subject": {"type": "string", "enum": ["AI", "IT", "CS", "IP"]},
                    "type": {
                        "type": "string",
                        "enum": [
                            "Notes",
                            "Books",
                            "Syllabus",
                            "Sample Question Papers SQP",
                        ],
                    },
                },
                # "required": ["class", "subject"]
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_videos",
            "description": "Retrieve the links to required videos.",
            "parameters": {
                "type": "object",
                "properties": {
                    "topic": {
                        "type": "string",
                        # "enum": ["Class 10", "Class 11", "Class 12"],
                    }
                },
            },
            "required": ["query"],
        },
    },
]


# Classify intent function
async def classify_intent(query, user_id):
    output = {
        "output_screener": "",
        "output_intent": "",
        "output_entitites": "",
        "final_output": "",
    }

    if user_id not in user_conversations:
        user_conversations[user_id] = []
    user_history = user_conversations[user_id]

    message_result = await screen_message(query)
    message_is_valid = message_result["is_valid"]
    output["output_screener"] = message_is_valid
    if message_is_valid:
        append_to_history(user_id, "user", query)

        system_prompt = f"""
            CHECK CONVERSATION HISTORY BEFORE RESPONDING.
            You are ASK.ai a helpful assistant that provides notes and other asssistance based on user queries. 
            Greet the user with a message saying who you are. Solve doubts or help with notes adn other items.
            STRICTLY ask for missing details if required. STRICTLY DON'T ASSUME THE CLASS.
            STRICTLY Use get_notes tool if the intent is to get notes.
            STRICTLY Use get_videos tool if the intent is to get videos. 
            STRICTLY Keep responses under 30 words. Summarize where necessary as long messages will be truncated.

            """
        # Add initial system message for context
        if len(user_history) == 0:
            append_to_history(user_id, "system", system_prompt)

        # Get response from the model
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=user_history,
            tools=tools,
            max_tokens=200,
        )
        assistant_message = response.choices[0].message

        if assistant_message.tool_calls:
            tool_call = assistant_message.tool_calls[0]
            print("Tool is present", tool_call)
            if tool_call.function.name == "get_notes":
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    print("Arguments are:", arguments)
                    # Handle missing information
                    required_fields = ["type", "class", "subject"]
                    missing_info = [
                        field for field in required_fields if field not in arguments
                    ]
                    print("missing info", missing_info)
                    if missing_info:
                        prompt = f"Could you please specify the following: {', '.join(missing_info)}?"
                        append_to_history(user_id, "assistant", prompt)
                        output["final_output"] = prompt
                    else:
                        # Call the get_notes function
                        result = await get_notes(arguments)
                        append_to_history(user_id, "assistant", result)
                        output["final_output"] = result
                except json.JSONDecodeError as e:
                    output[
                        "final_output"
                    ] = "Error decoding function arguments. Please try again."
            elif tool_call.function.name == "get_videos":
                try:
                    arguments = json.loads(tool_call.function.arguments)
                    print("Arguments are:", arguments)
                    # Handle missing information
                    required_fields = ["topic"]
                    missing_info = [
                        field for field in required_fields if field not in arguments
                    ]
                    print("missing info", missing_info)
                    if missing_info:
                        prompt = f"Could you please specify the {', '.join(missing_info)}"
                        append_to_history(user_id, "assistant", prompt)
                        output["final_output"] = prompt
                    else:
                        # Call the get_notes function
                        result = await get_videos(arguments)
                        append_to_history(user_id, "assistant", result)
                        output["final_output"] = result
                except json.JSONDecodeError as e:
                    output[
                        "final_output"
                    ] = "Error decoding function arguments. Please try again."
            else:
                # append_to_history("assistant", "Unsupported function call.")
                output["final_output"] = "Unsupported function call."
        else:
            # Regular assistant message
            append_to_history(user_id, "assistant", assistant_message.content)
            output["final_output"] = assistant_message.content

    else:
        return "Please use respectful language. [Warning]"
    return output

async def classify_intent(query, user_id, sh):
    output = {
        "output_screener": "",
        "output_intent": "",
        "output_entitites": "",
        "final_output": "",
    }

    message_result = await screen_message(query)
    message_is_valid = message_result["is_valid"]
    output["output_screener"] = message_is_valid

    if not message_is_valid:
        output["final_output"] = "Please use respectful language. [Warning]"
        return output

    append_to_history(user_id, "user", query)
    system_prompt = """
        You are ASK.ai. Greet the user. Solve doubts, help with notes or videos.
        Ask for missing details if needed. Don't assume class.
        Use get_notes or get_videos tools when needed. 
        Keep responses under 30 words.
    """

    # Retrieve user history from `utils/common.user_conversations`
    from utils.common import user_conversations
    user_history = user_conversations.get(user_id, [])

    if len(user_history) == 0:
        append_to_history(user_id, "system", system_prompt)

    response = client  # Placeholder for actual call to your model that supports tools.
    # Pseudo-code: 
    # response = client.chat.completions.create(
    #     model="gpt-4o-mini",
    #     messages=user_history,
    #     tools=[...], # define your tools
    #     max_tokens=200,
    # )

    # This is where you'd handle tool calls like before.
    # For demonstration, let's assume response.tool_calls is available as before.

    # After processing response, populate output["final_output"] and others as needed.
    # This is a skeleton—you’ll adapt from your original logic.

    return output

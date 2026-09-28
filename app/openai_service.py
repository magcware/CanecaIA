from openai import OpenAI
from app.config import OPENAI_API_KEY
from app.prompts import SYSTEM_PROMPT

client = OpenAI(
    api_key=OPENAI_API_KEY
)

def classify_image(base64_image: str):

    response = client.responses.create(
        model="gpt-5",
        input=[
            {
                "role":"system",
                "content":SYSTEM_PROMPT
            },
            {
                "role":"user",
                "content":[
                    {
                        "type":"input_text",
                        "text":"Classify this waste"
                    },
                    {
                        "type":"input_image",
                        "image_url":f"data:image/jpeg;base64,{base64_image}"
                    }
                ]
            }
        ]
    )

    return response.output_text.strip()
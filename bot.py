from openai import OpenAI
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
import os


@dataclass_json
@dataclass
class BotData:
    name : str
    owner_id : int
    api : str
    model : str
    system_prompt : str
    sampling_parameters : dict = field(default_factory=dict)


class Bot:

    def __init__(self, **kwargs):

        if 'usermessages' in kwargs:
            self.usermessages = kwargs['usermessages']
            del kwargs['usermessages']
        else:
            self.usermessages = []

        

        self.bot_data = BotData(**kwargs)
        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )


    def get_completion(self, user_message):
        self.usermessages.append({"role": "user", "content": user_message})

        completion = self.client.chat.completions.create(
            model=self.bot_data.model,
            messages=[
                {
                    "role": "system",
                    "content": self.bot_data.system_prompt
                }
            ] + [ {"role": msg["role"], "content": msg["content"]} for msg in self.usermessages],
            **self.bot_data.sampling_parameters
        )

        reply = completion.choices[0].message.content
        self.usermessages.append({"role": "assistant", "content": reply})
        return reply
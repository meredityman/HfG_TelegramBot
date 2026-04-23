from openai import OpenAI
from dataclasses import dataclass, field
from dataclasses_json import dataclass_json
import os


@dataclass_json
@dataclass
class BotData:
    name : str
    owner_id : int
    message_history : list = field(default_factory=list)

class Bot:

    config_type = BotData

    def __init__(self, **kwargs):
        self.config = self.config_type(**kwargs)

    def get_completion(self, user_input):
        raise NotImplementedError("This method should be implemented by subclasses.")

@dataclass_json
@dataclass
class SimpleBotData(BotData):
    api : str = None
    model : str = None
    system_prompt : str = None
    sampling_parameters : dict = field(default_factory=dict)



class SimpleBot(Bot):

    config_type = SimpleBotData

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )

    def get_completion(self, user_message):
        self.config.message_history.append({"role": "user", "content": user_message})

        completion = self.client.chat.completions.create(
            model=self.config.model,
            messages=[
                {
                    "role": "system",
                    "content": self.config.system_prompt
                }
            ] + [ {"role": msg["role"], "content": msg["content"]} for msg in self.config.message_history],
            **self.config.sampling_parameters
        )

        reply = completion.choices[0].message.content
        self.config.message_history.append({"role": "assistant", "content": reply})
        return reply


@dataclass_json
@dataclass
class Group_1BotData(BotData):

    @dataclass_json
    @dataclass
    class Message:
        cont_message : str
        sampling_parameters : dict = field(default_factory=dict)
        

    cont_messages : list[Message] = field(default_factory=list)
    api : str = None
    model : str = None
    system_prompt : str = None



    
class Group_1(Bot):

    config_type = Group_1BotData

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        

        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_API_KEY"),
        )


        
    def get_completion(self, user_message):
        story = ""
        for m in self.config.cont_messages:
            m = self.config.Message(**m) if isinstance(m, dict) else m
            messages = [
                {
                    "role": "system",
                    "content": self.config.system_prompt
                }
            ]
            if story:
                messages.append({"role": "assistant", "content": story})

            messages.append({"role": "user", "content": m.cont_message})

            completion = self.client.chat.completions.create(
                model=self.config.model,
                messages=messages,
                **m.sampling_parameters

            )

            story += completion.choices[0].message.content
        return story
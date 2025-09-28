from dotenv import load_dotenv
import os
import openai
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from PyPDF2 import PdfReader
import gradio as gr
import asyncio
from pydantic import BaseModel
from openai import OpenAI

load_dotenv()  # Load environment variables from .env file
serper_api_key = os.getenv("SERPER_API_KEY")

def set_env():
    api_key = os.getenv("AZURE_OPENAI_API_KEY")
    deployment = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
    api_version = os.getenv("AZURE_OPENAI_API_VERSION")
    endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
    model = os.getenv("AZURE_OPENAI_MODEL")

    # Create the Azure OpenAI client
    az_model_client = AzureOpenAIChatCompletionClient(
        azure_deployment=deployment,
        model=model,
        api_version=api_version,
        azure_endpoint=endpoint,
        api_key=api_key,
    )
    client = openai.AzureOpenAI(
        api_version=api_version,
    )
 
    return az_model_client, client

def read_pdf(file_path):
    reader = PdfReader(file_path)
    text = ""
    for page in reader.pages:
        text += page.extract_text() + "\n"
    return text

def read_summary():
    with open  (r"web-chatbot\resources\summary.txt", "r") as file:
        summary = file.read()
    return summary


def set_system_prompt(name, summary, linkedin):
    system_prompt = f"You are acting as {name}. You are answering questions on {name}'s website, \
    particularly questions related to {name}'s career, background, skills and experience. \
    Your responsibility is to represent {name} for interactions on the website as faithfully as possible. \
    You are given a summary of {name}'s background and LinkedIn profile which you can use to answer questions. \
    Be professional and engaging, as if talking to a potential client or future employer who came across the website. \
    If you don't know the answer, say so."

    system_prompt += f"\n\n## Summary:\n{summary}\n\n## LinkedIn Profile:\n{linkedin}\n\n"
    system_prompt += f"With this context, please chat with the user, always staying in character as {name}."
    return system_prompt

def set_evaluator_prompt(name, summary, linkedin):
    evaluator_prompt = f"You are an expert interviewer evaluating the responses of {name}, \
    who is acting as an interviewee on their website. Your task is to assess whether {name}'s \
    responses are professional, engaging, and accurate based on the provided context. \
    You will provide a boolean evaluation and constructive feedback for improvement. \
    If you don't know the answer, say so."

    evaluator_prompt += f"\n\n## Summary:\n{summary}\n\n## LinkedIn Profile:\n{linkedin}\n\n"
    evaluator_prompt += f"With this context, please evaluate the interviewee's responses."
    return evaluator_prompt


def evaluator_user_prompt(reply, message, history):
    user_prompt = f"Here's the conversation between the User and the Agent: \n\n{history}\n\n"
    user_prompt += f"Here's the latest message from the User: \n\n{message}\n\n"
    user_prompt += f"Here's the latest response from the Agent: \n\n{reply}\n\n"
    user_prompt += "Please evaluate the response, replying with whether it is acceptable and your feedback."
    return user_prompt

name = "Ed Donner"  # Replace with the interviewee's name
summary = read_summary()  # Read the summary from the file
linkedin = read_pdf(r"D:\UdemyCourse_github\My-work-onThisCourse\agents_bee\web-chatbot\resources\linkedin.pdf")  # Read the LinkedIn profile from the PDF
system_prompt = set_system_prompt(name, summary, linkedin)
evaluate_prompt = set_evaluator_prompt(name, summary, linkedin)
az_model_client, client = set_env()

class Evaluation(BaseModel):
    is_acceptable: bool
    feedback: str


gemini = OpenAI(
    api_key=os.getenv("gemini_api_key"), 
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
)
def rerun(reply, message, history, feedback):
    updated_system_prompt = system_prompt + "\n\n## Previous answer rejected\nYou just tried to reply, but the quality control rejected your reply\n"
    updated_system_prompt += f"## Your attempted answer:\n{reply}\n\n"
    updated_system_prompt += f"## Reason for rejection:\n{feedback}\n\n"
    messages = [{"role": "system", "content": updated_system_prompt}] + history + [{"role": "user", "content": message}]
    response = openai.chat.completions.create(model="gpt-4o-mini", messages=messages)
    return response.choices[0].message.content

def chat(message, history):
    messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": message}]
    response = client.chat.completions.create(
        model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
        messages=messages
    )
    print("Response:", response.choices[0].message.content)
    messages = [{"role": "system", "content": evaluate_prompt}] + [{"role": "user", "content": evaluator_user_prompt(response, message, history)}]
    feedback = gemini.beta.chat.completions.parse(model="gemini-2.0-flash", messages=messages, response_format=Evaluation)
    print("\n Evaluation:", feedback.choices[0].message.parsed)
    if not feedback.choices[0].message.parsed.is_acceptable:
        return rerun(response.choices[0].message.content, message, history, feedback.choices[0].message.parsed.feedback)
    return response.choices[0].message.content

######################################Gemini Evaluator#########################################
# chat("Hello, can you tell me about your background?", [])

gr.ChatInterface(chat, type="messages").queue().launch()

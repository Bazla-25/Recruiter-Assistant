from dotenv import load_dotenv
import os
import openai
from autogen_ext.models.openai import AzureOpenAIChatCompletionClient
from PyPDF2 import PdfReader
import gradio as gr
import asyncio



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

name = "Ed Donner"  # Replace with the interviewee's name
summary = read_summary()  # Read the summary from the file
linkedin = read_pdf(r"D:\UdemyCourse_github\My-work-onThisCourse\agents_bee\web-chatbot\resources\linkedin.pdf")  # Read the LinkedIn profile from the PDF
system_prompt = set_system_prompt(name, summary, linkedin)
az_model_client, client = set_env()

def chat(message, history):
    try:
        messages = [{"role": "system", "content": system_prompt}] + history + [{"role": "user", "content": message}]
        response = client.chat.completions.create(
            model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
            messages=messages
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"An error occurred: {str(e)}"

def test_chat():
    try:
        response = chat("Hello", [])
        print(response)
    except Exception as e:
        print(f"Error: {e}")


gr.ChatInterface(chat, type="messages").queue().launch()
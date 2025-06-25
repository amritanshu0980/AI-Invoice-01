from google import genai

client = genai.Client(api_key="AIzaSyCUiNWMUB9u7LE5wczpPhL6RpTAhoM3Z5I")

response = client.models.generate_content(
    model="gemini-1.5-flash",
    contents="Explain how AI works",
)

print(response.text)
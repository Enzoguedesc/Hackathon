import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
API_KEY = os.getenv("GOOGLE_API_KEY")

if not API_KEY:
    print("Chave de API não encontrada no .env!")
else:
    try:
        print("Configurando API...")
        genai.configure(api_key=API_KEY)
        print("Criando modelo...")
        model = genai.GenerativeModel('gemini-pro') # Ou o modelo que você está usando
        print("Gerando conteúdo de teste...")
        response = model.generate_content("Olá, Gemini! Isso é um teste.")
        print("Resposta da API:", response.text)
    except Exception as e:
        print(f"ERRO NO TESTE DIRETO DA API: {e}")
import google.generativeai as genai

GEMINI_API_KEY = "AIzaSyD07vhyzXmzloH_R8oJyIqkwcjS3zwclIY"
genai.configure(api_key=GEMINI_API_KEY)

print("🔍 Listando modelos disponíveis:")
print("-" * 50)

for m in genai.list_models():
    if 'generateContent' in m.supported_generation_methods:
        print(f"✅ {m.name}")
        
print("\n🧪 Testando modelos:")
print("-" * 50)

modelos = [
    'gemini-2.0-flash-exp',
    'gemini-1.5-flash',
    'gemini-1.5-flash-latest',
    'gemini-1.5-pro',
    'gemini-pro'
]

for modelo in modelos:
    try:
        model = genai.GenerativeModel(modelo)
        response = model.generate_content("Oi")
        print(f"✅ {modelo} - FUNCIONOU!")
        print(f"   Resposta: {response.text[:50]}...")
        break
    except Exception as e:
        print(f"❌ {modelo} - Erro: {str(e)[:80]}")
import json
import os

# Obter o diretório atual
current_dir = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_PATH = os.path.join(current_dir, 'credentials.json')

# Ler o arquivo de credenciais
if os.path.exists(CREDENTIALS_PATH):
    with open(CREDENTIALS_PATH, 'r') as f:
        credentials = json.load(f)
    
    if 'client_email' in credentials:
        print("\n=== INFORMAÇÕES DA CONTA DE SERVIÇO ===")
        print(f"Email da conta de serviço: {credentials['client_email']}")
        print(f"ID do projeto: {credentials.get('project_id', 'Não disponível')}")
        print("\nPara resolver o erro de permissão:")
        print("1. Abra sua planilha do Google Sheets:")
        print("   https://docs.google.com/spreadsheets/d/1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc")
        print("2. Clique no botão 'Compartilhar' no canto superior direito")
        print("3. Adicione o email da conta de serviço acima")
        print("4. IMPORTANTE: Dê permissão de 'Editor' (não apenas 'Visualizador')")
        print("5. Desmarque a opção 'Notificar pessoas'")
        print("6. Clique em 'Enviar' ou 'Compartilhar'")
        print("\nDepois disso, execute novamente o aplicativo principal.")
    else:
        print("Erro: O arquivo de credenciais não contém o campo 'client_email'.")
else:
    print(f"Erro: Arquivo de credenciais não encontrado em {CREDENTIALS_PATH}") 
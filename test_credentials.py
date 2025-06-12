from utils.credentials_helper import get_credentials
from google.oauth2.service_account import Credentials
import os
import json

# Define scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def test_credentials():
    print("Testando obtenção de credenciais...")
    
    # Tenta obter credenciais
    credentials = get_credentials(SCOPES)
    
    if credentials:
        print("✅ Credenciais obtidas com sucesso!")
        
        # Verifica se as credenciais são válidas
        if isinstance(credentials, Credentials):
            print("✅ Tipo de credenciais correto: Credentials")
            print(f"✅ Client email: {credentials.service_account_email}")
            print(f"✅ Projeto: {credentials.project_id}")
        else:
            print("❌ Tipo de credenciais incorreto")
    else:
        print("❌ Falha ao obter credenciais")
        
        # Verifica se existe arquivo de credenciais
        current_dir = os.path.dirname(os.path.abspath(__file__))
        credentials_path = os.path.join(current_dir, 'credentials.json')
        
        if os.path.exists(credentials_path):
            print(f"✅ Arquivo de credenciais encontrado em: {credentials_path}")
            # Tenta carregar o arquivo para diagnóstico
            try:
                with open(credentials_path, 'r') as f:
                    credentials_data = json.load(f)
                print("✅ Arquivo de credenciais é um JSON válido")
                if 'client_email' in credentials_data:
                    print(f"✅ Client email no arquivo: {credentials_data['client_email']}")
                else:
                    print("❌ Client email não encontrado no arquivo de credenciais")
            except Exception as e:
                print(f"❌ Erro ao ler arquivo de credenciais: {str(e)}")
        else:
            print(f"❌ Arquivo de credenciais não encontrado em: {credentials_path}")
        
        # Verifica se existe variável de ambiente
        if 'GOOGLE_CREDENTIALS' in os.environ:
            print("✅ Variável de ambiente GOOGLE_CREDENTIALS encontrada")
            # Tenta carregar a variável de ambiente para diagnóstico
            try:
                credentials_data = json.loads(os.environ.get('GOOGLE_CREDENTIALS'))
                print("✅ Variável de ambiente GOOGLE_CREDENTIALS é um JSON válido")
                if 'client_email' in credentials_data:
                    print(f"✅ Client email na variável de ambiente: {credentials_data['client_email']}")
                else:
                    print("❌ Client email não encontrado na variável de ambiente")
            except Exception as e:
                print(f"❌ Erro ao processar variável de ambiente GOOGLE_CREDENTIALS: {str(e)}")
        else:
            print("❌ Variável de ambiente GOOGLE_CREDENTIALS não encontrada")

if __name__ == "__main__":
    test_credentials() 
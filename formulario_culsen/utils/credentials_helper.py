import os
import json
from google.oauth2.service_account import Credentials
import logging

# Configurar logger
logger = logging.getLogger('formulario_culsen.credentials_helper')

def get_credentials(scopes):
    """
    Obtém credenciais do Google a partir de:
    1. Variável de ambiente GOOGLE_CREDENTIALS (GitHub Secret)
    2. Arquivo credentials.json local
    
    Retorna um objeto Credentials ou None se não encontrar
    """
    try:
        # Primeiro, tenta usar variável de ambiente (GitHub Secret)
        if 'GOOGLE_CREDENTIALS' in os.environ:
            logger.info("Usando credenciais da variável de ambiente GOOGLE_CREDENTIALS")
            credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
            service_account_info = json.loads(credentials_json)
            return Credentials.from_service_account_info(service_account_info, scopes=scopes)
        
        # Se não encontrar, tenta usar arquivo local
        current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        credentials_path = os.path.join(current_dir, 'credentials.json')
        
        if os.path.exists(credentials_path):
            logger.info(f"Usando credenciais do arquivo: {credentials_path}")
            return Credentials.from_service_account_file(credentials_path, scopes=scopes)
        
        logger.error("Credenciais não encontradas na variável de ambiente nem no arquivo local")
        return None
    
    except Exception as e:
        logger.error(f"Erro ao obter credenciais: {str(e)}")
        return None 
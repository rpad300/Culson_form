import logging
import traceback
from utils.sheets import get_config
from utils.ia import get_gemini_key, get_openai_key, get_claude_key, get_deepseek_key
from utils.credentials_helper import get_credentials
import requests
import json
import google.generativeai as genai
import openai
import anthropic
from googleapiclient.discovery import build
from google.oauth2.service_account import Credentials
import os

# Configurar logger
logger = logging.getLogger('formulario_culsen.api_checker')

# Define scopes para Drive
DRIVE_SCOPES = ['https://www.googleapis.com/auth/drive.metadata.readonly']

def check_api_status():
    """
    Verifica o status de conexão com as diferentes APIs utilizadas pelo sistema
    Retorna um dicionário com o status de cada API
    """
    logger.info("Verificando status das APIs...")
    
    # Obter configurações
    config = get_config()
    
    # Resultado inicializado com erro para todas as APIs
    result = {
        "google_drive": {
            "status": False,
            "error": "Não testado"
        },
        "gemini": {
            "status": False,
            "error": "Não testado"
        },
        "openai": {
            "status": False,
            "error": "Não testado"
        },
        "claude": {
            "status": False,
            "error": "Não testado"
        },
        "deepseek": {
            "status": False,
            "error": "Não testado"
        }
    }
    
    # Verificar Google Drive
    try:
        credentials = get_credentials(DRIVE_SCOPES)
        
        if not credentials:
            result["google_drive"]["error"] = "Credenciais não encontradas"
        else:
            service = build('drive', 'v3', credentials=credentials)
            response = service.files().list(pageSize=1, fields="files(id, name)").execute()
            
            # Se chegou aqui, a conexão foi bem-sucedida
            result["google_drive"]["status"] = True
            result["google_drive"]["error"] = None
            logger.info("Google Drive API: Conexão OK")
    except Exception as e:
        result["google_drive"]["error"] = str(e)
        logger.error(f"Erro na verificação do Google Drive: {str(e)}")
        logger.error(traceback.format_exc())
    
    # Verificar Gemini
    try:
        gemini_key = get_gemini_key()
        if not gemini_key:
            result["gemini"]["error"] = "Chave API não configurada"
        else:
            genai.configure(api_key=gemini_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content("Olá, isto é um teste de conexão.")
            
            # Se chegou aqui, a conexão foi bem-sucedida
            result["gemini"]["status"] = True
            result["gemini"]["error"] = None
            logger.info("Gemini API: Conexão OK")
    except Exception as e:
        result["gemini"]["error"] = str(e)
        logger.error(f"Erro na verificação do Gemini: {str(e)}")
        logger.error(traceback.format_exc())
    
    # Verificar OpenAI
    try:
        openai_key = get_openai_key()
        if not openai_key:
            result["openai"]["error"] = "Chave API não configurada"
        else:
            client = openai.OpenAI(api_key=openai_key)
            response = client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": "Olá, isto é um teste de conexão."}],
                max_tokens=5
            )
            
            # Se chegou aqui, a conexão foi bem-sucedida
            result["openai"]["status"] = True
            result["openai"]["error"] = None
            logger.info("OpenAI API: Conexão OK")
    except Exception as e:
        result["openai"]["error"] = str(e)
        logger.error(f"Erro na verificação da OpenAI: {str(e)}")
        logger.error(traceback.format_exc())
    
    # Verificar Claude
    try:
        claude_key = get_claude_key()
        if not claude_key:
            result["claude"]["error"] = "Chave API não configurada"
        else:
            client = anthropic.Anthropic(api_key=claude_key)
            response = client.completions.create(
                model="claude-2",
                max_tokens_to_sample=5,
                prompt=f"\n\nHuman: Olá, isto é um teste de conexão.\n\nAssistant:"
            )
            
            # Se chegou aqui, a conexão foi bem-sucedida
            result["claude"]["status"] = True
            result["claude"]["error"] = None
            logger.info("Claude API: Conexão OK")
    except Exception as e:
        result["claude"]["error"] = str(e)
        logger.error(f"Erro na verificação do Claude: {str(e)}")
        logger.error(traceback.format_exc())
    
    # Verificar DeepSeek
    try:
        deepseek_key = get_deepseek_key()
        if not deepseek_key:
            result["deepseek"]["error"] = "Chave API não configurada"
        else:
            # Configurar cabeçalhos e payload para a API DeepSeek
            headers = {
                "Authorization": f"Bearer {deepseek_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": "Olá, isto é um teste de conexão."}],
                "max_tokens": 5
            }
            
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                data=json.dumps(payload)
            )
            
            if response.status_code == 200:
                result["deepseek"]["status"] = True
                result["deepseek"]["error"] = None
                logger.info("DeepSeek API: Conexão OK")
            else:
                result["deepseek"]["error"] = f"Erro HTTP: {response.status_code} - {response.text}"
                logger.error(f"Erro na resposta da DeepSeek API: {response.status_code} - {response.text}")
        
    except Exception as e:
        result["deepseek"]["error"] = str(e)
        logger.error(f"Erro na verificação da DeepSeek: {str(e)}")
        logger.error(traceback.format_exc())
    
    logger.info(f"Verificação de APIs concluída: {json.dumps(result)}")
    return result 
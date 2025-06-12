from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google.oauth2.service_account import Credentials
import os
import datetime
import logging
import traceback
import io
import re
from utils.credentials_helper import get_credentials

# Importar a função get_config da utils.sheets
from utils.sheets import get_config

# Configurar logger
logger = logging.getLogger('formulario_culsen.drive')

# Define scopes
SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.metadata.readonly',
    'https://www.googleapis.com/auth/drive'
]

# Get current directory
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_drive_client():
    """Returns an authenticated Google Drive client"""
    try:
        logger.info("Tentando autenticar com Google Drive")
        
        credentials = get_credentials(SCOPES)
        if not credentials:
            logger.error("Não foi possível obter credenciais válidas")
            return None
        
        drive_service = build('drive', 'v3', credentials=credentials)
        logger.info("Autenticação com Google Drive bem-sucedida")
        return drive_service
    except Exception as e:
        logger.error(f"Erro ao autenticar com Google Drive: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_or_create_folder(service, folder_name):
    """
    Obtém a ID da pasta no Drive ou cria se não existir
    """
    try:
        logger.info(f"Procurando pasta '{folder_name}' no Google Drive")
        # Procurar pasta por nome
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        logger.info(f"Query de busca: {query}")
        response = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
        folders = response.get('files', [])
        
        # Se a pasta existir, retorna o ID
        if folders:
            folder_id = folders[0]['id']
            logger.info(f"Pasta existente encontrada. ID: {folder_id}")
            return folder_id
        
        logger.info(f"Pasta '{folder_name}' não encontrada. Criando nova pasta.")
        # Se a pasta não existir, cria
        folder_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = service.files().create(body=folder_metadata, fields='id').execute()
        folder_id = folder['id']
        logger.info(f"Nova pasta criada com sucesso. ID: {folder_id}")
        return folder_id
    except Exception as e:
        logger.error(f"Erro ao obter/criar pasta no Drive: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def upload_file_to_drive(file_path, original_filename):
    """
    Upload a file to Google Drive
    Returns the sharable link of the uploaded file
    """
    try:
        logger.info(f"Iniciando upload de arquivo para o Google Drive: {file_path}")
        service = get_drive_client()
        
        # Obter o nome da pasta do Google Drive da configuração
        logger.info("Obtendo nome da pasta do Google Drive das configurações")
        config = get_config()
        folder_name = config.get("PASTA_GOOGLE_DRIVE", "CVs Formulário Culsen")
        logger.info(f"Nome da pasta configurada: {folder_name}")
        
        # Obter ID da pasta ou criar se não existir
        logger.info(f"Obtendo/criando pasta no Drive: {folder_name}")
        folder_id = get_or_create_folder(service, folder_name)
        
        # Create a timestamp for the filename
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        file_extension = os.path.splitext(original_filename)[1]
        filename = f"CV_{timestamp}{file_extension}"
        logger.info(f"Nome do arquivo a ser salvo: {filename}")
        
        # Define file metadata
        file_metadata = {
            'name': filename,
            'mimeType': 'application/pdf' if file_extension.lower() == '.pdf' else 'text/plain',
            'parents': [folder_id]  # Adiciona à pasta especificada
        }
        
        # Upload file
        logger.info(f"Preparando upload do arquivo. Mime type: {file_metadata['mimeType']}")
        media = MediaFileUpload(
            file_path,
            mimetype='application/pdf' if file_extension.lower() == '.pdf' else 'text/plain',
            resumable=True
        )
        
        logger.info("Enviando arquivo para o Google Drive...")
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id,webViewLink'
        ).execute()
        
        file_id = file.get('id')
        logger.info(f"Arquivo enviado com sucesso. ID: {file_id}")
        
        # Make the file viewable by anyone with the link
        logger.info("Configurando permissões para o arquivo...")
        permission = {
            'type': 'anyone',
            'role': 'reader',
            'allowFileDiscovery': False
        }
        
        service.permissions().create(
            fileId=file_id,
            body=permission
        ).execute()
        logger.info("Permissões configuradas com sucesso")
        
        # Return the sharable link
        web_view_link = file.get('webViewLink')
        logger.info(f"Link compartilhável criado: {web_view_link}")
        return web_view_link
    
    except Exception as e:
        logger.error(f"Erro ao fazer upload do arquivo para o Drive: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def download_cv_for_processing(file_url, output_filename):
    """
    Faz o download do CV a partir de uma URL do Google Drive para reprocessamento
    Retorna o caminho local do arquivo baixado
    """
    try:
        logger.info(f"Fazendo download do CV: {file_url}")
        
        # Extrair o ID do arquivo da URL do Google Drive
        # Formato típico: https://drive.google.com/file/d/FILE_ID/view?usp=drivesdk
        file_id = None
        if '/d/' in file_url:
            file_id = file_url.split('/d/')[1].split('/')[0]
        
        if not file_id:
            logger.error(f"Não foi possível extrair o ID do arquivo da URL: {file_url}")
            raise ValueError(f"URL inválida do Google Drive: {file_url}")
        
        logger.info(f"ID do arquivo extraído: {file_id}")
        
        # Obter o serviço do Google Drive
        service = get_drive_client()
        
        # Criar diretório de saída se não existir
        os.makedirs('temp', exist_ok=True)
        output_path = os.path.join('temp', output_filename)
        
        # Fazer o download do arquivo
        logger.info(f"Baixando arquivo para: {output_path}")
        request = service.files().get_media(fileId=file_id)
        
        with open(output_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"Download {int(status.progress() * 100)}% concluído")
        
        logger.info(f"Download concluído: {output_path}")
        return output_path
    
    except Exception as e:
        logger.error(f"Erro ao fazer download do CV: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def download_file_from_drive(file_id, destination_path):
    """
    Baixa um arquivo do Google Drive pelo seu ID
    
    Args:
        file_id (str): ID do arquivo no Google Drive
        destination_path (str): Caminho onde o arquivo será salvo
        
    Returns:
        bool: True se o download foi bem-sucedido, False caso contrário
    """
    try:
        logger.info(f"Fazendo download do arquivo com ID: {file_id}")
        
        # Obter cliente do Google Drive
        drive_service = get_drive_client()
        if not drive_service:
            logger.error("Falha ao obter cliente do Google Drive")
            return False
        
        # Solicitar download do arquivo
        request = drive_service.files().get_media(fileId=file_id)
        
        # Criar arquivo de saída
        with open(destination_path, 'wb') as f:
            downloader = MediaIoBaseDownload(f, request)
            done = False
            while not done:
                status, done = downloader.next_chunk()
                logger.info(f"Download {int(status.progress() * 100)}% concluído")
        
        logger.info(f"Download concluído: {destination_path}")
        return True
    
    except Exception as e:
        logger.error(f"Erro ao baixar arquivo do Google Drive: {str(e)}")
        logger.error(traceback.format_exc())
        return False 
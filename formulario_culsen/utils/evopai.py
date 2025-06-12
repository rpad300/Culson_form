"""
Evolution API Integration Module
Módulo para integração com Evolution API para WhatsApp
"""
import requests
import json
import os
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EvolutionAPI:
    """
    Classe para integração com Evolution API
    """
    
    def __init__(self, base_url: str, api_key: str, instance_name: str = "default"):
        """
        Inicializa a conexão com Evolution API
        
        Args:
            base_url: URL base da Evolution API (ex: https://api.evolution.com.br)
            api_key: Chave de API para autenticação
            instance_name: Nome da instância do WhatsApp
        """
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self.instance_name = instance_name
        self.headers = {
            'Content-Type': 'application/json',
            'apikey': api_key
        }
        
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """
        Faz uma requisição para a API
        
        Args:
            method: Método HTTP (GET, POST, PUT, DELETE)
            endpoint: Endpoint da API
            data: Dados para enviar (opcional)
            
        Returns:
            Resposta da API
        """
        url = f"{self.base_url}/{endpoint}"
        
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=self.headers, timeout=30)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=30)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=self.headers, json=data, timeout=30)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=self.headers, timeout=30)
            else:
                raise ValueError(f"Método HTTP não suportado: {method}")
                
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Erro na requisição para {url}: {str(e)}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Erro ao decodificar JSON da resposta: {str(e)}")
            raise
    
    # ==================== GERENCIAMENTO DE INSTÂNCIA ====================
    
    def create_instance(self, instance_config: Dict) -> Dict:
        """
        Cria uma nova instância do WhatsApp
        
        Args:
            instance_config: Configurações da instância
            
        Returns:
            Resposta da API
        """
        endpoint = f"instance/create"
        config = {
            "instanceName": self.instance_name,
            "qrcode": True,
            "integration": "WHATSAPP-BAILEYS",
            **instance_config
        }
        return self._make_request('POST', endpoint, config)
    
    def get_instance_status(self) -> Dict:
        """
        Obtém o status da instância
        
        Returns:
            Status da instância
        """
        endpoint = f"instance/connectionState/{self.instance_name}"
        return self._make_request('GET', endpoint)
    
    def get_qr_code(self) -> Dict:
        """
        Obtém o QR Code para conectar o WhatsApp
        
        Returns:
            QR Code em base64
        """
        endpoint = f"instance/connect/{self.instance_name}"
        return self._make_request('GET', endpoint)
    
    def logout_instance(self) -> Dict:
        """
        Desloga a instância do WhatsApp
        
        Returns:
            Resposta da API
        """
        endpoint = f"instance/logout/{self.instance_name}"
        return self._make_request('DELETE', endpoint)
    
    def delete_instance(self) -> Dict:
        """
        Deleta a instância
        
        Returns:
            Resposta da API
        """
        endpoint = f"instance/delete/{self.instance_name}"
        return self._make_request('DELETE', endpoint)
    
    # ==================== ENVIO DE MENSAGENS ====================
    
    def send_text_message(self, number: str, message: str, delay: int = 1200) -> Dict:
        """
        Envia uma mensagem de texto
        
        Args:
            number: Número do destinatário (com código do país)
            message: Texto da mensagem
            delay: Delay entre mensagens em ms
            
        Returns:
            Resposta da API
        """
        endpoint = f"message/sendText/{self.instance_name}"
        data = {
            "number": number,
            "options": {
                "delay": delay,
                "presence": "composing"
            },
            "textMessage": {
                "text": message
            }
        }
        return self._make_request('POST', endpoint, data)
    
    def send_media_message(self, number: str, media_url: str, media_type: str, 
                          caption: str = "", filename: str = "") -> Dict:
        """
        Envia uma mensagem com mídia
        
        Args:
            number: Número do destinatário
            media_url: URL da mídia
            media_type: Tipo da mídia (image, video, audio, document)
            caption: Legenda da mídia
            filename: Nome do arquivo
            
        Returns:
            Resposta da API
        """
        endpoint = f"message/sendMedia/{self.instance_name}"
        data = {
            "number": number,
            "options": {
                "delay": 1200,
                "presence": "composing"
            },
            "mediaMessage": {
                "mediatype": media_type,
                "media": media_url,
                "caption": caption,
                "fileName": filename
            }
        }
        return self._make_request('POST', endpoint, data)
    
    def send_button_message(self, number: str, text: str, buttons: List[Dict]) -> Dict:
        """
        Envia mensagem com botões
        
        Args:
            number: Número do destinatário
            text: Texto da mensagem
            buttons: Lista de botões
            
        Returns:
            Resposta da API
        """
        endpoint = f"message/sendButtons/{self.instance_name}"
        data = {
            "number": number,
            "options": {
                "delay": 1200,
                "presence": "composing"
            },
            "buttonsMessage": {
                "text": text,
                "buttons": buttons,
                "footerText": ""
            }
        }
        return self._make_request('POST', endpoint, data)
    
    def send_list_message(self, number: str, text: str, title: str, 
                         button_text: str, sections: List[Dict]) -> Dict:
        """
        Envia mensagem com lista
        
        Args:
            number: Número do destinatário
            text: Texto da mensagem
            title: Título da lista
            button_text: Texto do botão
            sections: Seções da lista
            
        Returns:
            Resposta da API
        """
        endpoint = f"message/sendList/{self.instance_name}"
        data = {
            "number": number,
            "options": {
                "delay": 1200,
                "presence": "composing"
            },
            "listMessage": {
                "title": title,
                "description": text,
                "buttonText": button_text,
                "footerText": "",
                "sections": sections
            }
        }
        return self._make_request('POST', endpoint, data)
    
    # ==================== GRUPOS ====================
    
    def get_groups(self) -> Dict:
        """
        Obtém lista de grupos
        
        Returns:
            Lista de grupos
        """
        endpoint = f"group/fetchAllGroups/{self.instance_name}?getParticipants=true"
        return self._make_request('GET', endpoint)
    
    def create_group(self, subject: str, participants: List[str]) -> Dict:
        """
        Cria um novo grupo
        
        Args:
            subject: Nome do grupo
            participants: Lista de participantes
            
        Returns:
            Resposta da API
        """
        endpoint = f"group/create/{self.instance_name}"
        data = {
            "subject": subject,
            "participants": participants
        }
        return self._make_request('POST', endpoint, data)
    
    # ==================== CONTATOS ====================
    
    def get_contacts(self) -> Dict:
        """
        Obtém lista de contatos
        
        Returns:
            Lista de contatos
        """
        endpoint = f"chat/fetchContacts/{self.instance_name}"
        return self._make_request('GET', endpoint)
    
    def check_number(self, numbers: List[str]) -> Dict:
        """
        Verifica se números estão no WhatsApp
        
        Args:
            numbers: Lista de números para verificar
            
        Returns:
            Status dos números
        """
        endpoint = f"chat/whatsappNumbers/{self.instance_name}"
        data = {
            "numbers": numbers
        }
        return self._make_request('POST', endpoint, data)
    
    # ==================== WEBHOOKS ====================
    
    def set_webhook(self, webhook_url: str, webhook_by_events: bool = True, 
                   webhook_base64: bool = True) -> Dict:
        """
        Configura webhook para receber eventos
        
        Args:
            webhook_url: URL do webhook
            webhook_by_events: Receber eventos separadamente
            webhook_base64: Receber mídias em base64
            
        Returns:
            Resposta da API
        """
        endpoint = f"webhook/set/{self.instance_name}"
        data = {
            "url": webhook_url,
            "webhook_by_events": webhook_by_events,
            "webhook_base64": webhook_base64,
            "events": [
                "APPLICATION_STARTUP",
                "QRCODE_UPDATED",
                "MESSAGES_UPSERT",
                "MESSAGES_UPDATE",
                "MESSAGES_DELETE",
                "SEND_MESSAGE",
                "CONTACTS_SET",
                "CONTACTS_UPSERT",
                "CONTACTS_UPDATE",
                "PRESENCE_UPDATE",
                "CHATS_SET",
                "CHATS_UPSERT",
                "CHATS_UPDATE",
                "CHATS_DELETE",
                "GROUPS_UPSERT",
                "GROUP_UPDATE",
                "GROUP_PARTICIPANTS_UPDATE",
                "CONNECTION_UPDATE",
                "LABELS_EDIT",
                "LABELS_ASSOCIATION",
                "CALL_UPSERT"
            ]
        }
        return self._make_request('POST', endpoint, data)
    
    def get_webhook(self) -> Dict:
        """
        Obtém configurações do webhook
        
        Returns:
            Configurações do webhook
        """
        endpoint = f"webhook/find/{self.instance_name}"
        return self._make_request('GET', endpoint)
    
    # ==================== UTILITÁRIOS ====================
    
    def format_phone_number(self, number: str, country_code: str = "55") -> str:
        """
        Formata número de telefone para o padrão do WhatsApp
        
        Args:
            number: Número de telefone
            country_code: Código do país (padrão: Brasil)
            
        Returns:
            Número formatado
        """
        # Remove caracteres especiais
        clean_number = ''.join(filter(str.isdigit, number))
        
        # Adiciona código do país se não estiver presente
        if not clean_number.startswith(country_code):
            clean_number = country_code + clean_number
        
        # Adiciona @s.whatsapp.net
        return f"{clean_number}@s.whatsapp.net"
    
    def is_group_number(self, number: str) -> bool:
        """
        Verifica se o número é de um grupo
        
        Args:
            number: Número para verificar
            
        Returns:
            True se for grupo, False caso contrário
        """
        return "@g.us" in number
    
    def extract_phone_from_jid(self, jid: str) -> str:
        """
        Extrai número de telefone do JID do WhatsApp
        
        Args:
            jid: JID completo do WhatsApp
            
        Returns:
            Número de telefone limpo
        """
        return jid.split('@')[0]

# ==================== CONFIGURAÇÃO E INICIALIZAÇÃO ====================

def load_evolution_config() -> Dict:
    """
    Carrega configurações do Evolution API das variáveis de ambiente
    
    Returns:
        Dicionário com configurações
    """
    config = {
        'base_url': os.getenv('EVOLUTION_API_URL', 'http://localhost:8080'),
        'api_key': os.getenv('EVOLUTION_API_KEY', ''),
        'instance_name': os.getenv('EVOLUTION_INSTANCE_NAME', 'culsen_form'),
        'webhook_url': os.getenv('EVOLUTION_WEBHOOK_URL', ''),
    }
    
    # Validar configurações obrigatórias
    if not config['api_key']:
        raise ValueError("EVOLUTION_API_KEY não configurada nas variáveis de ambiente")
    
    return config

def create_evolution_client() -> EvolutionAPI:
    """
    Cria cliente Evolution API com configurações do ambiente
    
    Returns:
        Instância do EvolutionAPI
    """
    config = load_evolution_config()
    return EvolutionAPI(
        base_url=config['base_url'],
        api_key=config['api_key'],
        instance_name=config['instance_name']
    )

# ==================== EXEMPLO DE USO ====================

if __name__ == "__main__":
    # Exemplo de uso básico
    try:
        # Criar cliente
        evolution = create_evolution_client()
        
        # Verificar status da instância
        status = evolution.get_instance_status()
        print(f"Status da instância: {status}")
        
        # Exemplo de envio de mensagem
        # number = evolution.format_phone_number("11999999999")
        # response = evolution.send_text_message(number, "Olá! Esta é uma mensagem de teste.")
        # print(f"Mensagem enviada: {response}")
        
    except Exception as e:
        logger.error(f"Erro no exemplo: {str(e)}") 
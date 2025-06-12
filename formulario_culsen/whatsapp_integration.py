"""
Integração WhatsApp - Evolution API + Formulário Culsen
Este módulo conecta o Evolution API ao sistema de análise de currículos
"""

import os
import sys
import logging
from datetime import datetime
from typing import Dict, Optional, List
import json

# Adicionar utils ao path
sys.path.append(os.path.join(os.path.dirname(__file__), 'utils'))

try:
    from utils.evopai import create_evolution_client, EvolutionAPI
    from utils.sheets import SheetsManager
    from utils.ia import process_cv_with_ai
except ImportError as e:
    print(f"Erro ao importar módulos: {e}")
    print("Certifique-se de que todos os módulos estão disponíveis")

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WhatsAppNotifier:
    """
    Classe para enviar notificações via WhatsApp
    """
    
    def __init__(self):
        self.evolution = None
        self.sheets = None
        self._init_clients()
    
    def _init_clients(self):
        """Inicializa os clientes necessários"""
        try:
            self.evolution = create_evolution_client()
            self.sheets = SheetsManager()
            logger.info("Clientes WhatsApp e Sheets inicializados com sucesso")
        except Exception as e:
            logger.error(f"Erro ao inicializar clientes: {e}")
    
    def format_phone_number(self, phone: str) -> str:
        """
        Formata número de telefone para WhatsApp
        
        Args:
            phone: Número de telefone
            
        Returns:
            Número formatado para WhatsApp
        """
        if not self.evolution:
            return phone
        return self.evolution.format_phone_number(phone)
    
    def send_welcome_message(self, phone: str, name: str) -> Dict:
        """
        Envia mensagem de boas-vindas ao candidato
        
        Args:
            phone: Telefone do candidato
            name: Nome do candidato
            
        Returns:
            Resposta da API
        """
        if not self.evolution:
            return {"error": "Evolution API não inicializada"}
        
        try:
            number = self.format_phone_number(phone)
            
            message = f"""🎉 Olá {name}!

Obrigado por enviar seu currículo para a Culsen!

📋 **Status:** Recebido com sucesso
⏰ **Análise:** Em andamento
🤖 **IA:** Processando seu perfil

Você será notificado assim que a análise estiver completa.

Para consultar o status a qualquer momento, envie: *status*"""

            response = self.evolution.send_text_message(number, message)
            logger.info(f"Mensagem de boas-vindas enviada para {name} ({phone})")
            return response
            
        except Exception as e:
            logger.error(f"Erro ao enviar mensagem de boas-vindas: {e}")
            return {"error": str(e)}
    
    def send_analysis_complete(self, phone: str, name: str, analysis_result: Dict) -> Dict:
        """
        Envia resultado da análise do currículo
        
        Args:
            phone: Telefone do candidato
            name: Nome do candidato
            analysis_result: Resultado da análise da IA
            
        Returns:
            Resposta da API
        """
        if not self.evolution:
            return {"error": "Evolution API não inicializada"}
        
        try:
            number = self.format_phone_number(phone)
            
            # Determinar status da análise
            score = analysis_result.get('pontuacao_geral', 0)
            
            if score >= 8:
                status_emoji = "🟢"
                status_text = "EXCELENTE"
                message_type = "aprovado"
            elif score >= 6:
                status_emoji = "🟡"
                status_text = "BOM"
                message_type = "em_analise"
            else:
                status_emoji = "🔴"
                status_text = "PRECISA MELHORAR"
                message_type = "rejeitado"
            
            message = f"""🤖 **Análise Completa!**

Olá {name}, sua análise foi finalizada:

{status_emoji} **Pontuação Geral:** {score}/10
📊 **Status:** {status_text}

**Principais Pontos:**
{analysis_result.get('principais_pontos', 'Não disponível')}

**Sugestões de Melhoria:**
{analysis_result.get('sugestoes_melhoria', 'Nenhuma sugestão disponível')}"""

            # Enviar mensagem principal
            response = self.evolution.send_text_message(number, message)
            
            # Enviar botões baseados no resultado
            self._send_action_buttons(number, message_type, analysis_result)
            
            logger.info(f"Resultado da análise enviado para {name} ({phone})")
            return response
            
        except Exception as e:
            logger.error(f"Erro ao enviar resultado da análise: {e}")
            return {"error": str(e)}
    
    def _send_action_buttons(self, number: str, message_type: str, analysis_result: Dict):
        """
        Envia botões de ação baseados no resultado da análise
        
        Args:
            number: Número do WhatsApp
            message_type: Tipo da mensagem (aprovado, em_analise, rejeitado)
            analysis_result: Resultado da análise
        """
        try:
            if message_type == "aprovado":
                buttons = [
                    {
                        "buttonId": "agendar_entrevista",
                        "buttonText": {"displayText": "📅 Agendar Entrevista"},
                        "type": 1
                    },
                    {
                        "buttonId": "ver_vagas",
                        "buttonText": {"displayText": "💼 Ver Vagas"},
                        "type": 1
                    }
                ]
                text = "Próximas etapas disponíveis:"
                
            elif message_type == "em_analise":
                buttons = [
                    {
                        "buttonId": "melhorar_cv",
                        "buttonText": {"displayText": "📝 Dicas para Melhorar"},
                        "type": 1
                    },
                    {
                        "buttonId": "reenviar_cv",
                        "buttonText": {"displayText": "🔄 Reenviar CV"},
                        "type": 1
                    }
                ]
                text = "Ações disponíveis:"
                
            else:  # rejeitado
                buttons = [
                    {
                        "buttonId": "melhorar_cv",
                        "buttonText": {"displayText": "📚 Como Melhorar"},
                        "type": 1
                    },
                    {
                        "buttonId": "novas_vagas",
                        "buttonText": {"displayText": "🔔 Avisar Novas Vagas"},
                        "type": 1
                    }
                ]
                text = "Não desista! Você pode:"
            
            self.evolution.send_button_message(number, text, buttons)
            
        except Exception as e:
            logger.error(f"Erro ao enviar botões: {e}")
    
    def send_status_update(self, phone: str, name: str) -> Dict:
        """
        Envia status atual do candidato
        
        Args:
            phone: Telefone do candidato
            name: Nome do candidato
            
        Returns:
            Resposta da API
        """
        if not self.evolution or not self.sheets:
            return {"error": "Clientes não inicializados"}
        
        try:
            # Buscar dados do candidato na planilha
            candidato_data = self._get_candidate_data(name, phone)
            
            if not candidato_data:
                message = f"""❌ **Status não encontrado**

Olá {name}!

Não encontramos seu currículo em nossa base.

Você pode:
• Reenviar seu currículo
• Verificar se usou o mesmo nome/telefone
• Entrar em contato conosco"""
            else:
                status = candidato_data.get('status', 'Em análise')
                data_envio = candidato_data.get('data_envio', 'Não informado')
                pontuacao = candidato_data.get('pontuacao', 'Pendente')
                
                message = f"""📊 **Status do seu Currículo**

Olá {name}!

📅 **Enviado em:** {data_envio}
⚡ **Status Atual:** {status}
🎯 **Pontuação:** {pontuacao}

Mantenha-se atualizado sobre o processo seletivo!"""
            
            number = self.format_phone_number(phone)
            response = self.evolution.send_text_message(number, message)
            
            logger.info(f"Status enviado para {name} ({phone})")
            return response
            
        except Exception as e:
            logger.error(f"Erro ao enviar status: {e}")
            return {"error": str(e)}
    
    def _get_candidate_data(self, name: str, phone: str) -> Optional[Dict]:
        """
        Busca dados do candidato na planilha
        
        Args:
            name: Nome do candidato
            phone: Telefone do candidato
            
        Returns:
            Dados do candidato ou None
        """
        try:
            # Implementar busca na planilha Google Sheets
            # Isso deve ser adaptado conforme a estrutura da sua planilha
            candidates = self.sheets.get_all_records()
            
            for candidate in candidates:
                if (candidate.get('nome', '').lower() == name.lower() or 
                    candidate.get('telefone', '') == phone):
                    return candidate
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao buscar dados do candidato: {e}")
            return None
    
    def send_job_opportunities(self, phone: str, name: str, profile_type: str = None) -> Dict:
        """
        Envia oportunidades de trabalho personalizadas
        
        Args:
            phone: Telefone do candidato
            name: Nome do candidato
            profile_type: Tipo de perfil do candidato
            
        Returns:
            Resposta da API
        """
        if not self.evolution:
            return {"error": "Evolution API não inicializada"}
        
        try:
            number = self.format_phone_number(phone)
            
            # Oportunidades baseadas no perfil (isso pode vir de uma base de dados)
            opportunities = self._get_opportunities_by_profile(profile_type)
            
            if not opportunities:
                message = f"""💼 **Oportunidades de Trabalho**

Olá {name}!

No momento não temos vagas específicas para seu perfil, mas:

🔔 **Ativamos alertas** para quando surgirem oportunidades
📝 **Continue aprimorando** seu currículo
🎯 **Acompanhe** nossas redes sociais

Em breve entraremos em contato!"""
            else:
                sections = []
                for opp in opportunities[:5]:  # Máximo 5 oportunidades
                    sections.append({
                        "title": "Vagas Disponíveis",
                        "rows": [{
                            "rowId": f"vaga_{opp['id']}",
                            "title": opp['titulo'],
                            "description": f"{opp['empresa']} - {opp['localizacao']}"
                        }]
                    })
                
                # Enviar lista de oportunidades
                self.evolution.send_list_message(
                    number=number,
                    text=f"Olá {name}! Encontramos vagas que podem interessar:",
                    title="Oportunidades",
                    button_text="Ver Detalhes",
                    sections=sections
                )
                return {"status": "sent", "type": "list"}
            
            response = self.evolution.send_text_message(number, message)
            logger.info(f"Oportunidades enviadas para {name} ({phone})")
            return response
            
        except Exception as e:
            logger.error(f"Erro ao enviar oportunidades: {e}")
            return {"error": str(e)}
    
    def _get_opportunities_by_profile(self, profile_type: str) -> List[Dict]:
        """
        Busca oportunidades baseadas no perfil
        
        Args:
            profile_type: Tipo de perfil
            
        Returns:
            Lista de oportunidades
        """
        # Implementar busca em base de dados de vagas
        # Por enquanto, retornar exemplo estático
        return [
            {
                "id": "1",
                "titulo": "Desenvolvedor Python",
                "empresa": "TechCorp",
                "localizacao": "São Paulo - SP",
                "tipo": "CLT"
            },
            {
                "id": "2", 
                "titulo": "Analista de Dados",
                "empresa": "DataAnalytics",
                "localizacao": "Remote",
                "tipo": "PJ"
            }
        ]

# ==================== FUNÇÃO DE INTEGRAÇÃO PRINCIPAL ====================

def integrate_whatsapp_with_form(form_data: Dict) -> Dict:
    """
    Integra o WhatsApp com o formulário de currículos
    
    Args:
        form_data: Dados do formulário submetido
        
    Returns:
        Resultado da integração
    """
    try:
        whatsapp = WhatsAppNotifier()
        
        name = form_data.get('nome', '')
        phone = form_data.get('telefone', '')
        
        if not phone:
            return {"error": "Telefone não fornecido"}
        
        # Enviar mensagem de boas-vindas
        welcome_result = whatsapp.send_welcome_message(phone, name)
        
        # Log da integração
        logger.info(f"WhatsApp integrado para {name} ({phone})")
        
        return {
            "status": "success",
            "message": "WhatsApp notification sent",
            "whatsapp_response": welcome_result
        }
        
    except Exception as e:
        logger.error(f"Erro na integração WhatsApp: {e}")
        return {"error": str(e)}

def send_analysis_notification(candidate_data: Dict, analysis_result: Dict) -> Dict:
    """
    Envia notificação de análise completa
    
    Args:
        candidate_data: Dados do candidato
        analysis_result: Resultado da análise da IA
        
    Returns:
        Resultado do envio
    """
    try:
        whatsapp = WhatsAppNotifier()
        
        name = candidate_data.get('nome', '')
        phone = candidate_data.get('telefone', '')
        
        if not phone:
            return {"error": "Telefone não encontrado"}
        
        # Enviar resultado da análise
        result = whatsapp.send_analysis_complete(phone, name, analysis_result)
        
        logger.info(f"Notificação de análise enviada para {name}")
        
        return {
            "status": "success",
            "message": "Analysis notification sent",
            "whatsapp_response": result
        }
        
    except Exception as e:
        logger.error(f"Erro ao enviar notificação de análise: {e}")
        return {"error": str(e)}

# ==================== EXEMPLO DE USO ====================

if __name__ == "__main__":
    # Exemplo de uso da integração
    
    # Dados de exemplo do formulário
    form_data = {
        "nome": "João Silva",
        "telefone": "11999999999",
        "email": "joao@email.com"
    }
    
    # Integrar com WhatsApp
    result = integrate_whatsapp_with_form(form_data)
    print(f"Resultado da integração: {result}")
    
    # Exemplo de notificação de análise
    analysis_result = {
        "pontuacao_geral": 8.5,
        "principais_pontos": "• Experiência sólida em Python\n• Boa formação acadêmica\n• Projetos relevantes",
        "sugestoes_melhoria": "• Adicionar certificações\n• Detalhar mais os projetos\n• Incluir soft skills"
    }
    
    # Enviar notificação de análise
    notification_result = send_analysis_notification(form_data, analysis_result)
    print(f"Resultado da notificação: {notification_result}") 
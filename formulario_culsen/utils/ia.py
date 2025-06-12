import os
import pdfplumber
from google.cloud import aiplatform
from google.oauth2.service_account import Credentials
import json
import logging
import traceback
import PyPDF2
import requests
import anthropic
import openai
import google.generativeai as genai
from anthropic import Anthropic

from utils.sheets import get_config, get_custom_prompt, get_validation_prompt

# Configurar logger
logger = logging.getLogger('formulario_culsen.ia')

def extract_text_from_file(file_path):
    """Extract text from PDF or TXT file"""
    file_extension = os.path.splitext(file_path)[1].lower()
    
    logger.info(f"Extraindo texto do arquivo: {file_path} (tipo: {file_extension})")
    
    if file_extension == '.pdf':
        return extract_text_from_pdf(file_path)
    elif file_extension == '.txt':
        try:
            logger.info("Processando arquivo TXT")
            with open(file_path, 'r', encoding='utf-8') as file:
                text = file.read()
                logger.info(f"Texto extraído do TXT. Total: {len(text)} caracteres")
                return text
        except Exception as e:
            logger.error(f"Erro lendo arquivo TXT: {str(e)}")
            logger.error(traceback.format_exc())
            return ""
    else:
        logger.warning(f"Formato de arquivo não suportado: {file_extension}")
        return ""

def extract_text_from_pdf(pdf_path):
    """
    Extrai texto de um arquivo PDF usando PyPDF2
    """
    try:
        logger.info(f"Extraindo texto do PDF: {pdf_path}")
        
        # Desativar logs muito detalhados durante o processamento
        logging.getLogger("pdfminer").setLevel(logging.ERROR)
        logging.getLogger("pdfplumber").setLevel(logging.WARNING)
        
        text = ""
        total_chars = 0
        
        with open(pdf_path, 'rb') as pdf_file:
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            num_pages = len(pdf_reader.pages)
            
            for i in range(num_pages):
                page = pdf_reader.pages[i]
                page_text = page.extract_text()
                chars = len(page_text) if page_text else 0
                logger.info(f"Página {i+1}: {chars} caracteres extraídos")
                if page_text:
                    text += page_text + "\n\n"
                    total_chars += chars
        
        logger.info(f"Extração de texto do PDF concluída. Total: {total_chars} caracteres")
        return text
    except Exception as e:
        logger.error(f"Erro ao extrair texto do PDF: {str(e)}")
        logger.error(traceback.format_exc())
        return ""

def extract_text_from_txt(txt_path):
    """
    Extrai texto de arquivos TXT.
    """
    try:
        logger.info(f"Extraindo texto do arquivo TXT: {txt_path}")
        with open(txt_path, 'r', encoding='utf-8', errors='ignore') as file:
            text = file.read()
        logger.info(f"Extração de texto concluída. Tamanho do texto: {len(text)} caracteres")
        return text
    except Exception as e:
        logger.error(f"Erro ao extrair texto do arquivo TXT: {str(e)}")
        logger.error(traceback.format_exc())
        return ""

def get_gemini_key():
    """
    Obtém a chave API do Gemini da configuração.
    """
    try:
        logger.info("Obtendo chave API do Gemini da configuração")
        configs = get_config()
        if not configs:
            logger.error("Falha ao obter configurações")
            return None
        
        api_key = configs.get('API_KEY_GEMINI')
        if not api_key:
            logger.error("Chave API do Gemini não encontrada na configuração")
            return None
        
        return api_key
    except Exception as e:
        logger.error(f"Erro ao obter chave API do Gemini: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_openai_key():
    """
    Obtém a chave API da OpenAI da configuração.
    """
    try:
        logger.info("Obtendo chave API da OpenAI da configuração")
        configs = get_config()
        if not configs:
            logger.error("Falha ao obter configurações")
            return None
        
        api_key = configs.get('API_KEY_OPENAI')
        if not api_key:
            logger.error("Chave API da OpenAI não encontrada na configuração")
            return None
        
        return api_key
    except Exception as e:
        logger.error(f"Erro ao obter chave API da OpenAI: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_claude_key():
    """
    Obtém a chave API do Claude da configuração.
    """
    try:
        logger.info("Obtendo chave API do Claude da configuração")
        configs = get_config()
        if not configs:
            logger.error("Falha ao obter configurações")
            return None
        
        api_key = configs.get('API_KEY_CLAUDE')
        if not api_key:
            logger.error("Chave API do Claude não encontrada na configuração")
            return None
        
        return api_key
    except Exception as e:
        logger.error(f"Erro ao obter chave API do Claude: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_deepseek_key():
    """
    Obtém a chave API do DeepSeek da configuração.
    """
    try:
        logger.info("Obtendo chave API do DeepSeek da configuração")
        configs = get_config()
        if not configs:
            logger.error("Falha ao obter configurações")
            return None
        
        api_key = configs.get('API_KEY_DEEPSEEK')
        if not api_key:
            logger.error("Chave API do DeepSeek não encontrada na configuração")
            return None
        
        return api_key
    except Exception as e:
        logger.error(f"Erro ao obter chave API do DeepSeek: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_ai_provider():
    """
    Obtém o provedor de IA da configuração.
    """
    try:
        logger.info("Obtendo provedor de IA da configuração")
        configs = get_config()
        if not configs:
            logger.error("Falha ao obter configurações")
            return "gemini"  # Provedor padrão
        
        provider = configs.get('AI_PROVIDER', 'gemini').lower()
        logger.info(f"Provedor de IA configurado: {provider}")
        
        # Verificar se o provedor é válido
        if provider not in ['gemini', 'openai', 'claude', 'deepseek']:
            logger.warning(f"Provedor de IA inválido: {provider}. Usando o provedor padrão (gemini)")
            return "gemini"
        
        return provider
    except Exception as e:
        logger.error(f"Erro ao obter provedor de IA: {str(e)}")
        logger.error(traceback.format_exc())
        return "gemini"  # Provedor padrão em caso de erro

def analyze_cv(file_path, form_data):
    """
    Analisa o currículo do candidato e retorna avaliação.
    """
    try:
        logger.info(f"Iniciando análise do CV: {file_path}")
        
        # Extrair texto do arquivo
        text = ""
        file_extension = os.path.splitext(file_path)[1].lower()
        if file_extension == '.pdf':
            text = extract_text_from_pdf(file_path)
        elif file_extension == '.txt':
            text = extract_text_from_txt(file_path)
        else:
            logger.error(f"Formato de arquivo não suportado: {file_extension}")
            return {"error": "Formato de arquivo não suportado"}
        
        if not text:
            logger.error("Não foi possível extrair texto do arquivo")
            return {"error": "Não foi possível extrair texto do arquivo"}
        
        # Obter o provedor de IA configurado
        provider = get_ai_provider()
        
        # Analisar o CV com o provedor selecionado
        result = None
        if provider == "gemini":
            result = analyze_with_gemini(text, form_data)
        elif provider == "openai":
            result = analyze_with_openai(text, form_data)
        elif provider == "claude":
            result = analyze_with_claude(text, form_data)
        elif provider == "deepseek":
            result = analyze_with_deepseek(text, form_data)
        else:
            logger.error(f"Provedor de IA não suportado: {provider}")
            return {"error": "Provedor de IA não suportado"}
        
        # Adicionar informação sobre o provedor usado na análise
        if result and not isinstance(result, dict):
            result = {"analysis": result, "provider": provider}
        elif result and isinstance(result, dict) and not result.get("error"):
            result["provider"] = provider
        
        logger.info(f"Análise de CV concluída com o provedor: {provider}")
        return result
    except Exception as e:
        logger.error(f"Erro durante a análise do CV: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": f"Erro durante a análise: {str(e)}"}

def get_prompt(text, form_data):
    """
    Gera o prompt para análise do CV usando os dados do formulário.
    Se existir uma prompt personalizada na planilha, usa ela. Caso contrário, usa a padrão.
    """
    nome = form_data.get('nome', '')
    email = form_data.get('email', '')
    telefone = form_data.get('telefone', '')
    cargo = form_data.get('cargo', 'Cuidador')  # Valor padrão para cargo
    
    # Preparar um resumo de todas as respostas do formulário
    respostas = ""
    for chave, valor in form_data.items():
        if chave not in ['justificacao', 'provider', 'cv_url', 'classificacao']:  # Excluir campos internos
            respostas += f"- {chave}: {valor}\n"
    
    # Tentar obter a prompt personalizada da planilha
    custom_prompt = get_custom_prompt()
    
    if custom_prompt:
        logger.info("Usando prompt personalizada da planilha")
        try:
            # Formatar a prompt personalizada com os dados do formulário
            formatted_prompt = custom_prompt.format(
                nome=nome,
                email=email,
                telefone=telefone,
                cargo=cargo,
                text=text,
                respostas=respostas
            )
            return formatted_prompt
        except Exception as e:
            logger.error(f"Erro ao formatar prompt personalizada: {str(e)}")
            logger.error("Usando prompt padrão como fallback")
            # Continuar para usar a prompt padrão em caso de erro
    else:
        logger.info("Prompt personalizada não encontrada. Usando prompt padrão")
    
    # Se não existir prompt personalizada ou houve erro na formatação, usar a padrão
    prompt = f"""
Analise o currículo abaixo para o candidato {nome} que está se aplicando para a vaga de {cargo}.

Detalhes do candidato:
- Nome: {nome}
- Email: {email}
- Telefone: {telefone}
- Cargo pretendido: {cargo}

Respostas completas do formulário:
{respostas}

Currículo:
{text}

Responda às seguintes perguntas:
1. Quais são as principais habilidades e competências do candidato?
2. O candidato tem experiência relevante para a vaga de {cargo}? Liste as experiências relevantes.
3. O candidato tem formação adequada para a vaga? Descreva a formação.
4. Quais são os pontos fortes do candidato que o tornam adequado para esta posição?
5. Há alguma lacuna ou ponto de atenção no perfil do candidato?
6. Em uma escala de 0 a 10, qual seria a pontuação deste candidato para a vaga, considerando o alinhamento do perfil?
7. O candidato deve ser chamado para entrevista? Por quê?

Forneça uma análise detalhada e objetiva baseada apenas nas informações do currículo.
"""
    return prompt

def analyze_with_gemini(text, form_data):
    """
    Analisa o CV usando a API do Gemini.
    """
    try:
        logger.info("Iniciando análise com o Google Gemini")
        
        # Obter a chave API
        api_key = get_gemini_key()
        if not api_key:
            logger.error("Chave API do Gemini não disponível")
            return {"error": "Chave API do Gemini não configurada"}
        
        # Configurar o cliente Gemini
        genai.configure(api_key=api_key)
        # Utilizar o modelo gemini-1.5-flash que está disponível
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Gerar o prompt para análise
        prompt = get_prompt(text, form_data)
        
        # Enviar para análise
        logger.info("Enviando CV para análise com Gemini")
        response = model.generate_content(prompt)
        
        # Verificar e processar a resposta
        if hasattr(response, 'text'):
            logger.info("Análise com Gemini concluída com sucesso")
            return response.text
        else:
            logger.error("Formato de resposta do Gemini inesperado")
            return {"error": "Formato de resposta do Gemini inesperado"}
    except Exception as e:
        logger.error(f"Erro durante a análise com Gemini: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": f"Erro durante a análise com Gemini: {str(e)}"}

def analyze_with_openai(text, form_data):
    """
    Analisa o CV usando a API da OpenAI.
    """
    try:
        logger.info("Iniciando análise com a OpenAI")
        
        # Obter a chave API
        api_key = get_openai_key()
        if not api_key:
            logger.error("Chave API da OpenAI não disponível")
            return {"error": "Chave API da OpenAI não configurada"}
        
        # Configurar o cliente OpenAI
        client = openai.OpenAI(api_key=api_key)
        
        # Gerar o prompt para análise
        prompt = get_prompt(text, form_data)
        
        # Enviar para análise
        logger.info("Enviando CV para análise com OpenAI")
        response = client.chat.completions.create(
            model="gpt-4",  # ou outro modelo como "gpt-3.5-turbo"
            messages=[
                {"role": "system", "content": "Você é um assistente especializado em análise de currículos."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=1500
        )
        
        # Verificar e processar a resposta
        if response.choices and response.choices[0].message.content:
            logger.info("Análise com OpenAI concluída com sucesso")
            return response.choices[0].message.content
        else:
            logger.error("Resposta da OpenAI vazia ou inválida")
            return {"error": "Resposta da OpenAI vazia ou inválida"}
    except Exception as e:
        logger.error(f"Erro durante a análise com OpenAI: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": f"Erro durante a análise com OpenAI: {str(e)}"}

def analyze_with_claude(text, form_data):
    """
    Analisa o CV usando a API do Anthropic Claude.
    """
    try:
        logger.info("Iniciando análise com o Anthropic Claude")
        
        # Obter a chave API
        api_key = get_claude_key()
        if not api_key:
            logger.error("Chave API do Claude não disponível")
            return {"error": "Chave API do Claude não configurada"}
        
        # Configurar o cliente Anthropic
        client = Anthropic(api_key=api_key)
        
        # Gerar o prompt para análise
        prompt = get_prompt(text, form_data)
        
        # Enviar para análise usando a API de Completions
        logger.info("Enviando CV para análise com Claude")
        response = client.completions.create(
            model="claude-2",  # Usando modelo Claude 2 que é compatível com a API antiga
            max_tokens_to_sample=1500,
            temperature=0.2,
            prompt=f"\n\nHuman: {prompt}\n\nAssistant:"
        )
        
        # Verificar e processar a resposta para a API de completions
        logger.info("Análise com Claude concluída com sucesso")
        if hasattr(response, 'completion'):
            return response.completion
        else:
            logger.error("Formato de resposta do Claude inesperado")
            return {"error": "Formato de resposta do Claude inesperado"}
    except Exception as e:
        error_msg = str(e)
        logger.error(f"Erro na análise com Claude: {error_msg}")
        logger.error(traceback.format_exc())
        return {"error": f"Erro na análise com Claude: {error_msg}"}

def analyze_with_deepseek(text, form_data):
    """
    Analisa o CV usando a API do DeepSeek via chamadas HTTP diretas.
    """
    try:
        logger.info("Iniciando análise com o DeepSeek")
        
        # Obter a chave API
        api_key = get_deepseek_key()
        if not api_key:
            logger.error("Chave API do DeepSeek não disponível")
            return {"error": "Chave API do DeepSeek não configurada"}
        
        # Gerar o prompt para análise
        prompt = get_prompt(text, form_data)
        
        # Configurar cabeçalhos e payload para a API DeepSeek
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "max_tokens": 1500
        }
        
        # Enviar para análise
        logger.info("Enviando CV para análise com DeepSeek")
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload)
        )
        
        # Verificar e processar a resposta
        if response.status_code == 200:
            response_data = response.json()
            if response_data.get("choices") and len(response_data["choices"]) > 0:
                content = response_data["choices"][0].get("message", {}).get("content", "")
                if content:
                    logger.info("Análise com DeepSeek concluída com sucesso")
                    return content
                else:
                    logger.error("Resposta do DeepSeek vazia")
                    return {"error": "Resposta do DeepSeek vazia"}
            else:
                logger.error("Formato de resposta do DeepSeek inesperado")
                return {"error": "Formato de resposta do DeepSeek inesperado"}
        else:
            logger.error(f"Erro na API do DeepSeek: {response.status_code} - {response.text}")
            return {"error": f"Erro na API do DeepSeek: {response.status_code}"}
    except Exception as e:
        logger.error(f"Erro durante a análise com DeepSeek: {str(e)}")
        logger.error(traceback.format_exc())
        return {"error": f"Erro durante a análise com DeepSeek: {str(e)}"}

def validate_cv_content(file_path):
    """
    Valida se um arquivo é realmente um currículo usando IA.
    Retorna um dicionário com 'valid' (boolean) e 'message' (string).
    """
    try:
        logger.info(f"Iniciando validação de CV: {file_path}")
        
        # Verificar se o arquivo existe
        if not os.path.exists(file_path):
            logger.error(f"Arquivo não encontrado: {file_path}")
            return {
                'valid': False, 
                'message': 'Arquivo não encontrado. Tente fazer upload novamente.'
            }
        
        # Obter provedor de IA
        provider = get_ai_provider()
        logger.info(f"Usando provedor de IA: {provider}")
        
        # Obter prompt personalizada da planilha
        custom_validation_prompt = get_validation_prompt()
        
        # Analisar com o provedor configurado (enviando o arquivo)
        if provider == 'gemini':
            result = validate_with_gemini_file(file_path, custom_validation_prompt)
        elif provider == 'openai':
            result = validate_with_openai_file(file_path, custom_validation_prompt)
        elif provider == 'claude':
            result = validate_with_claude_file(file_path, custom_validation_prompt)
        elif provider == 'deepseek':
            result = validate_with_deepseek_file(file_path, custom_validation_prompt)
        else:
            logger.error(f"Provedor de IA não suportado: {provider}")
            return {
                'valid': False, 
                'message': 'Erro de configuração do sistema. Contacte o administrador.'
            }
        
        # Processar resultado
        if isinstance(result, dict) and 'error' in result:
            logger.error(f"Erro na validação: {result['error']}")
            return {
                'valid': False, 
                'message': 'Erro ao validar o arquivo. Tente novamente.'
            }
        
        # Log da resposta completa da IA para debug
        logger.info(f"Resposta completa da IA: '{result}'")
        
        # Analisar resposta da IA
        response_text = str(result).upper()
        logger.info(f"Resposta em maiúsculas: '{response_text}'")
        
        # Verificar se a IA conseguiu analisar o arquivo
        if 'NÃO RECEBI' in response_text or 'NOT RECEIVED' in response_text or 'NO FILE' in response_text:
            logger.warning("IA não conseguiu receber/analisar o arquivo")
            return {
                'valid': False, 
                'message': 'Erro ao enviar arquivo para análise. Tente novamente.'
            }
        
        # Procurar por padrões específicos de resposta válida/inválida
        # Deve começar com VÁLIDO ou INVÁLIDO seguido de hífen
        if response_text.strip().startswith('VÁLIDO -') or response_text.strip().startswith('VALIDO -') or response_text.strip().startswith('VALID -'):
            logger.info("CV validado como válido")
            return {
                'valid': True, 
                'message': 'Currículo válido detectado. Pode prosseguir com a submissão.'
            }
        elif response_text.strip().startswith('INVÁLIDO -') or response_text.strip().startswith('INVALIDO -') or response_text.strip().startswith('INVALID -'):
            logger.info("CV validado como inválido")
            # Extrair explicação se disponível
            explanation = result.split('-', 1)[1].strip() if '-' in str(result) else "Não parece ser um currículo válido."
            return {
                'valid': False, 
                'message': f'Este arquivo não parece ser um currículo. {explanation}'
            }
        # Fallback: procurar apenas as palavras (menos rigoroso)
        elif ('VÁLIDO' in response_text or 'VALIDO' in response_text) and 'VÁLIDO/INVÁLIDO' not in response_text:
            logger.info("CV validado como válido (fallback)")
            return {
                'valid': True, 
                'message': 'Currículo válido detectado. Pode prosseguir com a submissão.'
            }
        elif ('INVÁLIDO' in response_text or 'INVALIDO' in response_text) and 'VÁLIDO/INVÁLIDO' not in response_text:
            logger.info("CV validado como inválido (fallback)")
            explanation = result.split('-', 1)[1].strip() if '-' in str(result) else "Não parece ser um currículo válido."
            return {
                'valid': False, 
                'message': f'Este arquivo não parece ser um currículo. {explanation}'
            }
        else:
            logger.warning(f"Resposta da IA não reconhecida: '{result}'")
            logger.warning("Não foi encontrado 'VÁLIDO', 'VALIDO', 'VALID', 'INVÁLIDO', 'INVALIDO' ou 'INVALID' na resposta")
            return {
                'valid': False, 
                'message': 'Não foi possível validar o arquivo. Verifique se é um currículo e tente novamente.'
            }
        
    except Exception as e:
        logger.error(f"Erro na validação de CV: {str(e)}")
        logger.error(traceback.format_exc())
        return {
            'valid': False, 
            'message': 'Erro interno na validação. Tente novamente.'
        }

def validate_with_gemini(prompt):
    """Valida CV usando Gemini"""
    try:
        api_key = get_gemini_key()
        if not api_key:
            return {"error": "Chave API do Gemini não configurada"}
        
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        response = model.generate_content(prompt)
        return response.text if hasattr(response, 'text') else {"error": "Resposta inválida"}
    except Exception as e:
        return {"error": str(e)}

def validate_with_openai(prompt):
    """Valida CV usando OpenAI"""
    try:
        api_key = get_openai_key()
        if not api_key:
            return {"error": "Chave API da OpenAI não configurada"}
        
        client = openai.OpenAI(api_key=api_key)
        
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "Você é um especialista em análise de documentos."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=200
        )
        
        return response.choices[0].message.content if response.choices else {"error": "Resposta vazia"}
    except Exception as e:
        return {"error": str(e)}

def validate_with_claude(prompt):
    """Valida CV usando Claude"""
    try:
        api_key = get_claude_key()
        if not api_key:
            return {"error": "Chave API do Claude não configurada"}
        
        client = Anthropic(api_key=api_key)
        
        response = client.completions.create(
            model="claude-2",
            max_tokens_to_sample=200,
            temperature=0.1,
            prompt=f"\n\nHuman: {prompt}\n\nAssistant:"
        )
        
        return response.completion if hasattr(response, 'completion') else {"error": "Resposta inválida"}
    except Exception as e:
        return {"error": str(e)}

def validate_with_deepseek(prompt):
    """Valida CV usando DeepSeek"""
    try:
        api_key = get_deepseek_key()
        if not api_key:
            return {"error": "Chave API do DeepSeek não configurada"}
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
            "max_tokens": 200
        }
        
        response = requests.post(
            "https://api.deepseek.com/v1/chat/completions",
            headers=headers,
            data=json.dumps(payload)
        )
        
        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"] if data.get("choices") else {"error": "Resposta vazia"}
        else:
            return {"error": f"Erro API: {response.status_code}"}
    except Exception as e:
        return {"error": str(e)}

def validate_with_gemini_file(file_path, custom_prompt=None):
    """Valida CV usando Gemini com upload de arquivo"""
    try:
        api_key = get_gemini_key()
        if not api_key:
            return {"error": "Chave API do Gemini não configurada"}
        
        genai.configure(api_key=api_key)
        
        # Upload do arquivo para o Gemini
        logger.info(f"Fazendo upload do arquivo para Gemini: {file_path}")
        uploaded_file = genai.upload_file(file_path)
        logger.info(f"Arquivo enviado com sucesso. URI: {uploaded_file.uri}")
        
        # Preparar prompt
        if custom_prompt:
            prompt = custom_prompt
        else:
            prompt = """
Analise o arquivo anexado e determine se é um currículo/CV válido.

Um currículo válido deve conter pelo menos algumas das seguintes informações:
- Dados pessoais (nome, contacto)
- Experiência profissional ou histórico de trabalho
- Formação académica ou educação
- Competências ou habilidades
- Informações sobre carreira profissional

Responda APENAS com:
- "VÁLIDO" se for um currículo
- "INVÁLIDO" se não for um currículo (ex: foto, documento pessoal, carta, etc.)

Seguido de uma breve explicação (máximo 50 palavras).

Formato da resposta: VÁLIDO/INVÁLIDO - explicação
"""
        
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content([prompt, uploaded_file])
        
        # Limpar arquivo do Gemini
        genai.delete_file(uploaded_file.name)
        logger.info("Arquivo removido do Gemini")
        
        return response.text if hasattr(response, 'text') else {"error": "Resposta inválida"}
    except Exception as e:
        logger.error(f"Erro na validação com Gemini: {str(e)}")
        return {"error": str(e)}

def validate_with_openai_file(file_path, custom_prompt=None):
    """Valida CV usando OpenAI - extrai texto primeiro pois OpenAI não aceita upload direto de arquivos"""
    try:
        # Extrair texto do arquivo
        text = extract_text_from_file(file_path)
        
        if not text or len(text.strip()) < 50:
            return {"error": "Arquivo muito pequeno ou sem texto"}
        
        # Preparar prompt
        if custom_prompt:
            try:
                prompt = custom_prompt.format(text=text[:2000] + "...")
            except:
                prompt = f"Analise o seguinte texto de um arquivo e determine se é um currículo válido:\n\n{text[:2000]}..."
        else:
            prompt = f"""
Analise o seguinte texto extraído de um arquivo e determine se é um currículo/CV válido.

Um currículo válido deve conter pelo menos algumas das seguintes informações:
- Dados pessoais (nome, contacto)
- Experiência profissional ou histórico de trabalho
- Formação académica ou educação
- Competências ou habilidades
- Informações sobre carreira profissional

Texto a analisar:
{text[:2000]}...

Responda APENAS com:
- "VÁLIDO" se for um currículo
- "INVÁLIDO" se não for um currículo (ex: foto, documento pessoal, carta, etc.)

Seguido de uma breve explicação (máximo 50 palavras).

Formato da resposta: VÁLIDO/INVÁLIDO - explicação
"""
        
        return validate_with_openai(prompt)
    except Exception as e:
        return {"error": str(e)}

def validate_with_claude_file(file_path, custom_prompt=None):
    """Valida CV usando Claude - extrai texto primeiro pois Claude não aceita upload direto de arquivos"""
    try:
        # Extrair texto do arquivo
        text = extract_text_from_file(file_path)
        
        if not text or len(text.strip()) < 50:
            return {"error": "Arquivo muito pequeno ou sem texto"}
        
        # Preparar prompt - sempre usar formato específico para Claude
        if custom_prompt and '{text}' in custom_prompt:
            try:
                prompt = custom_prompt.format(text=text[:2000] + "...")
            except:
                prompt = f"Analise o seguinte texto extraído de um arquivo e determine se é um currículo válido:\n\n{text[:2000]}..."
        else:
            # Usar prompt específica que funciona bem com Claude
            prompt = f"""
Analise o seguinte texto extraído de um arquivo e determine se é um currículo/CV válido.

Um currículo válido deve conter pelo menos algumas das seguintes informações:
- Dados pessoais (nome, contacto)
- Experiência profissional ou histórico de trabalho
- Formação académica ou educação
- Competências ou habilidades
- Informações sobre carreira profissional

Texto a analisar:
{text[:2000]}...

Responda EXATAMENTE no formato:
VÁLIDO - [explicação breve] OU INVÁLIDO - [explicação breve]

Não inclua outras informações na resposta.
"""
        
        return validate_with_claude(prompt)
    except Exception as e:
        return {"error": str(e)}

def validate_with_deepseek_file(file_path, custom_prompt=None):
    """Valida CV usando DeepSeek - extrai texto primeiro pois DeepSeek não aceita upload direto de arquivos"""
    try:
        # Extrair texto do arquivo
        text = extract_text_from_file(file_path)
        
        if not text or len(text.strip()) < 50:
            return {"error": "Arquivo muito pequeno ou sem texto"}
        
        # Preparar prompt
        if custom_prompt:
            try:
                prompt = custom_prompt.format(text=text[:2000] + "...")
            except:
                prompt = f"Analise o seguinte texto de um arquivo e determine se é um currículo válido:\n\n{text[:2000]}..."
        else:
            prompt = f"""
Analise o seguinte texto extraído de um arquivo e determine se é um currículo/CV válido.

Um currículo válido deve conter pelo menos algumas das seguintes informações:
- Dados pessoais (nome, contacto)
- Experiência profissional ou histórico de trabalho
- Formação académica ou educação
- Competências ou habilidades
- Informações sobre carreira profissional

Texto a analisar:
{text[:2000]}...

Responda APENAS com:
- "VÁLIDO" se for um currículo
- "INVÁLIDO" se não for um currículo (ex: foto, documento pessoal, carta, etc.)

Seguido de uma breve explicação (máximo 50 palavras).

Formato da resposta: VÁLIDO/INVÁLIDO - explicação
"""
        
        return validate_with_deepseek(prompt)
    except Exception as e:
        return {"error": str(e)}
import gspread
from google.oauth2.service_account import Credentials
import datetime
import os
import logging
import traceback
import json
import time
import threading
from utils.credentials_helper import get_credentials
from utils.file_cache import with_file_cache, default_file_cache

# Configurar logger
logger = logging.getLogger('formulario_culsen.sheets')

# Define scopes
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

# Get current directory
current_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ===== SISTEMA DE CACHE EM MEMÓRIA =====
class MemoryCache:
    def __init__(self):
        self._cache = {}
        self._timestamps = {}
        self._lock = threading.Lock()
        self.default_ttl = 300  # 5 minutos por padrão
        self.config_ttl = 600   # 10 minutos para configurações
        self.candidates_ttl = 180  # 3 minutos para candidatos
        
    def get(self, key):
        """Obtém um valor do cache se ainda for válido"""
        with self._lock:
            if key not in self._cache:
                return None
                
            # Verificar se o cache expirou
            timestamp = self._timestamps.get(key, 0)
            ttl = self._get_ttl_for_key(key)
            
            if time.time() - timestamp > ttl:
                # Cache expirado, remover
                del self._cache[key]
                del self._timestamps[key]
                logger.info(f"Cache expirado para chave: {key}")
                return None
                
            logger.info(f"Cache hit para chave: {key}")
            return self._cache[key]
    
    def set(self, key, value):
        """Define um valor no cache"""
        with self._lock:
            self._cache[key] = value
            self._timestamps[key] = time.time()
            logger.info(f"Cache atualizado para chave: {key}")
    
    def invalidate(self, key):
        """Remove uma chave específica do cache"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                del self._timestamps[key]
                logger.info(f"Cache invalidado para chave: {key}")
    
    def invalidate_pattern(self, pattern):
        """Remove todas as chaves que contêm o padrão"""
        with self._lock:
            keys_to_remove = [k for k in self._cache.keys() if pattern in k]
            for key in keys_to_remove:
                del self._cache[key]
                del self._timestamps[key]
                logger.info(f"Cache invalidado para chave: {key}")
    
    def clear(self):
        """Limpa todo o cache"""
        with self._lock:
            self._cache.clear()
            self._timestamps.clear()
            logger.info("Cache completamente limpo")
    
    def _get_ttl_for_key(self, key):
        """Retorna o TTL apropriado baseado na chave"""
        if 'config' in key.lower():
            return self.config_ttl
        elif 'candidates' in key.lower() or 'candidate_' in key.lower():
            return self.candidates_ttl
        else:
            return self.default_ttl
    
    def get_stats(self):
        """Retorna estatísticas do cache"""
        with self._lock:
            return {
                'total_keys': len(self._cache),
                'keys': list(self._cache.keys()),
                'memory_usage_estimate': sum(len(str(v)) for v in self._cache.values())
            }

# Instância global do cache
cache = MemoryCache()

def with_cache_fallback(cache_key, fetch_function, force_refresh=False):
    """
    Decorator/helper para implementar cache com fallback
    
    Args:
        cache_key: Chave para o cache
        fetch_function: Função para buscar dados se não estiver em cache
        force_refresh: Se True, força a atualização do cache
    """
    try:
        # Se não for refresh forçado, tentar cache primeiro
        if not force_refresh:
            cached_data = cache.get(cache_key)
            if cached_data is not None:
                return cached_data
        
        # Buscar dados frescos
        logger.info(f"Buscando dados frescos para: {cache_key}")
        fresh_data = fetch_function()
        
        # Salvar no cache
        cache.set(cache_key, fresh_data)
        
        return fresh_data
        
    except Exception as e:
        logger.error(f"Erro ao buscar dados frescos para {cache_key}: {str(e)}")
        
        # Em caso de erro, tentar usar cache mesmo que expirado
        with cache._lock:
            if cache_key in cache._cache:
                logger.warning(f"Usando cache expirado devido a erro para: {cache_key}")
                return cache._cache[cache_key]
        
        # Se não há cache, re-raise o erro
        raise e

def get_sheet_client():
    """Returns an authenticated Google Sheets client"""
    try:
        logger.info("Tentando autenticar com Google Sheets")
        
        credentials = get_credentials(SCOPES)
        if not credentials:
            raise FileNotFoundError("Não foi possível obter credenciais válidas")
            
        client = gspread.authorize(credentials)
        logger.info("Autenticação bem-sucedida")
        return client
    except Exception as e:
        logger.error(f"Erro ao autenticar com Google: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def get_config(force_refresh=False):
    """Get configuration values from the Config sheet with file caching"""
    def _fetch_config():
        logger.info("Obtendo configurações da planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        logger.info(f"Tentando abrir a planilha com ID: {SPREADSHEET_ID}")
        
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        try:
            logger.info("Tentando acessar a aba 'Config'")
            config_sheet = sheet.worksheet("Config")
            
            # Obter todos os valores da planilha como células brutas
            logger.info("Lendo todos os valores da aba Config")
            all_values = config_sheet.get_all_values()
            
            # Converter para dicionário
            config = {}
            
            # Processar diretamente cada linha, considerando que a coluna A contém a chave e a coluna B o valor
            for row in all_values:
                if len(row) >= 2 and row[0]:  # Se tiver pelo menos duas colunas e a chave não estiver vazia
                    key = row[0]
                    value = row[1] if len(row) > 1 and row[1] else ""
                    config[key] = value
                    logger.info(f"Configuração carregada: {key} = {value}")
            
            logger.info(f"Configurações carregadas com sucesso: {json.dumps(config, ensure_ascii=False)}")
            return config
        except Exception as e:
            logger.warning(f"Erro ao acessar aba Config: {str(e)}. Usando configurações padrão.")
            return {}
    
    return with_file_cache('config_data', _fetch_config, force_refresh)

def save_form_data(form_data):
    """Save form data to Google Sheets"""
    try:
        logger.info("Iniciando salvamento de dados do formulário")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        logger.info(f"Tentando abrir a planilha com ID: {SPREADSHEET_ID}")
        
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        try:
            logger.info("Tentando acessar a aba 'Respostas do Formulário 2'")
            form_sheet = sheet.worksheet("Respostas do Formulário 2")
        except gspread.exceptions.WorksheetNotFound:
            # Se a aba não existir, tenta Respostas do Formulário 1
            logger.info("Aba 'Respostas do Formulário 2' não encontrada. Tentando 'Respostas do Formulário 1'")
            try:
                form_sheet = sheet.worksheet("Respostas do Formulário 1")
            except gspread.exceptions.WorksheetNotFound:
                # Se ainda não existir, tenta Sheet1 ou cria nova
                logger.info("Tentando acessar a primeira aba ou criar nova aba")
                try:
                    form_sheet = sheet.get_worksheet(0)  # Primeira aba
                except:
                    form_sheet = sheet.add_worksheet(title="Respostas do Formulário", rows=1000, cols=50)
        
        # Define os cabeçalhos exatos da planilha existente
        expected_headers = [
            'Carimbo de data/hora',
            'Nome completo:',
            'Email de contacto:',
            'Número de telefone:',
            'Morada completa:',
            'Data de nascimento:',
            'Tem carta de condução válida?',
            'Tem experiência com cuidados a idosos e/ou pessoas dependentes?',
            'Se sim, tipo de experiência:',
            'Duração total da experiência:',
            'Funções desempenhadas:',
            'É cidadão português?',
            'Se não, está legalmente autorizado(a) a trabalhar em Portugal?',
            'Documento que possui:',
            'Há quanto tempo está em Portugal?',
            'Disponibilidade para trabalhar como prestador de serviços (recibos verdes)?',
            'Tem formação na área da saúde/cuidados a idosos?',
            'Tipo de formação:',
            'Nome da entidade formadora:',
            'Ano de conclusão:',
            'Dias disponíveis para trabalhar:',
            'Turnos disponíveis:',
            'Carregue aqui o seu CV',
            'Zona de residência atual:',
            'Endereço de email',
            'Erro: Link CV ausente ou inválido',
            'STATUS',
            'Classificacao IA',
            'Justificacao IA',
            'Horarios Sugeridos',
            'Email Enviado',
            'Provedor IA'
        ]
        
        # Verificar se já existem cabeçalhos
        logger.info("Verificando cabeçalhos existentes")
        headers = form_sheet.row_values(1)
        logger.info(f"Cabeçalhos encontrados: {headers}")
        
        # Se não existem cabeçalhos, adiciona-os
        if not headers:
            logger.info("Nenhum cabeçalho encontrado. Adicionando cabeçalhos.")
            form_sheet.append_row(expected_headers)
        
        # Prepare row data - usando os índices dos cabeçalhos esperados
        logger.info("Preparando dados da linha para inserção")
        row_data = [""] * len(expected_headers)
        
        # Preencher os dados nas posições corretas
        row_data[0] = form_data.get('data', '')                                    # Carimbo de data/hora
        row_data[1] = form_data.get('nome', '')                                    # Nome completo:
        row_data[2] = form_data.get('email', '')                                   # Email de contacto:
        row_data[3] = form_data.get('telefone', '')                                # Número de telefone:
        row_data[4] = form_data.get('morada', '')                                  # Morada completa:
        row_data[5] = form_data.get('data_nascimento', '')                         # Data de nascimento:
        row_data[6] = form_data.get('carta_conducao', '')                          # Tem carta de condução válida?
        row_data[7] = form_data.get('experiencia', '')                             # Tem experiência com cuidados a idosos e/ou pessoas dependentes?
        row_data[8] = form_data.get('tipo_experiencia', '')                        # Se sim, tipo de experiência:
        row_data[9] = form_data.get('duracao_experiencia', '')                     # Duração total da experiência:
        row_data[10] = form_data.get('funcoes', '')                                # Funções desempenhadas:
        row_data[11] = form_data.get('cidadao_portugues', '')                      # É cidadão português?
        row_data[12] = form_data.get('autorizacao_portugal', '')                   # Se não, está legalmente autorizado(a) a trabalhar em Portugal?
        row_data[13] = form_data.get('documento', '')                              # Documento que possui:
        row_data[14] = form_data.get('tempo_portugal', '')                         # Há quanto tempo está em Portugal?
        row_data[15] = form_data.get('recibos_verdes', '')                         # Disponibilidade para trabalhar como prestador de serviços (recibos verdes)?
        row_data[16] = form_data.get('formacao_area', '')                          # Tem formação na área da saúde/cuidados a idosos?
        row_data[17] = form_data.get('tipo_formacao', '')                          # Tipo de formação:
        row_data[18] = form_data.get('entidade_formadora', '')                     # Nome da entidade formadora:
        row_data[19] = form_data.get('ano_conclusao', '')                          # Ano de conclusão:
        row_data[20] = form_data.get('dias_disponiveis', '')                       # Dias disponíveis para trabalhar:
        row_data[21] = form_data.get('turnos_disponiveis', '')                     # Turnos disponíveis:
        row_data[22] = "Enviado pelo formulário web"                               # Carregue aqui o seu CV
        row_data[23] = form_data.get('residencia', '')                             # Zona de residência atual:
        row_data[24] = form_data.get('email', '')                                  # Endereço de email
        row_data[25] = ""                                                          # Erro: Link CV ausente ou inválido
        row_data[26] = "NOVO"                                                      # STATUS
        row_data[27] = form_data.get('classificacao', '')                          # Classificacao IA
        row_data[28] = form_data.get('justificacao', '')                           # Justificacao IA
        row_data[29] = ""                                                          # Horarios Sugeridos
        row_data[30] = "Não"                                                       # Email Enviado
        
        # Adicionando provedor de IA se presente
        if 'provider' in form_data:
            # Verificar se já existe coluna para o provedor de IA
            provider_col = None
            for i, header in enumerate(expected_headers):
                if header == 'Provedor IA':
                    provider_col = i
                    break
            
            # Se a coluna existir, preencher o valor
            if provider_col is not None:
                row_data[provider_col] = form_data.get('provider', '')
            # Se não existir, adicionar nova coluna
            else:
                expected_headers.append('Provedor IA')
                row_data.append(form_data.get('provider', ''))
                # Atualizar cabeçalhos na planilha
                form_sheet.append_row(expected_headers, table_range='A1')
        
        # Atualizar o Link do CV na coluna apropriada
        if form_data.get('cv_url'):
            logger.info(f"Adicionando URL do CV: {form_data.get('cv_url')}")
            # Não há coluna específica para o link do CV, mas poderíamos adicionar na coluna de erros ou outra
            row_data[25] = form_data.get('cv_url', '')                            # Usamos a coluna de erro para o link
        
        # Append the row to the sheet
        logger.info("Adicionando linha à planilha")
        form_sheet.append_row(row_data)
        logger.info("Dados salvos com sucesso na planilha")
        
        # Invalidar cache de candidatos após adicionar novo
        cache.invalidate('all_candidates')
        logger.info("Cache de candidatos invalidado após nova submissão")
        
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar dados do formulário: {str(e)}")
        logger.error(traceback.format_exc())
        raise

def get_available_slots(days_ahead=7):
    """
    Get available interview slots from the Horarios sheet
    for the next 'days_ahead' days (default: 7 days)
    """
    try:
        logger.info(f"Buscando horários disponíveis para os próximos {days_ahead} dias")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        logger.info(f"Tentando abrir a planilha com ID: {SPREADSHEET_ID}")
        
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        try:
            logger.info("Tentando acessar a aba 'Horarios'")
            horarios_sheet = sheet.worksheet("Horarios")
        except gspread.exceptions.WorksheetNotFound:
            logger.warning("Aba 'Horarios' não encontrada. Criando aba.")
            horarios_sheet = sheet.add_worksheet(title="Horarios", rows=100, cols=10)
            # Adicionar cabeçalhos
            horarios_sheet.append_row(["Dia da Semana", "Início", "Fim", "Entrevistador", "Candidato", "Status"])
            logger.info("Aba 'Horarios' criada com sucesso.")
        
        # Get all records from Horarios sheet
        logger.info("Lendo registros da aba Horarios")
        records = horarios_sheet.get_all_records()
        logger.info(f"Encontrados {len(records)} registros de horários")
        
        # Get interview duration from Config
        logger.info("Obtendo duração da entrevista das configurações")
        config = get_config()
        interview_duration = int(config.get('DURACAO_ENTREVISTA_MIN', 30))
        logger.info(f"Duração da entrevista configurada: {interview_duration} minutos")
        
        # Get current date and time
        current_date = datetime.datetime.now()
        logger.info(f"Data atual: {current_date}")
        
        # Calculate the end date for our search
        end_date = current_date + datetime.timedelta(days=days_ahead)
        logger.info(f"Data final para busca de horários: {end_date}")
        
        # List of weekdays in Portuguese
        weekdays_pt = {
            0: "Segunda-feira",
            1: "Terça-feira",
            2: "Quarta-feira",
            3: "Quinta-feira",
            4: "Sexta-feira",
            5: "Sábado",
            6: "Domingo"
        }
        
        # Find available slots
        available_slots = []
        
        for day_offset in range(days_ahead):
            check_date = current_date + datetime.timedelta(days=day_offset)
            weekday_name = weekdays_pt[check_date.weekday()]
            logger.info(f"Verificando horários para {weekday_name} ({check_date.strftime('%d/%m/%Y')})")
            
            # Filter records for this weekday
            # Ajustado para usar os nomes de colunas da sua planilha
            day_slots = [r for r in records if r['Dia da Semana'] == weekday_name and not r.get('Entrevistador')]
            logger.info(f"Encontrados {len(day_slots)} horários disponíveis para {weekday_name}")
            
            for slot in day_slots:
                # Usando os nomes de colunas da sua planilha
                start_time = slot['Início']
                end_time = slot['Fim']
                logger.info(f"Horário disponível: {start_time} - {end_time}")
                
                # Format date and time information for this slot
                slot_date = check_date.strftime("%d/%m/%Y")
                available_slots.append({
                    'date': slot_date,
                    'weekday': weekday_name,
                    'start_time': start_time,
                    'end_time': end_time
                })
                
                # Limit to 3 slots
                if len(available_slots) >= 3:
                    logger.info(f"Limite de 3 horários atingido. Retornando {len(available_slots)} horários.")
                    return available_slots
        
        logger.info(f"Retornando {len(available_slots)} horários disponíveis")
        return available_slots
    except Exception as e:
        logger.error(f"Erro ao obter horários disponíveis: {str(e)}")
        logger.error(traceback.format_exc())
        return [] 

def get_all_candidates(force_refresh=False):
    """
    Obtém todos os candidatos da planilha com file cache
    Retorna uma lista de dicionários com os dados de cada candidato
    """
    def _fetch_candidates():
        logger.info("Buscando todos os candidatos...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        logger.info(f"Tentando abrir a planilha com ID: {SPREADSHEET_ID}")
        
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        try:
            logger.info("Tentando acessar a aba 'Respostas do Formulário 2'")
            form_sheet = sheet.worksheet("Respostas do Formulário 2")
        except gspread.exceptions.WorksheetNotFound:
            # Se a aba não existir, tenta Respostas do Formulário 1
            logger.info("Aba 'Respostas do Formulário 2' não encontrada. Tentando 'Respostas do Formulário 1'")
            try:
                form_sheet = sheet.worksheet("Respostas do Formulário 1")
            except gspread.exceptions.WorksheetNotFound:
                # Se ainda não existir, tenta a primeira aba
                logger.info("Tentando acessar a primeira aba")
                form_sheet = sheet.get_worksheet(0)  # Primeira aba
        
        # Obter todas as linhas da planilha
        logger.info("Lendo todas as entradas da planilha")
        all_records = form_sheet.get_all_records()
        
        # Retornar a lista de candidatos com o índice
        candidatos = []
        for i, record in enumerate(all_records, start=2):  # Começa em 2 pois a linha 1 é o cabeçalho
            candidato = record.copy()
            candidato['index'] = i
            candidatos.append(candidato)
        
        logger.info(f"Total de {len(candidatos)} candidatos encontrados")
        return candidatos
    
    return with_file_cache('candidates_all', _fetch_candidates, force_refresh)

def get_candidate_by_index(row_index, force_refresh=False):
    """
    Obtém dados de um candidato específico pelo índice da linha com cache
    Retorna um dicionário com os dados do candidato
    """
    def _fetch_candidate():
        logger.info(f"Buscando candidato na linha {row_index}")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Tenta encontrar a aba correta
        try:
            form_sheet = sheet.worksheet("Respostas do Formulário 2")
        except gspread.exceptions.WorksheetNotFound:
            try:
                form_sheet = sheet.worksheet("Respostas do Formulário 1")
            except gspread.exceptions.WorksheetNotFound:
                form_sheet = sheet.get_worksheet(0)
        
        # Obter cabeçalhos
        headers = form_sheet.row_values(1)
        
        # Obter valores da linha do candidato
        values = form_sheet.row_values(row_index)
        
        # Se não tiver valores suficientes, retorna None
        if not values:
            logger.warning(f"Nenhum dado encontrado na linha {row_index}")
            return None
        
        # Construir dicionário do candidato
        candidato = {}
        for i, header in enumerate(headers):
            if i < len(values):
                candidato[header] = values[i]
            else:
                candidato[header] = ""
        
        # Mapear para os campos usados na aplicação
        form_data = {}
        form_data['index'] = row_index
        form_data['nome'] = candidato.get('Nome completo:', '')
        form_data['email'] = candidato.get('Email de contacto:', '') or candidato.get('Endereço de email', '')
        form_data['telefone'] = candidato.get('Número de telefone:', '')
        form_data['morada'] = candidato.get('Morada completa:', '')
        form_data['data_nascimento'] = candidato.get('Data de nascimento:', '')
        form_data['cv_url'] = candidato.get('Erro: Link CV ausente ou inválido', '') or candidato.get('Carregue aqui o seu CV', '')
        
        # Buscar campos de análise IA com diferentes possibilidades de nomes
        form_data['classificacao'] = (candidato.get('Classificacao IA', '') or 
                                     candidato.get('Classificação IA', '') or 
                                     candidato.get('classificacao', '') or
                                     candidato.get('Classificacao', ''))
        
        form_data['justificacao'] = (candidato.get('Justificacao IA', '') or 
                                    candidato.get('Justificação IA', '') or 
                                    candidato.get('justificacao', '') or
                                    candidato.get('Justificacao', ''))
        
        form_data['status'] = (candidato.get('STATUS', '') or 
                              candidato.get('Status', '') or 
                              candidato.get('status', ''))
        
        form_data['provider'] = (candidato.get('Provedor IA', '') or 
                                candidato.get('Provider IA', '') or 
                                candidato.get('provider', '') or
                                candidato.get('Provedor', ''))
        
        # Log para debug
        logger.info(f"Dados de análise IA encontrados - Classificação: '{form_data['classificacao']}', Justificação: {len(form_data['justificacao'])} chars, Provider: '{form_data['provider']}'")
        
        # Log dos cabeçalhos disponíveis para debug
        logger.info(f"Cabeçalhos disponíveis: {list(candidato.keys())}")
        
        # Dados adicionais do formulário
        form_data['carta_conducao'] = candidato.get('Tem carta de condução?', '')
        form_data['experiencia'] = candidato.get('Tem experiência com cuidados a idosos e/ou pessoas dependentes?', '')
        form_data['tipo_experiencia'] = candidato.get('Se sim, que tipo de experiência tem?', '')
        form_data['duracao_experiencia'] = candidato.get('Há quanto tempo tem experiência nesta área?', '')
        form_data['funcoes'] = candidato.get('Que funções já desempenhou?', '')
        form_data['cidadao_portugues'] = candidato.get('É cidadão português?', '')
        form_data['autorizacao_portugal'] = candidato.get('Se não, está legalmente autorizado(a) a trabalhar em Portugal?', '')
        form_data['documento'] = candidato.get('Documento que possui:', '')
        form_data['tempo_portugal'] = candidato.get('Há quanto tempo está em Portugal?', '')
        form_data['recibos_verdes'] = candidato.get('Disponibilidade para trabalhar como prestador de serviços (recibos verdes)?', '')
        form_data['formacao_area'] = candidato.get('Tem formação na área da saúde ou cuidados?', '')
        form_data['tipo_formacao'] = candidato.get('Se sim, que tipo de formação tem?', '')
        form_data['entidade_formadora'] = candidato.get('Entidade formadora:', '')
        form_data['ano_conclusao'] = candidato.get('Ano de conclusão:', '')
        form_data['formacao'] = candidato.get('Tem formação?', '')
        form_data['dias_disponiveis'] = candidato.get('Que dias da semana tem disponibilidade?', '')
        form_data['turnos_disponiveis'] = candidato.get('Que turnos tem disponibilidade?', '')
        form_data['residencia'] = candidato.get('Zona de residência atual:', '')
        form_data['data_submissao'] = candidato.get('Carimbo de data/hora', '')
        
        # Verificar se tem dados básicos
        if not form_data['nome'] or not form_data['email']:
            logger.warning(f"Dados incompletos para o candidato na linha {row_index}")
        
        logger.info(f"Candidato encontrado: {form_data['nome']}")
        return form_data
    
    return with_file_cache(f'candidate_{row_index}', _fetch_candidate, force_refresh)

def update_candidate_analysis(row_index, cv_analysis):
    """
    Atualiza a análise de um candidato na planilha
    """
    try:
        logger.info(f"Atualizando análise para candidato na linha {row_index}")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Tenta encontrar a aba correta
        try:
            form_sheet = sheet.worksheet("Respostas do Formulário 2")
        except gspread.exceptions.WorksheetNotFound:
            try:
                form_sheet = sheet.worksheet("Respostas do Formulário 1")
            except gspread.exceptions.WorksheetNotFound:
                form_sheet = sheet.get_worksheet(0)
        
        # Obter cabeçalhos para encontrar as colunas corretas
        headers = form_sheet.row_values(1)
        
        # Encontrar índices das colunas
        classificacao_col = None
        justificacao_col = None
        status_col = None
        provider_col = None
        
        for i, header in enumerate(headers, start=1):
            if header == 'Classificacao IA':
                classificacao_col = i
            elif header == 'Justificacao IA':
                justificacao_col = i
            elif header == 'STATUS':
                status_col = i
            elif header == 'Provedor IA':
                provider_col = i
        
        # Atualizar células
        if classificacao_col:
            form_sheet.update_cell(row_index, classificacao_col, cv_analysis.get('classificacao', 'Desconhecido'))
            logger.info(f"Classificação atualizada: {cv_analysis.get('classificacao', 'Desconhecido')}")
        
        if justificacao_col:
            form_sheet.update_cell(row_index, justificacao_col, cv_analysis.get('justificacao', ''))
            logger.info(f"Justificação atualizada")
        
        if status_col:
            # Atualizar o status com base na classificação
            classificacao = cv_analysis.get('classificacao', '')
            if classificacao == 'Aprovado':
                status = 'ANALISADO'
            elif classificacao == 'Rejeitado':
                status = 'REJEITADO'
            elif classificacao == 'Revisão':
                status = 'REVISÃO'
            else:
                status = 'NOVO'
            
            form_sheet.update_cell(row_index, status_col, status)
            logger.info(f"Status atualizado: {status}")
        
        # Atualizar o provedor de IA
        if 'provider' in cv_analysis:
            if provider_col:
                form_sheet.update_cell(row_index, provider_col, cv_analysis.get('provider', ''))
                logger.info(f"Provedor IA atualizado: {cv_analysis.get('provider', '')}")
            else:
                # Adicionar nova coluna para o provedor se não existir
                headers.append('Provedor IA')
                form_sheet.update_cell(1, len(headers), 'Provedor IA')
                form_sheet.update_cell(row_index, len(headers), cv_analysis.get('provider', ''))
                logger.info(f"Coluna de Provedor IA adicionada e valor atualizado: {cv_analysis.get('provider', '')}")
        
        logger.info(f"Análise atualizada com sucesso para o candidato na linha {row_index}")
        
        # Invalidar cache relacionado
        cache.invalidate(f'candidate_{row_index}')
        cache.invalidate('all_candidates')
        logger.info("Cache invalidado após atualização de análise")
        
        return True
    
    except Exception as e:
        logger.error(f"Erro ao atualizar análise: {str(e)}")
        logger.error(traceback.format_exc())
        return False 

def update_config(config_updates):
    """
    Atualiza as configurações na planilha
    config_updates: dicionário com as configurações a atualizar
    """
    try:
        logger.info(f"Atualizando configurações: {json.dumps(config_updates, ensure_ascii=False)}")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Config existe, caso contrário, criar
        try:
            config_sheet = sheet.worksheet("Config")
            logger.info("Aba Config encontrada")
        except gspread.exceptions.WorksheetNotFound:
            logger.info("Aba Config não encontrada. Criando nova aba.")
            config_sheet = sheet.add_worksheet(title="Config", rows=50, cols=2)
            # Adicionar cabeçalhos
            config_sheet.append_row(["CHAVE", "VALOR"])
        
        # Obter todos os dados da planilha, incluindo os valores das células
        all_values = config_sheet.get_all_values()
        if not all_values:
            # Planilha vazia, adicionar cabeçalhos
            config_sheet.append_row(["CHAVE", "VALOR"])
            all_values = [["CHAVE", "VALOR"]]
        
        # Criar um mapeamento de chaves para índices de linha
        key_to_row = {}
        for i, row in enumerate(all_values):
            if i == 0:  # Pular o cabeçalho
                continue
            if len(row) >= 1:
                key_to_row[row[0]] = i + 1  # +1 porque a linha 1 é o cabeçalho
        
        # Atualizar valores existentes e adicionar novos
        updates_made = 0
        
        for key, value in config_updates.items():
            if key in key_to_row:
                # Atualizar valor existente
                row_idx = key_to_row[key]
                logger.info(f"Atualizando configuração existente: {key}={value} na linha {row_idx}")
                config_sheet.update_cell(row_idx, 2, value)  # Coluna 2 = VALOR
                updates_made += 1
            else:
                # Adicionar nova configuração
                logger.info(f"Adicionando nova configuração: {key}={value}")
                config_sheet.append_row([key, value])
                updates_made += 1
        
        logger.info(f"Total de {updates_made} configurações atualizadas")
        return True
    
    except Exception as e:
        logger.error(f"Erro ao atualizar configurações: {str(e)}")
        logger.error(traceback.format_exc())
        return False 

def get_custom_prompt():
    """
    Obtém a prompt personalizada para análise de CV da aba Prompt da planilha
    Retorna None se a aba não existir ou se não houver prompt definida
    """
    try:
        logger.info("Tentando obter prompt personalizada da planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Prompt existe
        try:
            prompt_sheet = sheet.worksheet("Prompt")
            logger.info("Aba Prompt encontrada")
        except gspread.exceptions.WorksheetNotFound:
            # Se a aba não existir, criar nova com um template de prompt
            logger.info("Aba Prompt não encontrada. Criando nova aba com template de prompt.")
            prompt_sheet = sheet.add_worksheet(title="Prompt", rows=50, cols=1)
            
            # Template de prompt padrão para análise de CV
            default_prompt = """
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
            
            # Template de prompt para validação de CV
            validation_prompt = """
Analise o seguinte texto e determine se é um currículo/CV válido.

Um currículo válido deve conter pelo menos algumas das seguintes informações:
- Dados pessoais (nome, contacto)
- Experiência profissional ou histórico de trabalho
- Formação académica ou educação
- Competências ou habilidades
- Informações sobre carreira profissional

Texto a analisar:
{text}

Responda APENAS com:
- "VÁLIDO" se for um currículo
- "INVÁLIDO" se não for um currículo (ex: foto, documento pessoal, carta, etc.)

Seguido de uma breve explicação (máximo 50 palavras).

Formato da resposta: VÁLIDO/INVÁLIDO - explicação
"""
            
            # Adicionar os templates às células A1 e A2
            prompt_sheet.update_cell(1, 1, default_prompt)
            prompt_sheet.update_cell(2, 1, validation_prompt)
            logger.info("Templates de prompt adicionados à aba Prompt (A1: análise, A2: validação)")
        
        # Ler o conteúdo da célula A1
        prompt_text = prompt_sheet.cell(1, 1).value
        
        if not prompt_text:
            logger.warning("Prompt não encontrada ou vazia na célula A1 da aba Prompt")
            return None
        
        logger.info("Prompt personalizada obtida com sucesso")
        return prompt_text
    
    except Exception as e:
        logger.error(f"Erro ao obter prompt personalizada: {str(e)}")
        logger.error(traceback.format_exc())
        return None

def get_validation_prompt():
    """
    Obtém a prompt personalizada para validação de CV da célula A2 da aba Prompt da planilha
    Retorna None se a aba não existir ou se não houver prompt definida
    """
    try:
        logger.info("Tentando obter prompt de validação da planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Prompt existe
        try:
            prompt_sheet = sheet.worksheet("Prompt")
            logger.info("Aba Prompt encontrada")
        except gspread.exceptions.WorksheetNotFound:
            logger.warning("Aba Prompt não encontrada. Usando prompt de validação padrão.")
            return None
        
        # Ler o conteúdo da célula A2
        prompt_text = prompt_sheet.cell(2, 1).value
        
        if not prompt_text:
            logger.warning("Prompt de validação não encontrada ou vazia na célula A2 da aba Prompt")
            return None
        
        logger.info("Prompt de validação personalizada obtida com sucesso")
        return prompt_text
    
    except Exception as e:
        logger.error(f"Erro ao obter prompt de validação: {str(e)}")
        logger.error(traceback.format_exc())
        return None 

def get_dynamic_questions(force_refresh=False):
    """
    Obtém as perguntas dinâmicas da aba 'Perguntas' da planilha com file cache
    Retorna uma lista de dicionários com as configurações das perguntas
    """
    def _fetch_questions():
        logger.info("Tentando obter perguntas dinâmicas da planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Perguntas existe
        try:
            questions_sheet = sheet.worksheet("Perguntas")
            logger.info("Aba Perguntas encontrada")
        except gspread.exceptions.WorksheetNotFound:
            # Se a aba não existir, criar nova com template
            logger.info("Aba Perguntas não encontrada. Criando nova aba com template.")
            questions_sheet = sheet.add_worksheet(title="Perguntas", rows=100, cols=10)
            
            # Template de perguntas padrão
            headers = [
                "ID", "Secao", "Pergunta", "Tipo", "Obrigatoria", "Opcoes", "Placeholder", "Ajuda", "Ordem", "Ativa"
            ]
            questions_sheet.append_row(headers)
            
            # Exemplos de perguntas
            sample_questions = [
                ["nome", "Dados Pessoais", "Nome Completo", "text", "Sim", "", "Digite seu nome completo", "Nome como aparece no documento", "1", "Sim"],
                ["email", "Dados Pessoais", "Email de Contacto", "email", "Sim", "", "exemplo@email.com", "Email válido para contacto", "2", "Sim"],
                ["telefone", "Dados Pessoais", "Número de Telefone", "tel", "Sim", "", "+351 xxx xxx xxx", "Número com código do país", "3", "Sim"],
                ["experiencia", "Experiência", "Tem experiência com cuidados?", "radio", "Não", "Sim|Não", "", "Experiência prévia na área", "4", "Sim"],
                ["tipo_experiencia", "Experiência", "Tipo de experiência", "checkbox", "Não", "Apoio domiciliário|Lares ou instituições|Hospitalar|Outro", "", "Selecione todos que se aplicam", "5", "Sim"],
                ["formacao", "Formação", "Descreva sua formação", "textarea", "Sim", "", "Descreva detalhadamente...", "Informações sobre formação acadêmica", "6", "Sim"]
            ]
            
            for question in sample_questions:
                questions_sheet.append_row(question)
            
            logger.info("Template de perguntas adicionado à aba Perguntas")
        
        # Verificar se a planilha tem dados antes de tentar ler
        try:
            # Verificar se há pelo menos uma linha de cabeçalho
            all_values = questions_sheet.get_all_values()
            if not all_values or len(all_values) < 1:
                logger.warning("Aba Perguntas está vazia. Adicionando template.")
                # Adicionar template se estiver vazia
                headers = [
                    "ID", "Secao", "Pergunta", "Tipo", "Obrigatoria", "Opcoes", "Placeholder", "Ajuda", "Ordem", "Ativa"
                ]
                questions_sheet.append_row(headers)
                
                # Exemplos de perguntas
                sample_questions = [
                    ["nome", "Dados Pessoais", "Nome Completo", "text", "Sim", "", "Digite seu nome completo", "Nome como aparece no documento", "1", "Sim"],
                    ["email", "Dados Pessoais", "Email de Contacto", "email", "Sim", "", "exemplo@email.com", "Email válido para contacto", "2", "Sim"],
                    ["telefone", "Dados Pessoais", "Número de Telefone", "tel", "Sim", "", "+351 xxx xxx xxx", "Número com código do país", "3", "Sim"],
                    ["cv", "Documentos", "Carregue o seu CV", "file", "Sim", "", "", "Arquivo PDF, DOC, DOCX ou TXT", "4", "Sim"],
                    ["experiencia", "Experiência", "Tem experiência com cuidados?", "radio", "Não", "Sim|Não", "", "Experiência prévia na área", "5", "Sim"],
                    ["tipo_experiencia", "Experiência", "Tipo de experiência", "checkbox", "Não", "Apoio domiciliário|Lares ou instituições|Hospitalar|Outro", "", "Selecione todos que se aplicam", "6", "Sim"],
                    ["formacao", "Formação", "Descreva sua formação", "textarea", "Sim", "", "Descreva detalhadamente...", "Informações sobre formação acadêmica", "7", "Sim"]
                ]
                
                for question in sample_questions:
                    questions_sheet.append_row(question)
                
                logger.info("Template de perguntas adicionado à aba Perguntas")
                
                # Atualizar all_values após adicionar dados
                all_values = questions_sheet.get_all_values()
            
            # Verificar se há pelo menos cabeçalhos
            if len(all_values) < 2:  # Apenas cabeçalhos, sem dados
                logger.warning("Aba Perguntas só tem cabeçalhos, sem perguntas configuradas")
                return []
            
            # Ler todas as perguntas usando get_all_records
            records = questions_sheet.get_all_records()
            
        except Exception as e:
            logger.error(f"Erro ao ler dados da aba Perguntas: {str(e)}")
            logger.error("Tentando método alternativo de leitura...")
            
            # Método alternativo: ler manualmente
            try:
                all_values = questions_sheet.get_all_values()
                if not all_values or len(all_values) < 2:
                    logger.warning("Não há dados suficientes na aba Perguntas")
                    return []
                
                headers = all_values[0]
                records = []
                
                for row in all_values[1:]:
                    if len(row) >= len(headers):
                        record = {}
                        for i, header in enumerate(headers):
                            record[header] = row[i] if i < len(row) else ""
                        records.append(record)
                
                logger.info(f"Lidas {len(records)} perguntas usando método alternativo")
                
            except Exception as e2:
                logger.error(f"Erro no método alternativo: {str(e2)}")
                return []
        
        # Filtrar apenas perguntas ativas e ordenar
        active_questions = [q for q in records if q.get('Ativa', '').lower() == 'sim']
        active_questions.sort(key=lambda x: int(x.get('Ordem', 999)) if str(x.get('Ordem', '')).isdigit() else 999)
        
        logger.info(f"Encontradas {len(active_questions)} perguntas ativas")
        return active_questions
    
    try:
        return with_file_cache('questions_dynamic', _fetch_questions, force_refresh)
    except Exception as e:
        logger.error(f"Erro ao obter perguntas dinâmicas: {str(e)}")
        logger.error(traceback.format_exc())
        return [] 

def save_dynamic_form_data(form_data, questions):
    """
    Salva dados do formulário dinâmico baseado nas perguntas configuradas
    """
    try:
        logger.info("Iniciando salvamento de dados do formulário dinâmico")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se existe aba "Respostas Dinâmicas"
        try:
            responses_sheet = sheet.worksheet("Respostas Dinâmicas")
            logger.info("Aba 'Respostas Dinâmicas' encontrada")
        except gspread.exceptions.WorksheetNotFound:
            # Criar nova aba
            logger.info("Aba 'Respostas Dinâmicas' não encontrada. Criando nova aba.")
            responses_sheet = sheet.add_worksheet(title="Respostas Dinâmicas", rows=1000, cols=50)
            
            # Criar cabeçalhos baseados nas perguntas
            headers = ["Data/Hora", "Status", "Classificação IA", "Justificação IA", "Provedor IA"]
            
            # Adicionar cabeçalhos das perguntas ordenadas
            sorted_questions = sorted(questions, key=lambda x: int(x.get('Ordem', 999)))
            for question in sorted_questions:
                headers.append(question['Pergunta'])
            
            # Adicionar cabeçalhos extras
            headers.extend(["CV URL", "Email Enviado"])
            
            responses_sheet.append_row(headers)
            logger.info("Cabeçalhos criados na aba 'Respostas Dinâmicas'")
        
        # Obter cabeçalhos existentes
        headers = responses_sheet.row_values(1)
        logger.info(f"Cabeçalhos encontrados: {len(headers)} colunas")
        
        # Preparar dados da linha
        row_data = [""] * len(headers)
        
        # Preencher dados fixos
        row_data[0] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")  # Data/Hora
        row_data[1] = "NOVO"  # Status
        row_data[2] = form_data.get('classificacao', '')  # Classificação IA
        row_data[3] = form_data.get('justificacao', '')  # Justificação IA
        row_data[4] = form_data.get('provider', '')  # Provedor IA
        
        # Preencher respostas das perguntas
        for i, header in enumerate(headers):
            if i < 5:  # Pular colunas fixas
                continue
                
            # Procurar pergunta correspondente
            for question in questions:
                if question['Pergunta'] == header:
                    question_id = question['ID']
                    
                    # Verificar se é campo de múltipla escolha (checkbox)
                    if question['Tipo'] == 'checkbox':
                        # Dados de checkbox vêm como lista
                        values = form_data.get(f"{question_id}[]", [])
                        if isinstance(values, list):
                            row_data[i] = "; ".join(values)
                        else:
                            row_data[i] = values
                    else:
                        row_data[i] = form_data.get(question_id, '')
                    break
            
            # Campos especiais
            if header == "CV URL":
                row_data[i] = form_data.get('cv_url', '')
            elif header == "Email Enviado":
                row_data[i] = "Não"
        
        # Adicionar linha à planilha
        logger.info("Adicionando linha à planilha dinâmica")
        responses_sheet.append_row(row_data)
        logger.info("Dados salvos com sucesso na planilha dinâmica")
        
        # Invalidar cache
        default_file_cache.invalidate('candidates_all')
        default_file_cache.invalidate('questions_dynamic')
        logger.info("Cache invalidado após nova submissão")
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao salvar dados do formulário dinâmico: {str(e)}")
        logger.error(traceback.format_exc())
        raise 

def get_all_questions():
    """
    Obtém todas as perguntas (ativas e inativas) da aba 'Perguntas' da planilha
    Retorna uma lista de dicionários com as configurações das perguntas
    """
    try:
        logger.info("Tentando obter todas as perguntas da planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Perguntas existe
        try:
            questions_sheet = sheet.worksheet("Perguntas")
            logger.info("Aba Perguntas encontrada")
        except gspread.exceptions.WorksheetNotFound:
            logger.warning("Aba Perguntas não encontrada")
            return []
        
        # Verificar se a planilha tem dados
        try:
            all_values = questions_sheet.get_all_values()
            if not all_values or len(all_values) < 2:
                logger.warning("Não há perguntas configuradas")
                return []
            
            # Ler todas as perguntas usando get_all_records
            records = questions_sheet.get_all_records()
            
        except Exception as e:
            logger.error(f"Erro ao ler dados da aba Perguntas: {str(e)}")
            # Método alternativo: ler manualmente
            try:
                all_values = questions_sheet.get_all_values()
                if not all_values or len(all_values) < 2:
                    return []
                
                headers = all_values[0]
                records = []
                
                for row in all_values[1:]:
                    if len(row) >= len(headers):
                        record = {}
                        for i, header in enumerate(headers):
                            record[header] = row[i] if i < len(row) else ""
                        records.append(record)
                
            except Exception as e2:
                logger.error(f"Erro no método alternativo: {str(e2)}")
                return []
        
        # Ordenar por ordem
        all_questions = sorted(records, key=lambda x: int(x.get('Ordem', 999)) if str(x.get('Ordem', '')).isdigit() else 999)
        
        logger.info(f"Encontradas {len(all_questions)} perguntas no total")
        return all_questions
    
    except Exception as e:
        logger.error(f"Erro ao obter todas as perguntas: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def save_questions_to_sheet(questions_data):
    """
    Salva todas as perguntas na aba 'Perguntas' da planilha
    questions_data: lista de listas com os dados das perguntas
    """
    try:
        logger.info("Salvando perguntas na planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Perguntas existe
        try:
            questions_sheet = sheet.worksheet("Perguntas")
        except gspread.exceptions.WorksheetNotFound:
            # Criar nova aba
            questions_sheet = sheet.add_worksheet(title="Perguntas", rows=100, cols=10)
        
        # Limpar a planilha
        questions_sheet.clear()
        
        # Adicionar cabeçalhos
        headers = [
            "ID", "Secao", "Pergunta", "Tipo", "Obrigatoria", "Opcoes", "Placeholder", "Ajuda", "Ordem", "Ativa"
        ]
        questions_sheet.append_row(headers)
        
        # Adicionar todas as perguntas
        for question_data in questions_data:
            questions_sheet.append_row(question_data)
        
        logger.info(f"Salvadas {len(questions_data)} perguntas na planilha")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao salvar perguntas: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def add_question_to_sheet(question_data):
    """
    Adiciona uma nova pergunta à aba 'Perguntas' da planilha
    question_data: dicionário com os dados da pergunta
    """
    try:
        logger.info("Adicionando nova pergunta à planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Perguntas existe
        try:
            questions_sheet = sheet.worksheet("Perguntas")
        except gspread.exceptions.WorksheetNotFound:
            # Criar nova aba
            questions_sheet = sheet.add_worksheet(title="Perguntas", rows=100, cols=10)
            # Adicionar cabeçalhos
            headers = [
                "ID", "Secao", "Pergunta", "Tipo", "Obrigatoria", "Opcoes", "Placeholder", "Ajuda", "Ordem", "Ativa"
            ]
            questions_sheet.append_row(headers)
        
        # Obter próxima ordem
        all_questions = get_all_questions()
        next_order = len(all_questions) + 1
        
        # Preparar dados da linha
        row_data = [
            question_data.get('id', f"q_{next_order}"),
            question_data.get('section', 'Geral'),
            question_data.get('question', ''),
            question_data.get('type', 'text'),
            question_data.get('required', 'Não'),
            question_data.get('options', ''),
            question_data.get('placeholder', ''),
            question_data.get('help', ''),
            str(next_order),
            question_data.get('active', 'Sim')
        ]
        
        # Adicionar à planilha
        questions_sheet.append_row(row_data)
        
        logger.info("Nova pergunta adicionada com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao adicionar pergunta: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def delete_question_from_sheet(question_id):
    """
    Remove uma pergunta da aba 'Perguntas' da planilha
    question_id: ID da pergunta a ser removida
    """
    try:
        logger.info(f"Removendo pergunta {question_id} da planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Perguntas existe
        try:
            questions_sheet = sheet.worksheet("Perguntas")
        except gspread.exceptions.WorksheetNotFound:
            logger.warning("Aba Perguntas não encontrada")
            return False
        
        # Encontrar a linha da pergunta
        all_values = questions_sheet.get_all_values()
        if len(all_values) < 2:
            logger.warning("Não há perguntas para remover")
            return False
        
        # Procurar pela pergunta
        row_to_delete = None
        for i, row in enumerate(all_values[1:], start=2):  # Começar da linha 2 (pular cabeçalho)
            if len(row) > 0 and row[0] == question_id:
                row_to_delete = i
                break
        
        if row_to_delete:
            questions_sheet.delete_rows(row_to_delete)
            logger.info(f"Pergunta {question_id} removida com sucesso")
            return True
        else:
            logger.warning(f"Pergunta {question_id} não encontrada")
            return False
        
    except Exception as e:
        logger.error(f"Erro ao remover pergunta: {str(e)}")
        logger.error(traceback.format_exc())
        return False 

def get_all_forms(force_refresh=False):
    """
    Obtém todos os formulários configurados da aba 'Formularios' com file cache
    Retorna uma lista de dicionários com as configurações dos formulários
    """
    def _fetch_forms():
        logger.info("Tentando obter todos os formulários da planilha...")
        client = get_sheet_client()
        
        # Usar ID direto em vez do nome da planilha
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        
        # Verificar se a aba Formularios existe
        try:
            forms_sheet = sheet.worksheet("Formularios")
            logger.info("Aba Formularios encontrada")
        except gspread.exceptions.WorksheetNotFound:
            logger.info("Aba Formularios não encontrada. Criando...")
            forms_sheet = sheet.add_worksheet(title="Formularios", rows="100", cols="10")
            
            # Adicionar cabeçalhos
            headers = [
                "ID", "Nome", "Descricao", "Ativo", "DataCriacao", 
                "DataModificacao", "Autor", "Categoria", "Ordem", "Configuracoes"
            ]
            forms_sheet.append_row(headers)
            
            # Adicionar formulário padrão
            default_form = [
                "form_cuidadores", 
                "Candidatura para Cuidadores", 
                "Formulário principal para candidaturas de cuidadores",
                "Sim",
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "Sistema",
                "Recrutamento",
                "1",
                "{}"
            ]
            forms_sheet.append_row(default_form)
            logger.info("Aba Formularios criada com formulário padrão")
        
        # Verificar se a planilha tem dados antes de tentar ler
        try:
            all_values = forms_sheet.get_all_values()
            if not all_values or len(all_values) < 2:
                logger.warning("Aba Formularios está vazia ou só tem cabeçalhos.")
                return []
            
            # Ler todas as configurações de formulários
            records = forms_sheet.get_all_records()
            
            logger.info(f"Encontrados {len(records)} formulários configurados")
            return records
            
        except Exception as e:
            logger.error(f"Erro ao ler dados da aba Formularios: {str(e)}")
            return []
    
    try:
        return with_file_cache('forms_all', _fetch_forms, force_refresh)
    except Exception as e:
        logger.error(f"Erro ao obter formulários: {str(e)}")
        logger.error(traceback.format_exc())
        return []

def get_active_forms():
    """
    Obtém apenas os formulários ativos
    """
    try:
        all_forms = get_all_forms()
        active_forms = [form for form in all_forms if form.get('Ativo', '').lower() == 'sim']
        
        # Ordenar por ordem
        active_forms.sort(key=lambda x: int(x.get('Ordem', 999)))
        
        logger.info(f"Encontrados {len(active_forms)} formulários ativos")
        return active_forms
        
    except Exception as e:
        logger.error(f"Erro ao obter formulários ativos: {str(e)}")
        return []

def get_form_questions(form_id):
    """
    Obtém as perguntas de um formulário específico
    """
    try:
        logger.info(f"Obtendo perguntas para o formulário: {form_id}")
        
        # Por enquanto, usar a aba Perguntas existente
        # No futuro, pode ser expandido para ter perguntas específicas por formulário
        questions = get_dynamic_questions()
        
        logger.info(f"Encontradas {len(questions)} perguntas para o formulário {form_id}")
        return questions
        
    except Exception as e:
        logger.error(f"Erro ao obter perguntas do formulário {form_id}: {str(e)}")
        return []

def save_form_configuration(form_data):
    """
    Salva ou atualiza a configuração de um formulário
    """
    try:
        logger.info("Salvando configuração do formulário...")
        client = get_sheet_client()
        
        SPREADSHEET_ID = "1UvH63UVLS8KkQJIh6y9hOvygOv2H6GWGZvKTAKMKFzc"
        sheet = client.open_by_key(SPREADSHEET_ID)
        forms_sheet = sheet.worksheet("Formularios")
        
        # Verificar se o formulário já existe
        records = forms_sheet.get_all_records()
        existing_row = None
        
        for i, record in enumerate(records):
            if record.get('ID') == form_data.get('ID'):
                existing_row = i + 2  # +2 porque records não inclui cabeçalho e é 1-indexed
                break
        
        # Preparar dados
        row_data = [
            form_data.get('ID', ''),
            form_data.get('Nome', ''),
            form_data.get('Descricao', ''),
            form_data.get('Ativo', 'Não'),
            form_data.get('DataCriacao', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # DataModificacao sempre atual
            form_data.get('Autor', 'Admin'),
            form_data.get('Categoria', 'Geral'),
            form_data.get('Ordem', '1'),
            form_data.get('Configuracoes', '{}')
        ]
        
        if existing_row:
            # Atualizar formulário existente
            forms_sheet.update(f'A{existing_row}:J{existing_row}', [row_data])
            logger.info(f"Formulário {form_data.get('ID')} atualizado")
        else:
            # Adicionar novo formulário
            forms_sheet.append_row(row_data)
            logger.info(f"Novo formulário {form_data.get('ID')} criado")
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao salvar configuração do formulário: {str(e)}")
        logger.error(traceback.format_exc())
        return False 